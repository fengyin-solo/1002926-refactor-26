"""场车管理接口：维护场内车辆，覆盖安排维修、安排年检、申请报废等动作。

可执行动作不在各页面各抄一份：列表与明细统一带出 allowed_actions，
动作顺序、跨模块拦截、授权与重复提交都由统一动作引擎判定。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.forklift import ForkliftService

router = APIRouter(prefix="/api/forklift", tags=["场车管理"])

service = ForkliftService()

LIST_FIELDS = ['车辆编号', '车辆类型', '动力类型', '核定载重', '行驶区域', '驾驶员', '年检日期', '车辆状态']
STATUSES = ['正常', '维修中', '待年检', '已报废']


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按车辆编号检索"),
    status: str | None = Query(default=None, description="正常、维修中、待年检、已报废"),
    page: int = 1,
    size: int = 20,
    x_operator_role: str | None = Header(default=None, alias="X-Operator-Role"),
) -> PageResult[dict]:
    """按车辆编号与状态过滤场车管理列表；每条记录只返回当前可执行的动作。"""
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
    """导出场车管理清单：返回当前过滤条件下的全量数据，可执行动作与列表口径一致。"""
    items, total = service.list_entries(role=x_operator_role, page=1, size=10000)
    return {"module": "forklift", "total": total, "items": items}

@router.get("/{entry_id}", response_model=dict)
def get_entry(
    entry_id: int,
    x_operator_role: str | None = Header(default=None, alias="X-Operator-Role"),
) -> dict:
    """读取单条场内车辆明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id, role=x_operator_role)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"场内车辆 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条场内车辆，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="场内车辆已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(
    entry_id: int,
    payload: EntryPayload,
    x_operator_role: str | None = Header(default=None, alias="X-Operator-Role"),
) -> ActionResult:
    """对单条场内车辆执行安排维修、安排年检、申请报废；回退/跳级、越权、缺授权、重复提交都会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action, role=x_operator_role)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)

