"""统一动作判定引擎。

所有模块的状态序列、动作顺序、授权口径与重复提交判定都收拢在这里，
各业务模块不再各自维护一份规则。
"""
from app.engine.auth import ROLE_LABELS, grants_for, roles
from app.engine.registry import ModuleSpec, registry
from app.engine.service import ActionError, ModuleService, get_service

__all__ = [
    "ActionError",
    "ModuleSpec",
    "ModuleService",
    "ROLE_LABELS",
    "get_service",
    "grants_for",
    "registry",
    "roles",
]
