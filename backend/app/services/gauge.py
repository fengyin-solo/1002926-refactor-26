"""压力表检定服务：状态序列、动作顺序、授权与去重统一由动作引擎判定。"""
from __future__ import annotations

from app.engine import ModuleService


def GaugeService() -> ModuleService:  # noqa: N802 - 保持既有服务名，路由层零改动
    return ModuleService('gauge')
