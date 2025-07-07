from ..schemas import stats

class NamedStats(stats.Stats):
    def __init__(self, stats: stats.Stats, name : str):
        self._name = name
        self._stats = stats
    
    async def value(self, key : str) -> stats.ValueType:
        return await self._stats.value(f"{self._name}/{key}")
    
    async def set(self, key : str, value : stats.ValueType) -> None:
        await self._stats.set(f"{self._name}/{key}", value)
    
    async def incr(self, key : str, value : int = 1) -> None:
        return await self._stats.incr(f"{self._name}/{key}", value)
    
    async def decr(self, key : str, value : int = 1) -> None:
        return await self._stats.decr(f"{self._name}/{key}", value)
    
    async def has(self, key : str) -> bool:
        return await self._stats.has(f"{self._name}/{key}")
    
    async def add(self, key : str, value : stats.ValueType) -> None:
        return await self._stats.add(f"{self._name}/{key}", value)
    
    async def remove(self, key : str, value : stats.ValueType) -> None:
        return await self._stats.remove(f"{self._name}/{key}", value)
    
    async def contains(self, key : str, value : stats.ValueType) -> bool:
        return await self._stats.contains(f"{self._name}/{key}", value)
    
    async def clear(self, key : str) -> None:
        return await self._stats.clear(f"{self._name}/{key}")
