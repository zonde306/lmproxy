import typing
import logging
import context
import loader

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    import engine

class Middleware:
    def __init__(self, settings: dict[str, typing.Any], engine: "engine.Engine") -> None:
        self.settings = settings
        self.engine = engine

    async def process_request(self, ctx: context.Context) -> typing.Literal[False] | None:
        """
        返回 False 以停止后续中间件处理
        """
        ...

    async def process_response(self, ctx: context.Context) -> typing.Literal[False] | None:
        """
        返回 False 以停止后续中间件处理
        """
        ...
    
    async def process_chunk(self, ctx: context.Context, chunk: context.DeltaType) -> typing.Literal[False] | None:
        """
        返回 False 以阻止响应
        """
        ...

    async def process_error(
        self, ctx: context.Context, error: Exception, attempt: int
    ) -> typing.Literal[True] | None:
        """
        返回 True 阻断异常传播
        """
        ...

    def __str__(self):
        return f"Middleware({self.settings.get('name', self.__class__.__name__)})"

    def __repr__(self):
        return f"Middleware({self.settings.get('name', self.__class__.__name__)})"


class MiddlewareManager:
    def __init__(self, settings: dict[str, typing.Any], engine: "engine.Engine") -> None:
        self.settings = settings
        self.middlewares: list[Middleware] = []
        self._engine = engine
        self._setup_middlewares()

    def add_middleware(self, middleware: Middleware) -> None:
        self.middlewares.append(middleware)

    def _setup_middlewares(self) -> None:
        middlewares = []
        for middleware in self.settings.get("middlewares", []):
            if isinstance(middleware, str):
                if cls := loader.get_object(middleware):
                    middlewares.append([100, cls({}, self._engine)])
                else:
                    logger.error(f"middleware {middleware} not found")
            elif isinstance(middleware, dict):
                if cls := loader.get_object(middleware.get("class", "")):
                    priority = middleware.get("priority", 100)
                    middlewares.append([priority, cls(middleware, self._engine)])
                else:
                    logger.error(f"middleware {middleware} not found")

        middlewares.sort(key=lambda x: x[0], reverse=True)
        self.middlewares = [middleware[1] for middleware in middlewares]
        logger.info(f"middlewares: {self.middlewares}")

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
    
    async def process_chunk(self, ctx: context.Context, chunk: context.DeltaType) -> bool | None:
        for middleware in self.middlewares:
            if (await middleware.process_chunk(ctx, chunk)) is False:
                return False
        return True

    async def process_error(
        self, ctx: context.Context, error: Exception, attempt: int
    ) -> bool | None:
        for middleware in self.middlewares:
            if await middleware.process_error(ctx, error, attempt):
                return False
        return True
