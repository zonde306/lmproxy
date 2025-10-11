import typing
import inspect
import asyncio
import logging
import itertools
import contextlib
import context
import loader
import error
import cache
import proxies
import http_client
import rnet

logger = logging.getLogger(__name__)

class Worker:
    def __init__(
        self,
        settings: dict[str, typing.Any],
        proxies: proxies.ProxyFactory
    ) -> None:
        self.settings = settings
        self._proxies = proxies
        self.available_models: list[str] = settings.get("models", [])
        self.aliases: dict[str, str] = settings.get("aliases", {})
        self.client_args: http_client.ClientOptions = {}
        self.name : str = settings.get("name", self.__class__.__name__)

        # 初始列表总是允许
        self._initial_available_models = set(self.available_models)

    async def models(self) -> list[str]:
        # 有序列表
        return self.available_models
    
    async def supports_model(self, model: str, type: typing.Literal["text", "image", "audio", "embedding", "video"]) -> bool:
        return model in self._initial_available_models or model in self.available_models

    async def generate_text(self, context: context.Context) -> context.Text:
        raise NotImplementedError

    async def generate_image(self, context: context.Context) -> context.Image:
        raise NotImplementedError

    async def generate_audio(self, context: context.Context) -> context.Audio:
        raise NotImplementedError

    async def generate_embedding(self, context: context.Context) -> context.Embedding:
        raise NotImplementedError

    async def generate_video(self, context: context.Context) -> context.Video:
        raise NotImplementedError

    async def count_tokens(self, context: context.Context) -> context.CountTokens:
        raise NotImplementedError

    @property
    def proxies(self):
        return self._proxies(self.settings.get("proxy", None))
    
    async def _client_created(self, client: rnet.Client):
        ...

    @contextlib.asynccontextmanager
    async def client(self) -> typing.AsyncGenerator[rnet.Client, None]:
        async with self.proxies as proxies:
            async with proxies as proxy:
                args = dict(
                    proxies=[rnet.Proxy.all(proxy)] if proxy else None,
                    impersonate=rnet.Impersonate.Firefox139,
                    cookie_store=True,
                    allow_redirects=True,
                    max_redirects=9,
                )
                args.update(self.client_args)
                client = rnet.Client(**args)
                await self._client_created(client)
                yield client
    
    def __str__(self):
        return f"Worker({self.name})"
    
    def __repr__(self):
        return f"Worker({self.name})"


class WorkerManager:
    def __init__(
        self,
        settings: dict[str, typing.Any],
        proxies: proxies.ProxyFactory
    ) -> None:
        self.settings = settings
        self.workers: list[Worker] = []
        self._setup_workers(proxies)

    def add_worker(self, worker: Worker) -> None:
        self.workers.append(worker)

    def _setup_workers(self, proxies: proxies.ProxyFactory) -> None:
        workers = []
        for worker in self.settings.get("workers", []):
            if isinstance(worker, str):
                if cls := loader.get_class(worker):
                    workers.append([100, cls({}, proxies)])
            elif isinstance(worker, dict):
                if cls := loader.get_class(worker.get("class")):
                    priority = worker.get("priority", 100)
                    workers.append([priority, cls(worker, proxies)])

        workers.sort(key=lambda x: x[0], reverse=True)
        self.workers = [worker[1] for worker in workers]
        logger.info(f"workers: {self.workers}")

    @cache.ttl_cache(300)
    async def models(self) -> list[str]:
        models = await asyncio.gather(*[ x.models() for x in self.workers ])
        [
            (x.available_models.clear(), x.available_models.extend(models[i]))
            for i, x in enumerate(self.workers)
        ]
        avaliable_models = sorted(set(itertools.chain.from_iterable(models)), key=lambda x: x.lower())
        logger.info(f"available models: { { x.name: x.available_models for x in self.workers } }")
        return avaliable_models

    async def generate_text(self, ctx: context.Context) -> context.Text:
        # 必须使用函数，否则会发生错误
        async def generate():
            for worker in self.workers:
                with error.worker_handler(ctx, logger, worker):
                    if not await worker.supports_model(ctx.model, "text"):
                        continue

                    logger.debug(f"worker: {worker}, model: {ctx.model}, type: text")
                    result = await worker.generate_text(ctx)

                    # 非流式未发生异常直接返回
                    if not inspect.isasyncgen(result):
                        ctx.metadata["worker"] = worker.name
                        return result
                    
                    # 等待第一个结果或者异常
                    first_chunk = await anext(result, None)  # noqa: F821

                    # 流式开始时未发生异常
                    async def continue_generate():
                        if first_chunk is not None:
                            yield first_chunk

                            # 因为已经发送了第一个块，所以之后的异常由外部处理
                            async for chunk in result:
                                yield chunk
                    
                    ctx.metadata["worker"] = worker.name
                    return continue_generate()

            raise error.WorkerError(f"No avaliable workers for {ctx.model}")
        
        return await generate()

    async def generate_image(self, ctx: context.Context) -> context.Image:
        for worker in self.workers:
            with error.worker_handler(ctx, logger, worker):
                if not await worker.supports_model(ctx.model, "text"):
                    continue
                
                logger.debug(f"model: {ctx.model}, worker: {worker}, type: image")
                return await worker.generate_image(ctx)

        raise error.WorkerError("No avaliable workers")

    async def generate_audio(self, ctx: context.Context) -> context.Audio:
        for worker in self.workers:
            with error.worker_handler(ctx, logger, worker):
                if not await worker.supports_model(ctx.model, "text"):
                    continue

                logger.debug(f"model: {ctx.model}, worker: {worker}, type: audio")
                return await worker.generate_audio(ctx)

        raise error.WorkerError("No avaliable workers")

    async def generate_embedding(self, ctx: context.Context) -> context.Embedding:
        for worker in self.workers:
            with error.worker_handler(ctx, logger, worker):
                if not await worker.supports_model(ctx.model, "text"):
                    continue

                logger.debug(f"model: {ctx.model}, worker: {worker}, type: embedding")
                return await worker.generate_embedding(ctx)

        raise error.WorkerError("No avaliable workers")

    async def generate_video(self, ctx: context.Context) -> context.Video:
        for worker in self.workers:
            with error.worker_handler(ctx, logger, worker):
                if not await worker.supports_model(ctx.model, "text"):
                    continue

                logger.debug(f"model: {ctx.model}, worker: {worker}, type: video")
                return await worker.generate_video(ctx)

        raise error.WorkerError("No avaliable workers")

    async def count_tokens(self, ctx: context.Context) -> context.CountTokens:
        for worker in self.workers:
            with error.worker_handler(ctx, logger, worker):
                if not await worker.supports_model(ctx.model, "text"):
                    continue

                logger.debug(f"model: {ctx.model}, worker: {worker}, type: count_tokens")
                return await worker.count_tokens(ctx)

        return -1
