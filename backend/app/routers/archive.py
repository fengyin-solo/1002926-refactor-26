"""档案管理接口：维护档案，覆盖办理借阅、登记归还、申请销毁等动作。

可执行动作不在各页面各抄一份：列表与明细统一带出 allowed_actions，
动作顺序、跨模块拦截、授权与重复提交都由统一动作引擎判定。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.archive import ArchiveService

router = APIRouter(prefix="/api/archive", tags=["档案管理"])

service = ArchiveService()

LIST_FIELDS = ['档案编号', '所属设备', '档案类别', '归档日期', '借阅人', '借阅日期', '归还日期', '档案状态']
STATUSES = ['在库', '借出中', '已归还', '已销毁']


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按档案编号检索"),
    status: str | None = Query(default=None, description="在库、借出中、已归还、已销毁"),
    page: int = 1,
    size: int = 20,
    x_operator_role: str | None = Header(default=None, alias="X-Operator-Role"),
) -> PageResult[dict]:
    """按档案编号与状态过滤档案管理列表；每条记录只返回当前可执行的动作。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(
        role=x_operator_role, keyword=keyword, status=status, page=page, size=size
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries(
    x_operator_role: str | None = Header(default=None, alias="X-Operator-Role"),
) -> dict[str, Any]:
    """导出档案管理清单：返回当前过滤条件下的全量数据，可执行动作与列表口径一致。"""
    items, total = service.list_entries(role=x_operator_role, page=1, size=10000)
    return {"module": "archive", "total": total, "items": items}

@router.get("/{entry_id}", response_model=dict)
def get_entry(
    entry_id: int,
    x_operator_role: str | None = Header(default=None, alias="X-Operator-Role"),
) -> dict:
    """读取单条档案明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id, role=x_operator_role)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"档案 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条档案，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="档案已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(
    entry_id: int,
    payload: EntryPayload,
    x_operator_role: str | None = Header(default=None, alias="X-Operator-Role"),
) -> ActionResult:
    """对单条档案执行办理借阅、登记归还、申请销毁；回退/跳级、越权、缺授权、重复提交都会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action, role=x_operator_role)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)

