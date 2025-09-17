import typing
import uuid
import inspect
import context
import retry
import middlewares
import worker
import proxies

class Router:
    def __init__(self, settings: dict[str, typing.Any]):
        self.settings = settings
        self.middleware = middlewares.MiddlewareManager(settings.get("middleware", {}))
        self.retry = retry.RetryFactory(settings.get("retry", {}), self.middleware)
        self.proxies = proxies.ProxyFactory(settings.get("proxies", {}))
        self.worker = worker.WorkerManager(settings.get("workers", {}))
    
    async def generate_text(self, body: dict[str, typing.Any], headers: dict[str, str]) -> context.Response:
        return await self._process(
            context.Context(body=body, headers=headers, type="text"), 
            self.worker.generate_text,
        )
    
    async def generate_image(self, body: dict[str, typing.Any], headers: dict[str, str]) -> context.Response:
        return await self._process(
            context.Context(body=body, headers=headers, type="image"), 
            self.worker.generate_image,
        )
    
    async def generate_audio(self, body: dict[str, typing.Any], headers: dict[str, str]) -> context.Response:
        return await self._process(
            context.Context(body=body, headers=headers, type="audio"), 
            self.worker.generate_audio,
        )
    
    async def generate_embedding(self, body: dict[str, typing.Any], headers: dict[str, str]) -> context.Response:
        return await self._process(
            context.Context(body=body, headers=headers, type="embedding"), 
            self.worker.generate_embedding,
        )

    async def _process(self, ctx: context.Context, callee: typing.Callable[[context.Context], typing.Any]) -> context.Response:
        ctx.metadata["task_id"] = uuid.uuid4().hex
        
        if not await self.middleware.process_request(ctx):
            return context.Response(
                status_code=200,
                headers=ctx.response_headers,
                body=ctx.response,
            )
        
        async for attempt in self.retry(ctx):
            with attempt:
                response = await self._to_response(ctx, await callee(ctx))
                
                if not await self.middleware.process_response(ctx):
                    return context.Response(
                        status_code=200,
                        headers=ctx.response_headers,
                        body=ctx.response,
                    )

                if response:
                    return response
    
    async def _to_response(self, ctx : context.Context, result: typing.Any) -> context.Response | None:
        if isinstance(result, (str, bytes, list, int)) or inspect.isasyncgen(result):
            ctx.response = result
            return context.Response(
                status_code=200,
                headers=ctx.response_headers,
                body=result,
            )
        
        return None
