"""起重机械接口：路径、方法与动作名保持不变，实现统一走 app.routers.common。"""
from __future__ import annotations

from app.routers.common import build_router
from app.services.crane import CraneService

service = CraneService()
router = build_router(service)
