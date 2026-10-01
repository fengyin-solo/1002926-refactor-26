"""内存数据仓库：给每个业务模块准备一份可筛选、可流转的示例数据。

真实项目里这里会换成数据库访问层；当前实现只依赖标准库，保证克隆下来就能起。
"""
from __future__ import annotations

from typing import Any

from app.seed import SEED_ROWS
from app.workflow import SPEC_BY_KEY


class Store:
    def __init__(self) -> None:
        self._tables: dict[str, list[dict[str, Any]]] = {
            name: [self._normalize(name, dict(row)) for row in rows]
            for name, rows in SEED_ROWS.items()
        }

    @staticmethod
    def _normalize(module: str, row: dict[str, Any]) -> dict[str, Any]:
        """补齐动作账本字段，并按统一状态机口径校正 pending/abnormal。

        示例数据里这两个标志是随手填的，这里统一以状态序为准，避免看板与动作判定不一致。
        """
        spec = SPEC_BY_KEY.get(module)
        status = row.get("status")
        if spec is not None and status in spec.statuses:
            index = spec.statuses.index(status)  # type: ignore[arg-type]
            row["pending"] = status != spec.terminal_status
            row["abnormal"] = index == 1
            # 初始就处于第 N 档的示例数据，视为前 N 个动作均已完成，保持状态与账本一致，
            # 否则列表会放行当前动作、提交时却因缺少前序记录而被误判为跳档。
            row["_performed"] = list(spec.actions[:index])
        else:
            row.setdefault("_performed", [])
        return row

    def module_names(self) -> list[str]:
        return sorted(self._tables)

    def rows(self, module: str) -> list[dict[str, Any]]:
        return self._tables.setdefault(module, [])

    def find(self, module: str, entry_id: int) -> dict[str, Any] | None:
        for row in self.rows(module):
            if int(row.get("id", 0)) == entry_id:
                return row
        return None

    def overview(self) -> dict[str, object]:
        modules: list[dict[str, object]] = []
        for name in self.module_names():
            rows = self.rows(name)
            modules.append({
                "name": name,
                "created": len(rows),
                "pending": sum(1 for row in rows if row.get("pending")),
                "abnormal": sum(1 for row in rows if row.get("abnormal")),
            })
        cards = [
            {"label": "业务模块", "value": len(modules)},
            {"label": "今日新增", "value": sum(int(item["created"]) for item in modules)},
            {"label": "待处理", "value": sum(int(item["pending"]) for item in modules)},
            {"label": "异常量", "value": sum(int(item["abnormal"]) for item in modules)},
        ]
        return {"cards": cards, "modules": modules}


store = Store()
