from ..schemas import proxy
from ..schemas import request

class NoProxy(proxy.Proxies):
    async def next(self, request: request.Request) -> proxy.Proxy | None:
        return None
