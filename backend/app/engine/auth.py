"""授权口径：角色与模块授权关系只有这一处。

当前演示用角色 -> 可操作模块集合。真实项目里这份表会换成用户中心/权限服务，
服务层只认 :func:`grants_for` 给出的授权集合，判定方式不用改。

请求通过 ``X-Operator-Role`` 头带上当前角色；不带时按值班管理员处理，
保持既有调用方（脚本、旧页面）行为不变。
"""
from __future__ import annotations

ROLE_ADMIN = "admin"
ROLE_INSPECTOR = "inspector"
ROLE_MAINTAINER = "maintainer"
ROLE_SUPERVISOR = "supervisor"

ROLE_LABELS: dict[str, str] = {
    ROLE_ADMIN: "值班管理员",
    ROLE_INSPECTOR: "检验员",
    ROLE_MAINTAINER: "维保员",
    ROLE_SUPERVISOR: "安全监督员",
}

# 检验口径：设备登记、承压类/机电类设备与定期检验、校验检定相关模块。
_INSPECTOR_GRANTS = frozenset({
    "register", "pressurevessel", "pipeline", "elevator", "crane",
    "forklift", "inspection", "safetyvalve", "gauge",
})

# 维保口径：锅炉、电梯维保与维保记录、备件、合同。
_MAINTAINER_GRANTS = frozenset({
    "boiler", "elevator", "maintenance", "sparepart", "contract",
})

# 安全监督口径：隐患、事故、应急、培训、人员、能效与档案。
_SUPERVISOR_GRANTS = frozenset({
    "hazard", "accident", "emergency", "training", "operator",
    "energyeff", "archive",
})

_GRANTS: dict[str, frozenset[str]] = {
    ROLE_ADMIN: frozenset(),  # 空集合在判定时按“全部授权”处理
    ROLE_INSPECTOR: _INSPECTOR_GRANTS,
    ROLE_MAINTAINER: _MAINTAINER_GRANTS,
    ROLE_SUPERVISOR: _SUPERVISOR_GRANTS,
}

DEFAULT_ROLE = ROLE_ADMIN


def roles() -> list[dict[str, str]]:
    """供页面角色切换使用：角色码与中文称谓。"""
    return [{"code": code, "label": ROLE_LABELS[code]} for code in _GRANTS]


def normalize_role(role: str | None) -> str:
    """未知角色归一化成空标记：一个授权都不给，而不是默认放行。"""
    role = (role or "").strip()
    return role if role in _GRANTS else ("" if not role else f"unknown:{role}")


def grants_for(role: str | None) -> frozenset[str]:
    """返回角色被授权的模块集合；不带身份时按默认值班角色处理。"""
    normalized = normalize_role(role)
    if not normalized:
        normalized = DEFAULT_ROLE
    return _GRANTS.get(normalized, frozenset())


def can_act(role: str | None, module: str) -> bool:
    """该角色能否在指定模块发起动作。不带身份按默认值班角色放行，显式未知角色一律拒绝。"""
    normalized = normalize_role(role)
    if not normalized:
        normalized = DEFAULT_ROLE
    grants = _GRANTS.get(normalized)
    if grants is None:
        return False
    return normalized == ROLE_ADMIN or module in grants


def role_label(role: str | None) -> str:
    normalized = normalize_role(role)
    if normalized in ROLE_LABELS:
        return ROLE_LABELS[normalized]
    return f"未识别角色（{role}）" if role else ROLE_LABELS[DEFAULT_ROLE]
