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
            await self.middleware.process_request(ctx)

            async for attempt in self.retries(ctx):
                async with attempt:
                    logger.info(f"{task_id} start attempt {attempt.attempt_number} stream={ctx.body.get('stream', False)}")
                    response = await self._create_response(ctx, await callee(ctx))

                    await self.middleware.process_response(ctx)

                    if response:
                        return response

        except error.TerminationRequest as e:
            logger.info(f"{task_id} request terminated")
            return e.response

    async def _create_response(
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
                    self.concat_chunks(ctx, chunk)

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
    
    def concat_chunks(self, ctx: context.Context, chunk: context.DeltaType) -> context.DeltaType:
        if not chunk:
            return None
        
        if ctx.metadata.get("stream_content", None) is None:
            ctx.metadata["stream_content"] = chunk
            return chunk
        
        # 不考虑多个响应
        combined : context.DeltaType = ctx.metadata["stream_content"]

        if chunk["content"]:
            if combined.get("content", None) is None:
                combined["content"] = chunk["content"]
            else:
                combined["content"] += chunk["content"]
        
        if chunk["reasoning_content"]:
            if combined.get("reasoning_content", None) is None:
                combined["reasoning_content"] = chunk["reasoning_content"]
            else:
                combined["reasoning_content"] += chunk["reasoning_content"]
        
        if calls := chunk.get("tool_calls"):
            if combined.get("tool_calls", None) is None:
                combined["tool_calls"] = calls
            else:
                tool_calls = combined["tool_calls"]
                for call in calls:
                    index : int = call.get("index", 0)
                    if index >= len(tool_calls):
                        tool_calls.append(call)
                    elif tool_calls[index]["function"].get("arguments", None) is None:
                        tool_calls[index]["function"]["arguments"] = call["function"]["arguments"]
                    else:
                        # 只有 arguments 才会流式传输
                        tool_calls[index]["function"]["arguments"] += call["function"]["arguments"]
        
        return combined
