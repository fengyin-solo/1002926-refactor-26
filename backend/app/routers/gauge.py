"""压力表检定接口：路径、方法与动作名保持不变，实现统一走 app.routers.common。"""
from __future__ import annotations

from app.routers.common import build_router
from app.services.gauge import GaugeService

service = GaugeService()
router = build_router(service)
