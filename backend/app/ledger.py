"""动作账本：记录每条记录已经执行过的动作，保证同一动作重复提交只认第一次。

内存实现，与 Store 一样只依赖标准库；真实项目里这张表会落库并加唯一约束。
键约定：``(模块, 记录id, 动作名)`` 只能成功写入一次。
"""
from __future__ import annotations

from threading import Lock


class ActionLedger:
    def __init__(self) -> None:
        self._done: set[tuple[str, int, str]] = set()
        self._lock = Lock()

    def claim(self, module: str, entry_id: int, action: str) -> bool:
        """尝试占用一次动作。首次返回 True 并记账；重复提交返回 False，状态不再变更。"""
        key = (module, entry_id, action)
        with self._lock:
            if key in self._done:
                return False
            self._done.add(key)
            return True

    def performed(self, module: str, entry_id: int) -> list[str]:
        prefix = (module, entry_id)
        return sorted(action for mod, eid, action in self._done if (mod, eid) == prefix)

    def reset(self) -> None:
        with self._lock:
            self._done.clear()


ledger = ActionLedger()
