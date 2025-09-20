import asyncio
from typing import List, Any, Optional

class ResourceManager:
    def __init__(self, resources: List[Any], 
                 cooldown_time: float = 0,
                 default_timeout: Optional[float] = None):
        """
        初始化资源管理器
        
        Args:
            resources: 资源列表
            cooldown_time: 资源使用后释放的冷却时间（秒）。默认为0，表示无冷却。
            default_timeout: 默认获取资源的超时时间（秒），None 表示无限等待
        """
        if not resources:
            raise ValueError("资源列表不能为空")
        self._resources = list(resources)  # 复制一份，避免外部修改
        self._available = set(range(len(self._resources)))  # 可用资源索引集合
        self._condition = asyncio.Condition()
        self._lock = asyncio.Lock()  # 保护共享状态
        self._default_timeout = default_timeout
        self._cooldown_time = cooldown_time  # 新增：冷却时间
        self._next_index = 0  # 轮询指针，记录下一次从哪个位置开始查找

    def get(self, timeout: Optional[float] = None):
        """
        获取资源锁
        
        Args:
            timeout: 超时时间（秒），None 表示使用默认超时时间
            
        Returns:
            ResourceLock: 异步上下文管理器
        """
        effective_timeout = timeout if timeout is not None else self._default_timeout
        return ResourceLock(self, effective_timeout)

    def _get_resource_round_robin(self) -> Any:
        """内部方法：按轮询方式取出一个可用资源"""
        if not self._available:
            return None
        
        n = len(self._resources)
        start_index = self._next_index
        
        for i in range(n):
            current_index = (start_index + i) % n
            if current_index in self._available:
                self._available.remove(current_index)
                self._next_index = (current_index + 1) % n
                return self._resources[current_index]
        
        return None

    def _release_resource(self, resource: Any) -> bool:
        """内部方法：释放资源，将其索引加入可用集合"""
        try:
            idx = self._resources.index(resource)
            if idx not in self._available:
                self._available.add(idx)
                return True
        except ValueError:
            pass
        return False

    async def _acquire_resource(self, timeout: Optional[float] = None) -> Any:
        """异步获取一个资源，支持超时"""
        async with self._lock:
            while True: # 使用 while 循环以防止虚假唤醒
                resource = self._get_resource_round_robin()
                if resource is not None:
                    return resource

                # 无可用资源，等待通知
                async with self._condition:
                    try:
                        if timeout is None:
                            await self._condition.wait()
                        else:
                            await asyncio.wait_for(self._condition.wait(), timeout)
                    except asyncio.TimeoutError:
                        # 再次检查，因为可能在超时和捕获异常之间资源变为可用
                        resource = self._get_resource_round_robin()
                        return resource # 如果仍然没有，返回 None

    async def _release_and_notify(self, resource: Any):
        """
        释放资源并通知等待者。
        如果设置了冷却时间，则启动一个后台任务来处理冷却。
        """
        if self._cooldown_time > 0:
            # 启动一个后台任务，在冷却后释放资源，不会阻塞当前协程
            asyncio.create_task(self._cooldown_and_release(resource))
        else:
            # 无冷却，立即释放并通知
            async with self._lock:
                if self._release_resource(resource):
                    async with self._condition:
                        self._condition.notify(1)

    async def _cooldown_and_release(self, resource: Any):
        """
        【新增】等待冷却时间，然后将资源放回池中并通知等待者。
        这是一个在后台运行的协程。
        """
        await asyncio.sleep(self._cooldown_time)
        async with self._lock:
            if self._release_resource(resource):
                # 冷却结束，资源现在可用
                async with self._condition:
                    self._condition.notify(1)


class ResourceLock:
    def __init__(self, manager: ResourceManager, timeout: Optional[float] = None):
        self._manager = manager
        self._timeout = timeout
        self._resource = None

    async def __aenter__(self):
        self._resource = await self._manager._acquire_resource(self._timeout)
        if self._resource is None:
            raise asyncio.TimeoutError("获取资源超时")
        return self._resource

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._resource is not None:
            await self._manager._release_and_notify(self._resource)
            self._resource = None
