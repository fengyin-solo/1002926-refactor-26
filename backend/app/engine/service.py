"""统一动作服务：顺序、授权、重复提交三项判定在这里收口。

判定顺序（每一关不通过都返回可读原因，不改数据）：

1. 记录是否存在；
2. 动作是否属于本模块——拿别的模块的动作来投，当场挡回并指明它的归属模块；
3. 当前角色对本模块是否授权，缺授权讲清楚需要哪个模块的权限；
4. 是否重复提交——同一记录的同一动作只认第一次；
5. 状态序列——动作只能把记录推进到紧挨着的下一档，回退、跳级、原地不动都拦下。

列表与明细返回的 ``allowed_actions`` 同样由这里计算，保证另一个页面读到的
可执行动作与动作入口完全一致。
"""
from __future__ import annotations

import threading
from typing import Any

from app.engine import auth
from app.engine.registry import ModuleSpec, registry
from app.store import store


class ActionError(Exception):
    """动作被统一判定拦下时抛出，message 即给调用方看的原因。"""


class IdempotencyGuard:
    """同一（模块、记录、动作）只认第一次提交；进程内加锁防并发双击。"""

    def __init__(self) -> None:
        self._done: set[tuple[str, int, str]] = set()
        self._locks: dict[tuple[str, int, str], threading.Lock] = {}
        self._guard = threading.Lock()

    def lock_for(self, key: tuple[str, int, str]) -> threading.Lock:
        with self._guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._locks[key] = lock
            return lock

    def already_done(self, key: tuple[str, int, str]) -> bool:
        return key in self._done

    def mark_done(self, key: tuple[str, int, str]) -> None:
        self._done.add(key)


_guard = IdempotencyGuard()


class ModuleService:
    """二十个模块共用的服务实现；每个模块只提供自己的 :class:`ModuleSpec`。"""

    def __init__(self, module: str) -> None:
        self.spec: ModuleSpec = registry.get(module)
        self.module = module

    # ---- 读取 ----------------------------------------------------------

    def list_entries(
        self,
        *,
        role: str | None = None,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(self.module)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get(self.spec.keyword_field, ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        page_rows = [self._with_actions(row, role) for row in rows[start:start + size]]
        return page_rows, total

    def get_entry(self, entry_id: int, *, role: str | None = None) -> dict[str, Any] | None:
        row = store.find(self.module, entry_id)
        return self._with_actions(row, role) if row is not None else None

    # ---- 写入 ----------------------------------------------------------

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [
            field for field in self.spec.required_fields
            if not str(values.get(field) or "").strip()
        ]
        if missing:
            return None, missing
        rows = store.rows(self.module)
        entry: dict[str, Any] = {
            "id": max((int(row.get("id", 0)) for row in rows), default=0) + 1,
        }
        entry.update({field: values.get(field) for field in self.spec.required_fields})
        entry["status"] = self.spec.status_order[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return self._with_actions(entry, None), []

    def run_action(
        self,
        entry_id: int,
        action: str,
        *,
        role: str | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        """执行动作。成功返回 (最新记录, 说明)；被拦下返回 (None, 原因)。"""
        entry = store.find(self.module, entry_id)
        if entry is None:
            return None, f"{self.spec.label} {entry_id} 不存在或已归档"

        action = (action or "").strip()

        # 越权/误投：动作名在不同模块间可能重名（如压力表与安全阀都有「登记合格」），
        # 因此先认本模块动作；确实不属于本模块时，再反查它在别处的归属并指明。
        target = self.spec.action_rules.get(action)
        if target is None:
            owner = registry.owner_of(action) if action else None
            if owner is None:
                return None, f"动作「{action}」不属于{self.spec.title}可执行范围"
            owner_title = registry.get(owner).title
            return (
                None,
                f"动作「{action}」属于{owner_title}模块，不能在{self.spec.title}发起；"
                f"请到{owner_title}页面对应记录上操作",
            )

        # 授权：当前角色对本模块没有授权，说明缺的是哪一项。
        if not auth.can_act(role, self.module):
            return None, self._missing_grant_message(role)

        key = (self.module, entry_id, action)
        lock = _guard.lock_for(key)
        with lock:
            # 重复提交：同一记录同一动作只认第一次。
            if _guard.already_done(key):
                return None, f"动作「{action}」已提交并生效，请勿重复发起"

            current = str(entry.get("status") or "")
            current_step = self.spec.step_of(current)
            target_step = self.spec.step_of(target)

            # 顺序：只能沿状态序列逐级往下走。
            if current_step < 0:
                return None, f"当前状态「{current}」不在{self.spec.title}的状态序列里，无法判定下一步"
            if target_step < current_step:
                return (
                    None,
                    f"动作「{action}」会把状态从「{current}」回退到「{target}」；"
                    f"流程只能逐级前进，不能回到上一档",
                )
            if target_step == current_step:
                return (
                    None,
                    f"记录当前已是「{current}」，动作「{action}」停在原档、没有推进，"
                    f"无需重复执行",
                )
            if target_step > current_step + 1:
                return (
                    None,
                    f"动作「{action}」要从「{current}」直接跳到「{target}」，"
                    f"中间还有「{self.spec.status_order[current_step + 1]}」未完成，不能跨档执行",
                )

            entry["status"] = target
            entry["pending"] = target != self.spec.status_order[-1]
            entry["abnormal"] = action == self.spec.negative_action
            _guard.mark_done(key)
            return self._with_actions(entry, role), f"{self.spec.label}已{action}"

    # ---- 统一推导 ------------------------------------------------------

    def allowed_actions(self, entry: dict[str, Any], role: str | None = None) -> list[str]:
        """某条记录在当前角色下真正可执行的动作：本模块、已授权、目标恰为下一档。"""
        if not auth.can_act(role, self.module):
            return []
        current_step = self.spec.step_of(entry.get("status"))
        if current_step < 0 or current_step >= len(self.spec.status_order) - 1:
            return []
        next_status = self.spec.status_order[current_step + 1]
        return [
            action
            for action, target in self.spec.action_rules.items()
            if target == next_status
        ]

    def _with_actions(self, entry: dict[str, Any], role: str | None) -> dict[str, Any]:
        view = dict(entry)
        view["allowed_actions"] = self.allowed_actions(entry, role)
        view["module"] = self.module
        return view

    def _missing_grant_message(self, role: str | None) -> str:
        normalized = auth.normalize_role(role)
        if not normalized:
            return f"未携带操作身份，无权在{self.spec.title}发起动作；请先选择值班角色后再操作"
        if normalized.startswith("unknown:"):
            return f"身份「{role}」未在系统登记，无权在{self.spec.title}发起动作；请联系管理员开通授权"
        return (
            f"当前身份「{auth.role_label(role)}」没有{self.spec.title}的操作授权，"
            f"动作已挡回；请改用持有该模块授权的角色，或申请增补「{self.spec.title}」权限"
        )


def get_service(module: str) -> ModuleService:
    return ModuleService(module)
