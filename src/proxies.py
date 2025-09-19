import typing
import asyncio
import loader
import rnet


class ProxyError(Exception):
    """在代理使用中抛出此异常，将导致当前代理被丢弃"""

    pass


class ProxyManager:
    def __init__(
        self,
        url: str,
        initial: list[str],
        # 注意：这里我们定义一个总的获取超时，而不是重试延迟
        timeout: float = 10.0,
        separator: str = "\n",
        repeat: int = 1,
        *args,
        **kwargs,
    ):
        self.renew_url = url
        self._repeat = repeat
        self._proxies : list[str] = list(initial) * repeat  # 可用代理池
        self._in_use = set()  # 正在使用的代理
        # 使用 Condition 替代 Lock + Event
        self._condition = asyncio.Condition()
        self._is_renewing = False  # 防止并发 renew 的标志
        self._timeout = timeout
        self._separator = separator

    async def renew(self) -> list[str]:
        if not self.renew_url:
            return []
        
        client = rnet.Client()
        async with client.get(self.renew_url) as response:
            assert isinstance(response, rnet.Response)
            content = await response.text()
            return content.split(self._separator)

    async def _get_or_wait_for_proxy(self) -> str:
        """
        在 Condition 保护下获取代理或等待。
        此方法会被 asyncio.wait_for 包装以实现超时。
        """
        async with self._condition:
            while True:
                # 1. 检查是否有可用代理
                available = [p for p in self._proxies if p not in self._in_use]
                if available:
                    proxy = available[0]
                    self._in_use.add(proxy)
                    return proxy

                # 2. 没有可用代理，且没有其他任务正在 renew，则由我来 renew
                if not self._is_renewing:
                    self._is_renewing = True
                    # 在锁外执行 I/O 操作 (renew)
                    # asyncio.create_task 立即返回，不阻塞当前循环
                    asyncio.create_task(self._renew_and_notify())

                # 3. 等待通知 (代理被释放或 renew 完成)
                # self._condition.wait() 会临时释放锁，直到被 notify
                await self._condition.wait()

    async def _renew_and_notify(self):
        """在后台执行 renew 操作并通知所有等待者。"""
        try:
            new_proxies = await self.renew()
        except Exception as e:
            print(f"Renew failed: {e}")
            new_proxies = []

        async with self._condition:
            if new_proxies:
                self._proxies.extend(new_proxies * self._repeat)
            self._is_renewing = False  # 重置标志
            self._condition.notify_all()  # 唤醒所有等待的任务

    async def _release_proxy(self, proxy: str, discard: bool = False):
        """释放代理，并通知一个等待者。"""
        async with self._condition:
            if discard and proxy in self._proxies:
                self._proxies.remove(proxy)
            self._in_use.discard(proxy)
            # 通知一个等待的任务，可能有代理可用了
            self._condition.notify()

    def __await__(self):
        raise TypeError("必须使用 'async with ProxyManager(...) as proxy'")

    async def __aenter__(self):
        try:
            proxy = await asyncio.wait_for(
                self._get_or_wait_for_proxy(), timeout=self._timeout
            )
            # 返回一个上下文管理器，它将在退出时自动释放代理
            return ProxyContext(self, proxy)
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError(
                f"获取代理超时，超过 {self._timeout}s"
            )

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # __aenter__ 返回的 ProxyContext 对象会处理代理的释放
        # 所以这里不需要做任何事
        pass


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
