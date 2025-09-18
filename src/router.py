import typing
import uuid
import inspect
import context
import retry
import middleware
import worker
import proxies
import error


class Router:
    def __init__(self, settings: dict[str, typing.Any]):
        self.settings = settings
        self.middleware = middleware.MiddlewareManager(settings.get("middleware", {}))
        self.retries = retry.RetryFactory(settings.get("retry", {}), self.middleware)
        self.proxies = proxies.ProxyFactory(settings.get("proxy", {}))
        self.workers = worker.WorkerManager(settings.get("worker", {}), self.proxies)

    async def models(self) -> list[str]:
        return await self.workers.models()

    async def generate_text(
        self, body: dict[str, typing.Any], headers: dict[str, str]
    ) -> context.Response:
        return await self._process(
            context.Context(body=body, headers=headers, type="text"),
            self.workers.generate_text,
        )

    async def generate_image(
        self, body: dict[str, typing.Any], headers: dict[str, str]
    ) -> context.Response:
        return await self._process(
            context.Context(body=body, headers=headers, type="image"),
            self.workers.generate_image,
        )

    async def generate_audio(
        self, body: dict[str, typing.Any], headers: dict[str, str]
    ) -> context.Response:
        return await self._process(
            context.Context(body=body, headers=headers, type="audio"),
            self.workers.generate_audio,
        )

    async def generate_embedding(
        self, body: dict[str, typing.Any], headers: dict[str, str]
    ) -> context.Response:
        return await self._process(
            context.Context(body=body, headers=headers, type="embedding"),
            self.workers.generate_embedding,
        )

    async def generate_video(
        self, body: dict[str, typing.Any], headers: dict[str, str]
    ) -> context.Response:
        return await self._process(
            context.Context(body=body, headers=headers, type="video"),
            self.workers.generate_video,
        )

    async def count_tokens(
        self, body: dict[str, typing.Any], headers: dict[str, str]
    ) -> context.Response:
        return await self.workers.count_tokens(
            context.Context(body=body, headers=headers, type="count_tokens")
        )

    async def _process(
        self,
        ctx: context.Context,
        callee: typing.Callable[[context.Context], typing.Any],
    ) -> context.Response:
        ctx.metadata["task_id"] = uuid.uuid4().hex

        try:
            if not await self.middleware.process_request(ctx):
                return context.Response(
                    status_code=200,
                    headers=ctx.response_headers,
                    body=ctx.response,
                )

            async for attempt in self.retries(ctx):
                async with attempt:
                    response = await self._to_response(ctx, await callee(ctx))

                    if not await self.middleware.process_response(ctx):
                        return context.Response(
                            status_code=200,
                            headers=ctx.response_headers,
                            body=ctx.response,
                        )

                    if response:
                        return response
        except error.TerminationRequest as e:
            return e.response

    async def _to_response(
        self, ctx: context.Context, result: typing.Any
    ) -> context.Response | None:
        if isinstance(result, (str, bytes, list, int, dict)) or inspect.isasyncgen(
            result
        ):
            ctx.response = result
            return context.Response(
                status_code=200,
                headers=ctx.response_headers,
                body=result,
            )

        return None
