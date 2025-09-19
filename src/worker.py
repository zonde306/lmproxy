import typing
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
        self, settings: dict[str, typing.Any], proxies: proxies.ProxyFactory
    ) -> None:
        self.settings = settings
        self._proxies = proxies
        self.available_models: list[str] = settings.get("models", [])
        self.client_args: http_client.ClientOptions = {}
        self.name = settings.get("name", self.__class__.__name__)

    async def models(self) -> list[str]:
        return []

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
        self, settings: dict[str, typing.Any], proxies: proxies.ProxyFactory
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
        [ x.available_models.clear() for x in self.workers ]
        models = await asyncio.gather(*[ x.models() for x in self.workers ])
        [ x.available_models.extend(models[i]) for i, x in enumerate(self.workers) ]
        avaliable_models = sorted(set(itertools.chain.from_iterable(models)), key=lambda x: x.lower())
        logger.info(f"available models: {avaliable_models}")
        return avaliable_models

    async def generate_text(self, context: context.Context) -> context.Text:
        for worker in self.workers:
            with error.worker_handler(context, logger, worker):
                logger.debug(f"model: {context.model}, worker: {worker}")
                return await worker.generate_text(context)

        raise error.WorkerError("No avaliable workers")

    async def generate_image(self, context: context.Context) -> context.Image:
        for worker in self.workers:
            with error.worker_handler(context, logger, worker):
                logger.debug(f"model: {context.model}, worker: {worker}")
                return await worker.generate_image(context)

        raise error.WorkerError("No avaliable workers")

    async def generate_audio(self, context: context.Context) -> context.Audio:
        for worker in self.workers:
            with error.worker_handler(context, logger, worker):
                logger.debug(f"model: {context.model}, worker: {worker}")
                return await worker.generate_audio(context)

        raise error.WorkerError("No avaliable workers")

    async def generate_embedding(self, context: context.Context) -> context.Embedding:
        for worker in self.workers:
            with error.worker_handler(context, logger, worker):
                logger.debug(f"model: {context.model}, worker: {worker}")
                return await worker.generate_embedding(context)

        raise error.WorkerError("No avaliable workers")

    async def generate_video(self, context: context.Context) -> context.Video:
        for worker in self.workers:
            with error.worker_handler(context, logger, worker):
                logger.debug(f"model: {context.model}, worker: {worker}")
                return await worker.generate_video(context)

        raise error.WorkerError("No avaliable workers")

    async def count_tokens(self, context) -> context.CountTokens:
        for worker in self.workers:
            with error.worker_handler(context, logger, worker):
                logger.debug(f"model: {context.model}, worker: {worker}")
                return await worker.count_tokens(context)

        return -1
