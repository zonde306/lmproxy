import typing
import asyncio
import logging
import collections
import loader
import rnet


class ProxyError(Exception):
    """在代理使用中抛出此异常，将导致当前代理被丢弃"""

    pass


class ProxyContext:
    def __init__(self, manager, proxy):
        self._manager = manager
        self.proxy = proxy

    async def __aenter__(self):
        return self.proxy

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        discard = exc_type is not None
        await self._manager._release_proxy(self.proxy, discard=discard)


class ProxyManager:
    def __init__(
        self,
        url: str,
        initial: list[str],
        repeat: int = 1,  # <--- 新增参数: 每个初始代理的重复次数
        timeout: float = 10.0,
        *args,
        **kwargs,
    ):
        self.renew_url = url

        if repeat < 1:
            raise ValueError("repeat 参数必须大于等于 1")

        # 将初始列表重复指定次数以创建最终的代理池
        effective_initial_pool = initial * repeat
        self._available_proxies = collections.deque(effective_initial_pool)
        # -----------------------

        self._condition = asyncio.Condition()
        self._is_renewing = False
        self._timeout = timeout

    async def renew(self) -> list[str]:
        if not self.renew_url:
            return []
        
        client = rnet.Client()
        async with client.get(self.renew_url) as response:
            assert isinstance(response, rnet.Response)
            content = await response.text()
            return content.split(self._separator)

    async def _get_or_wait_for_proxy(self) -> str:
        async with self._condition:
            while True:
                if self._available_proxies:
                    proxy = self._available_proxies.popleft()
                    return proxy
                if not self._is_renewing:
                    self._is_renewing = True
                    asyncio.create_task(self._renew_and_notify())
                await self._condition.wait()

    async def _renew_and_notify(self):
        try:
            new_proxies = await self.renew()
        except Exception:
            logging.error("Proxy renew failed", exc_info=True)
            new_proxies = []
        
        async with self._condition:
            if new_proxies:
                self._available_proxies.extend(new_proxies)
            self._is_renewing = False
            self._condition.notify_all()

    async def _release_proxy(self, proxy: str, discard: bool = False):
        async with self._condition:
            if not discard:
                self._available_proxies.append(proxy)
            if self._available_proxies:
                self._condition.notify()

    def __await__(self):
        raise TypeError("必须使用 'async with ProxyManager(...) as proxy'")

    async def __aenter__(self):
        try:
            proxy = await asyncio.wait_for(
                self._get_or_wait_for_proxy(), timeout=self._timeout
            )
            return ProxyContext(self, proxy)
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError(f"获取代理超时，超过 {self._timeout}s")

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


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
