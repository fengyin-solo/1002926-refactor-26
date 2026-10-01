"""接口层公共件：当前操作角色解析 + 标准 CRUD/动作路由工厂。

各业务模块的路径、HTTP 方法、动作名都保持不变；区别仅在于实现从“每模块抄一份”
换成统一工厂，服务层返回什么可执行动作，这里就原样透出。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Header

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.base import BaseService
from app.workflow import ROLE_STEPS, WorkflowSpec


def current_role(x_operator_role: str | None = Header(default=None, alias="X-Operator-Role")) -> str | None:
    """从请求头读取当前操作角色；非三档角色之一时视为未授权（None）。"""
    role = (x_operator_role or "").strip()
    return role if role in ROLE_STEPS else None


def build_router(service: BaseService) -> APIRouter:
    """按模块规格生成既有接口：列表、明细、登记、动作、导出。"""
    spec: WorkflowSpec = service.spec
    label = spec.label
    router = APIRouter(prefix=f"/api/{spec.key}", tags=[label])

    @router.get("", response_model=PageResult[dict])
    def list_entries(
        keyword: str | None = Query(default=None, description=f"按{spec.keyword_field}检索"),
        status: str | None = Query(default=None, description="、".join(spec.statuses)),
        page: int = 1,
        size: int = 20,
        role: str | None = current_role,
    ) -> PageResult[dict]:
        """按编号与状态过滤列表；每行带 allowedActions，与动作入口同源。"""
        if size > 200:
            raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
        items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size, role=role)
        return PageResult(items=items, total=total, page=page, size=size)

    @router.get("/export")
    def export_entries() -> dict[str, Any]:
        """导出模块清单：返回当前模块的全量数据。"""
        items, total = service.list_entries(page=1, size=10000)
        return {"module": spec.key, "total": total, "items": items}

    @router.get("/{entry_id}", response_model=dict)
    def get_entry(entry_id: int, role: str | None = current_role) -> dict[str, Any]:
        """读取单条明细；不存在时给出可读的错误说明。"""
        entry = service.get_entry(entry_id, role=role)
        if entry is None:
            raise HTTPException(status_code=404, detail=f"{label} {entry_id} 不存在或已归档")
        return entry

    @router.post("", response_model=ActionResult)
    def create_entry(payload: EntryPayload) -> ActionResult:
        """登记一条记录，缺字段时说明原因而不是静默丢弃。"""
        entry, missing = service.create_entry(payload.values)
        if missing:
            return ActionResult(ok=False, code="missing_fields", message=f"缺少必填字段：{'、'.join(missing)}")
        return ActionResult(ok=True, message=f"{label}已登记", entry=entry)

    @router.post("/{entry_id}/actions", response_model=ActionResult)
    def run_action(entry_id: int, payload: EntryPayload, role: str | None = current_role) -> ActionResult:
        """执行单条动作；回退/越权/跳档/重复提交都会被拦下并说明原因。"""
        action = str(payload.values.get("action") or "").strip()
        entry, message, code = service.run_action(entry_id, action, role)
        if entry is None:
            return ActionResult(ok=False, code=code, message=message)
        return ActionResult(ok=True, code="ok", message=message, entry=entry)

    return router
