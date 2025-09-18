import typing
import asyncio
import loader


class ProxyError(Exception):
    """在代理使用中抛出此异常，将导致当前代理被丢弃"""

    pass


class ProxyManager:
    def __init__(
        self,
        url: str,
        initial: list[str],
        retry_delay: float = 1.0,
        max_retries: int = 3,
        *args,
        **kwargs,
    ):
        self.renew_url = url
        self._proxies = list(initial)  # 可用代理池
        self._lock = asyncio.Lock()  # 并发锁
        self._in_use = set()  # 正在使用的代理
        self._has_proxies = asyncio.Event()  # 用于通知“现在有可用代理”
        self._waiters = 0  # 等待者计数（用于调试/限流）
        self._retry_delay = retry_delay
        self._max_retries = max_retries

        if self._proxies:
            self._has_proxies.set()

    async def renew(self) -> list[str]:
        """用户需实现此方法"""
        raise NotImplementedError("请实现 renew 方法")

    async def _wait_for_proxies(self, timeout: float = 30.0):
        """
        尝试获取代理，支持重试 + 超时
        """
        retries = 0
        while True:
            async with self._lock:
                # 检查是否有空闲代理
                available = [p for p in self._proxies if p not in self._in_use]
                if available:
                    proxy = available[0]
                    self._in_use.add(proxy)
                    return proxy

                # 无空闲 → 尝试 renew（仅限第一个等待者执行，避免并发 renew）
                if self._waiters == 0:
                    try:
                        new_proxies = await self.renew()
                        if new_proxies:
                            self._proxies.extend(new_proxies)
                            self._has_proxies.set()  # 通知其他等待者
                            # 立即从中分配一个
                            proxy = new_proxies[0]
                            self._in_use.add(proxy)
                            return proxy
                    except Exception as e:
                        # renew 失败，继续等待或重试
                        pass

            # 如果不是第一次，等待或重试
            if retries >= self._max_retries:
                break

            retries += 1

            # 等待“有代理”事件或超时
            try:
                await asyncio.wait_for(
                    self._has_proxies.wait(), timeout=self._retry_delay
                )
                # 被唤醒后，下一轮循环会重新检查代理
                continue
            except asyncio.TimeoutError:
                # 重试间隔到了，继续下一轮
                continue

        # 所有重试用尽，抛出超时异常
        raise asyncio.TimeoutError(
            f"等待代理超时（{timeout}s），renew 未能提供有效代理"
        )

    async def _acquire_proxy(self, timeout: float = 30.0) -> str:
        """获取一个可用代理，支持等待 + 超时"""
        try:
            async with self._lock:
                self._waiters += 1

            return await asyncio.wait_for(
                self._wait_for_proxies(timeout=timeout), timeout=timeout
            )
        finally:
            async with self._lock:
                self._waiters -= 1
                if self._waiters == 0:
                    self._has_proxies.clear()  # 没人等了，重置事件

    async def _release_proxy(self, proxy: str, discard: bool = False):
        """释放代理，discard=True 表示从池中移除"""
        async with self._lock:
            if discard and proxy in self._proxies:
                self._proxies.remove(proxy)
            self._in_use.discard(proxy)
            if self._proxies and not self._has_proxies.is_set():
                self._has_proxies.set()  # 通知等待者

    def __await__(self):
        raise TypeError("必须使用 'async with ProxyManager(...) as proxy'")

    async def __aenter__(self):
        proxy = await self._acquire_proxy()
        return ProxyContext(self, proxy)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass  # 由 ProxyContext 管理


class ProxyContext:
    def __init__(self, manager: ProxyManager, proxy: str):
        self.manager = manager
        self.proxy = proxy

    async def __aenter__(self) -> str:
        return self.proxy

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        discard = exc_type is not None and issubclass(exc_type, ProxyError)
        await self.manager._release_proxy(self.proxy, discard=discard)
        return False


class DummyProxyManager:
    """
    哑代理管理器，用于禁用代理的场景。
    兼容 ProxyManager 接口，但总是返回 None。
    """

    def __init__(self, *args, **kwargs):
        # 忽略所有参数，比如 renew_url, initial_proxies
        pass

    async def renew(self) -> list:
        """不执行任何操作，返回空列表"""
        return []

    async def __aenter__(self):
        # 返回一个哑上下文对象
        return DummyProxyContext()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # 无状态，无需清理
        pass


class DummyProxyContext:
    async def __aenter__(self) -> None:
        return None  # 重点：返回 None 表示“无代理”

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # 如果抛出了 ProxyError，我们忽略（兼容性）
        # 其他异常继续抛出
        if exc_type is not None and issubclass(exc_type, ProxyError):
            # 吞掉 ProxyError（因为没有代理可丢弃）
            return True  # 抑制异常
        return False  # 不抑制其他异常

    @property
    def proxy(self):
        return None


class ProxyFactory:
    def __init__(self, settings: dict[str, typing.Any]):
        self.settings = settings
        self.instance: dict[str, ProxyManager] = {}

    def create(self, name: str):
        if not name:
            return DummyProxyManager()

        if name in self.instance:
            return self.instance[name]

        manager: dict[str, typing.Any] = self.settings.get(name)
        if not manager:
            raise ValueError(f"未找到代理管理器 '{name}'")

        cls = manager.get("class")
        if not cls:
            raise ValueError(f"代理管理器 '{name}' 未指定 class")

        cls = loader.get_class(cls)
        if not cls:
            raise ValueError(f"代理管理器 '{name}' 未找到 class '{cls}'")

        self.instance[name] = cls(**manager)
        return self.instance[name]

    def __call__(self, name: str):
        return self.create(name)
