import typing
import context
import loader

class Middleware:
    def __init__(self, settings: dict[str, typing.Any]) -> None:
        self.settings = settings

    async def process_request(self, ctx: context.Context) -> bool | None:
        """
        返回 False 以停止后续处理并立即返回
        """
        ...
    
    async def process_response(self, ctx: context.Context) -> bool | None:
        """
        返回 False 以停止后续处理并立即返回
        """
        ...
    
    async def process_error(self, ctx: context.Context, error: Exception, attempt: int) -> bool | None:
        """
        返回 True 以吞掉异常
        """
        ...

class MiddlewareManager(Middleware):
    def __init__(self, settings: dict[str, typing.Any]) -> None:
        self.settings = settings
        self.middlewares: list[Middleware] = []
        self._setup_middlewares()
    
    def add_middleware(self, middleware: Middleware) -> None:
        self.middlewares.append(middleware)
    
    def _setup_middlewares(self) -> None:
        middlewares = []
        for middleware in self.settings.get("middlewares", []):
            if isinstance(middleware, str):
                if middleware := loader.get_class(middleware):
                    middlewares.append([100, middleware()])
            elif isinstance(middleware, dict):
                if cls := middleware.get("class"):
                    priority = middleware.get("priority", 100)
                    middlewares.append([priority, cls(middleware)])
        
        middlewares.sort(key=lambda x: x[0], reverse=True)
        self.middlewares = [middleware[1] for middleware in middlewares]
    
    async def process_request(self, ctx: context.Context) -> bool | None:
        for middleware in self.middlewares:
            if (await middleware.process_request(ctx)) is False:
                return False
        return True
    
    async def process_response(self, ctx: context.Context) -> bool | None:
        for middleware in self.middlewares:
            if (await middleware.process_response(ctx)) is False:
                return False
        return True
    
    async def process_error(self, ctx: context.Context, error: Exception, attempt: int) -> bool | None:
        for middleware in self.middlewares:
            if await middleware.process_error(ctx, error, attempt):
                return False
        return True
