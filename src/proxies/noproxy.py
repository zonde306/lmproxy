from ..schemas import proxies
from ..schemas import request

class NoProxy(proxies.Proxies):
    async def next(self, request: request.Request) -> proxies.Proxy | None:
        return None
