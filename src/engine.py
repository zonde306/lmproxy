import typing
import uuid
import inspect
import logging
import context
import retry
import middleware
import worker
import proxies
import error

logger = logging.getLogger(__name__)


class Engine:
    def __init__(self, settings: dict[str, typing.Any]):
        self.settings = settings
        self.middleware = middleware.MiddlewareManager(settings.get("middleware", {}), self)
        self.retries = retry.RetryFactory(settings.get("retry", {}), self.middleware)
        self.proxies = proxies.ProxyFactory(settings.get("proxy", {}))
        self.workers = worker.WorkerManager(settings.get("worker", {}), self.proxies)

    async def models(self) -> list[str]:
        return await self.workers.models()

    async def generate_text(
        self, body: dict[str, typing.Any], headers: dict[str, str]
    ) -> context.Response:
        return await self.process_generate(
            context.Context(body=body, headers=headers, type="text"),
            self.workers.generate_text,
        )

    async def generate_image(
        self, body: dict[str, typing.Any], headers: dict[str, str]
    ) -> context.Response:
        return await self.process_generate(
            context.Context(body=body, headers=headers, type="image"),
            self.workers.generate_image,
        )

    async def generate_audio(
        self, body: dict[str, typing.Any], headers: dict[str, str]
    ) -> context.Response:
        return await self.process_generate(
            context.Context(body=body, headers=headers, type="audio"),
            self.workers.generate_audio,
        )

    async def generate_embedding(
        self, body: dict[str, typing.Any], headers: dict[str, str]
    ) -> context.Response:
        return await self.process_generate(
            context.Context(body=body, headers=headers, type="embedding"),
            self.workers.generate_embedding,
        )

    async def generate_video(
        self, body: dict[str, typing.Any], headers: dict[str, str]
    ) -> context.Response:
        return await self.process_generate(
            context.Context(body=body, headers=headers, type="video"),
            self.workers.generate_video,
        )

    async def count_tokens(
        self, body: dict[str, typing.Any], headers: dict[str, str]
    ) -> context.Response:
        return await self.workers.count_tokens(
            context.Context(body=body, headers=headers, type="count_tokens")
        )

    async def process_generate(
        self,
        ctx: context.Context,
        callee: typing.Callable[[context.Context], typing.Any],
    ) -> context.Response:
        task_id = ctx.metadata["task_id"] = uuid.uuid4().hex

        try:
            if not await self.middleware.process_request(ctx):
                logger.info(f"{task_id} request cancelled")
                return ctx.to_response

            async for attempt in self.retries(ctx):
                async with attempt:
                    logger.info(f"{task_id} start attempt {attempt.attempt_number}")
                    response = await self._to_response(ctx, await callee(ctx))

                    if not await self.middleware.process_response(ctx):
                        logger.info(f"{task_id} response cancelled")
                        return ctx.to_response

                    if response:
                        return response

        except error.TerminationRequest as e:
            logger.info(f"{task_id} request terminated")
            return e.response

    async def _to_response(
        self,
        ctx: context.Context,
        result: context.DeltaType | typing.AsyncGenerator[context.DeltaType, None],
    ) -> context.Response | None:
        if inspect.isasyncgen(result):
            ctx.response = await self._stream_warpper(ctx, result)
            return ctx.to_response
        elif isinstance(result, (str, bytes, list, int, dict)):
            ctx.response = result
            return ctx.to_response

        return None

    async def _stream_warpper(
        self,
        ctx: context.Context,
        streamer: typing.AsyncGenerator[context.DeltaType, None]
    ) -> typing.AsyncGenerator[context.DeltaType, None]:
        async def generate():
            async for chunk in streamer:
                if chunk["type"] == "text":
                    if ctx.metadata("stream_content", None) is None:
                        ctx.metadata["stream_content"] = ""
                    if ctx.metadata("stream_reasoning", None) is None:
                        ctx.metadata["stream_reasoning"] = ""
                    
                    ctx.metadata["stream_content"] += chunk["content"] if chunk["content"] else ""
                    ctx.metadata["stream_reasoning"] += chunk["reasoning"] if chunk["reasoning"] else ""

                try:
                    if not await self.middleware.process_chunk(ctx, chunk):
                        logger.info(f"{ctx.task_id} chunk blocked")
                        continue
                except error.TerminationRequest as e:
                    logger.info(f"{ctx.task_id} request terminated")
                    if inspect.isasyncgen(e.response.body):
                        async for delta in e.response.body:
                            yield delta
                    else:
                        logger.error(
                            f"TerminationRequest {ctx.task_id} response is not a stream",
                            exc_info=True,
                            extra={"response": e.response, "context": ctx}
                        )
                        raise RuntimeError(f"TerminationRequest {ctx.task_id} response is not a stream") from e
                    
                    break
                
                yield chunk
        
        return generate()
