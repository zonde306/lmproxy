import asyncio
from typing import List, Any, Optional, AsyncIterator, Type, Tuple

class NoMoreResourceError(Exception):
    ...

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
        self._resources = list(resources)
        self._available = set(range(len(self._resources)))
        self._condition = asyncio.Condition()
        self._lock = asyncio.Lock()
        self._default_timeout = default_timeout
        self._cooldown_time = cooldown_time
        self._next_index = 0

    async def get_retying(
        self,
        stop: int = 3, 
        wait: float = 1.5, 
        exceptions: List[Type[BaseException]] | tuple[Type[BaseException]] = [ Exception ], 
        timeout: Optional[float] = None
    ) -> AsyncIterator['RetryAttemptContext']:
        """
        获取资源锁，支持对特定异常进行重试。
        每次重试都会尝试获取一个与之前尝试不同的资源。

        Args:
            stop: 最大尝试次数。
            wait: 每次失败重试前的等待时间（秒）。
            exceptions: 一个异常类型列表。当 `with` 块内抛出这些类型的异常时，才会触发重试。
                        如果抛出其他异常，重试将中止，异常会向外传播。默认为 [Exception]，即对所有标准异常重试。
            timeout: 获取每个资源的超时时间（秒）。None 表示使用默认超时。

        Yields:
            一个内部的异步上下文管理器，用于当前尝试。

        Raises:
            NoMoreResourceError: 如果所有资源都已尝试过，或者在等待新资源时超时，或者所有尝试都因可重试异常而失败。
            Any: 如果在 `with` 块内发生了不在 `exceptions` 列表中的异常，该异常将被重新抛出。

        Examples:
            ```python
            # 只在 ValueError 时重试
            async for attempt in rm.get_retying(exceptions=[ValueError]):
                async with attempt as resource:
                    if resource == "res1":
                        raise ValueError("Simulated failure") # 会触发重试
                    if resource == "res2":
                        raise TypeError("Fatal error") # 不会重试，直接抛出
                    print(f"Success with {resource}")
            ```
        """
        if stop <= 0:
            return

        effective_timeout = timeout if timeout is not None else self._default_timeout
        retryable_exceptions_tuple = tuple(exceptions)
        tried_indices = set()
        last_exception = None

        for attempt_num in range(stop):
            if attempt_num > 0 and wait > 0:
                await asyncio.sleep(wait)

            resource, index = await self._acquire_new_untried_resource(tried_indices, effective_timeout)
            tried_indices.add(index)
            
            attempt_context = RetryAttemptContext(self, resource, retryable_exceptions_tuple)
            
            yield attempt_context
            
            # --- with 块执行完毕，代码从这里恢复 ---

            if attempt_context.succeeded:
                # 成功了，直接结束生成器
                return
            
            # 如果没成功，记录下最后一次的异常
            last_exception = attempt_context.exception

        # 如果循环正常结束（即所有尝试都失败了），则抛出最终错误
        raise NoMoreResourceError(f"All {stop} attempts failed.") from last_exception

    async def _acquire_new_untried_resource(self, tried_indices: set, timeout: Optional[float]) -> Tuple[Any, int]:
        """内部方法：获取一个尚未尝试过的可用资源"""
        async with self._lock:
            while True:
                # 1. 寻找一个可用的、新的资源
                n = len(self._resources)
                start_search = self._next_index
                found_index = -1
                for i in range(n):
                    idx = (start_search + i) % n
                    if idx in self._available and idx not in tried_indices:
                        found_index = idx
                        break
                
                if found_index != -1:
                    # 2. 找到了，获取它
                    self._available.remove(found_index)
                    self._next_index = (found_index + 1) % n
                    return self._resources[found_index], found_index

                # 3. 如果没找到，检查是否所有资源都试过了
                if len(tried_indices) == len(self._resources):
                    raise NoMoreResourceError("All available resources have been tried.")
                    
                # 4. 如果还有未尝试的资源但它们当前都不可用，则等待
                async with self._condition:
                    try:
                        await asyncio.wait_for(self._condition.wait(), timeout)
                    except asyncio.TimeoutError:
                        raise NoMoreResourceError(f"Timed out after {timeout}s waiting for a new resource.") from None

    # ... (其他方法 _get_resource_round_robin, _release_resource 等保持不变)
    def get(self, timeout: Optional[float] = None):
        effective_timeout = timeout if timeout is not None else self._default_timeout
        return ResourceLock(self, effective_timeout)

    def _get_resource_round_robin(self) -> Any:
        if not self._available: return None
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
        try:
            idx = self._resources.index(resource)
            if idx not in self._available:
                self._available.add(idx)
                return True
        except ValueError:
            pass
        return False

    async def _acquire_resource(self, timeout: Optional[float] = None) -> Any:
        async with self._lock:
            while True:
                resource = self._get_resource_round_robin()
                if resource is not None:
                    return resource
                async with self._condition:
                    try:
                        await asyncio.wait_for(self._condition.wait(), timeout)
                    except asyncio.TimeoutError:
                        resource = self._get_resource_round_robin()
                        return resource

    async def _release_and_notify(self, resource: Any):
        if self._cooldown_time > 0:
            asyncio.create_task(self._cooldown_and_release(resource))
        else:
            async with self._lock:
                if self._release_resource(resource):
                    async with self._condition:
                        self._condition.notify(1)

    async def _cooldown_and_release(self, resource: Any):
        await asyncio.sleep(self._cooldown_time)
        async with self._lock:
            if self._release_resource(resource):
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


class RetryAttemptContext:
    """
    一个内部上下文管理器，用于处理单次重试。
    它的 __aexit__ 方法包含了决定是否继续重试的关键逻辑。
    """
    def __init__(self, manager: 'ResourceManager', resource: Any, retryable_exceptions: Tuple[Type[BaseException], ...]):
        self._manager = manager
        self._resource = resource
        self._retryable_exceptions = retryable_exceptions
        
        # 状态标志
        self.succeeded = False
        self.exception: Optional[BaseException] = None

    async def __aenter__(self):
        return self._resource

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # 必须先释放资源，无论成功与否
        if self._resource is not None:
            await self._manager._release_and_notify(self._resource)

        if exc_type is None:
            self.succeeded = True
            return False # 没有异常，正常退出，不抑制

        self.exception = exc_val
        # 检查发生的异常是否是可重试的类型
        if issubclass(exc_type, self._retryable_exceptions):
            # 是可重试异常，抑制它，以便 for 循环可以继续
            return True
        
        # 不是可重试异常，不抑制它，让它传播出去
        return False
