from ..schemas import stats
from ..utils import singleton

@singleton.singleton_thread_safe
class MemoryStats(stats.Stats):
    def __init__(self):
        self._stats = {}
    
    async def value(self, key : str) -> stats.ValueType:
        return self._stats.get(key, None)
    
    async def set(self, key : str, value : stats.ValueType) -> None:
        self._stats[key] = value
    
    async def incr(self, key : str, value : int = 1) -> None:
        self._stats[key] = self._stats.get(key, 0) + value
    
    async def decr(self, key : str, value : int = 1) -> None:
        self._stats[key] = self._stats.get(key, 0) - value
    
    async def has(self, key : str) -> bool:
        return key in self._stats
    
    async def add(self, key : str, value : stats.ValueType) -> None:
        if not isinstance(self._stats.get(key, None), list):
            self._stats[key] = []
        self._stats[key].append(value)
    
    async def remove(self, key : str, value : stats.ValueType) -> None:
        if isinstance(self._stats.get(key, None), list):
            self._stats[key].remove(value)
    
    async def contains(self, key : str, value : stats.ValueType) -> bool:
        if isinstance(self._stats.get(key, None), list):
            return value in self._stats[key]
        return False
    
    async def clear(self, key : str) -> None:
        del self._stats[key]

    