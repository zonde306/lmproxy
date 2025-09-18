import asyncio
from typing import List, Any, Optional


class ResourceManager:
    def __init__(self, resources: List[Any], default_timeout: Optional[float] = None):
        """
        初始化资源管理器

        Args:
            resources: 资源列表
            default_timeout: 默认超时时间（秒），None 表示无限等待
        """
        if not resources:
            raise ValueError("资源列表不能为空")
        self._resources = list(resources)  # 复制一份，避免外部修改
        self._available = set(range(len(self._resources)))  # 可用资源索引集合
        self._condition = asyncio.Condition()
        self._lock = asyncio.Lock()  # 保护共享状态
        self._default_timeout = default_timeout

    def get(self, timeout: Optional[float] = None):
        """
        获取资源锁

        Args:
            timeout: 超时时间（秒），None 表示使用默认超时时间

        Returns:
            ResourceLock: 异步上下文管理器
        """
        # 如果未指定 timeout，则使用默认超时时间
        effective_timeout = timeout if timeout is not None else self._default_timeout
        return ResourceLock(self, effective_timeout)

    def _get_resource(self) -> Any:
        """内部方法：取出一个可用资源"""
        if not self._available:
            return None
        idx = self._available.pop()
        return self._resources[idx]

    def _release_resource(self, resource: Any) -> bool:
        """内部方法：释放资源"""
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
            if self._available:
                return self._get_resource()

            # 无可用资源，等待通知
            async with self._condition:
                try:
                    if timeout is None:
                        await self._condition.wait()
                    else:
                        await asyncio.wait_for(self._condition.wait(), timeout)
                except asyncio.TimeoutError:
                    return None  # 超时返回 None

                # 被唤醒后再次检查
                if self._available:
                    return self._get_resource()
                else:
                    return None  # 仍无资源，返回 None

    async def _release_and_notify(self, resource: Any):
        """释放资源并通知等待者"""
        async with self._lock:
            if self._release_resource(resource):
                async with self._condition:
                    self._condition.notify(1)  # 通知一个等待者


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
