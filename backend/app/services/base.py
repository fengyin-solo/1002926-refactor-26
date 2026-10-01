"""统一动作判定引擎与服务基类。

二十个模块的服务都继承 :class:`BaseService`，只提供模块 key；状态序列、动作权限、
逐级推进、回退拦截、越权挡回、重复提交去重全部走这里的同一份实现。

驳回均以 ``code`` 标注原因，前端可据此给出稳定提示：
- not_found      记录不存在
- foreign_action 动作属于其他模块（越权发起）
- unknown_action 动作不在任何模块的可执行范围
- forbidden      当前角色缺少该档授权
- backward       目标档早于当前档（回退/越级后退），不允许
- skip_ahead     还有中间档未完成（跳档）
- duplicate      该动作已执行过，重复提交只认第一次
- terminal       已到末档，无后续动作
"""
from __future__ import annotations

from typing import Any

from app.ledger import ledger
from app.store import store
from app.workflow import (
    ACTION_OWNER,
    ROLE_STEPS,
    SPEC_BY_KEY,
    WorkflowSpec,
)

# 内部记账字段，不对接口暴露
_RESERVED_KEYS = {"performed"}


def public_entry(entry: dict[str, Any], spec: WorkflowSpec, role: str | None) -> dict[str, Any]:
    """把内部记录转成对外结构，并按当前状态与角色实时计算可执行动作。

    其他页面读到的 allowedActions 与动作入口、服务层同源，保证口径一致。
    """
    data = {key: value for key, value in entry.items() if not key.startswith("_") and key not in _RESERVED_KEYS}
    data["allowedActions"] = allowed_actions(entry, spec, role)
    return data


def _current_step(entry: dict[str, Any], spec: WorkflowSpec) -> int:
    """当前状态在状态序里的档序：处于 statuses[i] 表示下一个可执行动作为 actions[i]。"""
    status = entry.get("status")
    try:
        return spec.statuses.index(status)  # type: ignore[arg-type]
    except ValueError:
        # 未知/历史状态一律视作起点之前，不允许任何动作，避免被绕过
        return -1


def allowed_actions(entry: dict[str, Any], spec: WorkflowSpec, role: str | None) -> list[str]:
    """仅返回“当前档 + 角色已授权 + 未执行过”的动作；末档或异常状态返回空。"""
    step = _current_step(entry, spec)
    if step < 0 or step >= len(spec.actions):
        return []
    action = spec.actions[step]
    required_role = ROLE_STEPS[step]
    if role != required_role:
        return []
    if action in entry.get("_performed", []):
        return []
    return [action]


def evaluate(
    spec: WorkflowSpec,
    entry: dict[str, Any] | None,
    action: str,
    role: str | None,
) -> tuple[str | None, str | None, int | None]:
    """统一守卫。通过返回 (None, None, 目标档序)，否则返回 (code, 说明, None)。"""
    if entry is None:
        return "not_found", f"{spec.label}记录不存在或已归档", None

    normalized = action.strip()
    if not normalized:
        return "unknown_action", "未指定要执行的动作", None

    # 越权：动作是其他模块的，当场挡回并指明归属。
    owner = ACTION_OWNER.get(normalized)
    if owner is not None and owner.key != spec.key:
        return (
            "foreign_action",
            f"动作「{normalized}」属于{owner.label}模块（/api/{owner.key}），不能在{spec.label}里发起",
            None,
        )

    step = spec.step_of_action(normalized)
    if step is None:
        return "unknown_action", f"动作「{normalized}」不属于{spec.label}可执行范围", None

    # 授权：每一档绑定固定角色，缺哪项讲清楚。
    required_role = ROLE_STEPS[step]
    if role != required_role:
        who = role or "未识别身份"
        return (
            "forbidden",
            f"动作「{normalized}」需要{required_role}授权，当前身份为{who}，无法发起",
            None,
        )

    current = _current_step(entry, spec)
    if current < 0:
        return "unknown_action", f"当前状态「{entry.get('status')}」不在{spec.label}允许的状态序列里", None

    # 重复提交：同一动作只认第一次（优先于档位判定，给最贴近的原因）。
    if normalized in entry.get("_performed", []):
        return "duplicate", f"动作「{normalized}」已执行过，重复提交只认第一次", None

    # 已到末档：没有再往后的动作。
    if current >= len(spec.actions):
        return "terminal", f"当前已到末档「{spec.statuses[-1]}」，没有可继续的动作", None

    # 回退：目标档早于当前档，拦下并说明。
    if step < current:
        return (
            "backward",
            f"当前处于「{spec.statuses[current]}」，动作「{normalized}」会回到「{spec.statuses[step]}」，"
            f"动作只能逐级向前，不能回退",
            None,
        )

    # 跳档：目标档晚于当前档。
    if step > current:
        return (
            "skip_ahead",
            f"需先完成「{spec.actions[current]}」进入「{spec.statuses[current + 1]}」，"
            f"才能执行「{normalized}」，不允许越级",
            None,
        )

    return None, None, step


class BaseService:
    """二十个模块共用的列表/明细/登记/动作流转实现。"""

    module: str = ""

    def __init__(self) -> None:
        self.spec: WorkflowSpec = SPEC_BY_KEY[self.module]

    # -- 读取 ---------------------------------------------------------------
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
        role: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(self.module)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get(self.spec.keyword_field, ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        page_rows = rows[start:start + size]
        return [public_entry(row, self.spec, role) for row in page_rows], total

    def get_entry(self, entry_id: int, *, role: str | None = None) -> dict[str, Any] | None:
        entry = store.find(self.module, entry_id)
        return public_entry(entry, self.spec, role) if entry is not None else None

    def _raw(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(self.module, entry_id)

    # -- 登记 ---------------------------------------------------------------
    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in self.spec.required_fields if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(self.module)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in self.spec.required_fields})
        entry["status"] = self.spec.statuses[0]
        entry["pending"] = True
        entry["abnormal"] = False
        entry["_performed"] = []
        rows.append(entry)
        return entry, []

    # -- 动作 ---------------------------------------------------------------
    def run_action(
        self,
        entry_id: int,
        action: str,
        role: str | None = None,
    ) -> tuple[dict[str, Any] | None, str, str | None]:
        """执行动作。成功返回 (对外记录, 成功说明, None)；失败返回 (None, 原因, code)。"""
        raw = self._raw(entry_id)
        code, message, step = evaluate(self.spec, raw if raw is not None else None, action, role)
        if code is not None:
            return None, message or "动作被拦截", code

        assert raw is not None and step is not None
        normalized = action.strip()
        if not ledger.claim(self.module, entry_id, normalized):
            # 并发下的兜底：记账已存在则视为重复提交。
            return None, f"动作「{normalized}」已执行过，重复提交只认第一次", "duplicate"

        target_status = self.spec.statuses[step + 1]
        raw["status"] = target_status
        raw["pending"] = target_status != self.spec.terminal_status
        # 异常口径与历史数据保持一致：处于中间预警档（第 2 档）视为异常，其余档为正常。
        raw["abnormal"] = (step + 1) == 1
        performed = raw.setdefault("_performed", [])
        performed.append(normalized)
        return public_entry(raw, self.spec, role), f"{self.spec.label}已{normalized}", None
