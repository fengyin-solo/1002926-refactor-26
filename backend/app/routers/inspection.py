"""定期检验接口：路径、方法与动作名保持不变，实现统一走 app.routers.common。"""
from __future__ import annotations

from app.routers.common import build_router
from app.services.inspection import InspectionService

service = InspectionService()
router = build_router(service)
