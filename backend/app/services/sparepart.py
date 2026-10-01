"""备件管理业务规则：状态序列、动作授权与逐级流转统一收敛到 app.services.base。"""
from __future__ import annotations

from app.services.base import BaseService


class SparepartService(BaseService):
    module = "sparepart"
