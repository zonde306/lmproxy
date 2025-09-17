import typing
import contextlib
import context
import loader
import error
import cache
import proxies

class Worker:
    def __init__(self, settings: dict[str, typing.Any], proxies: proxies.ProxyFactory) -> None:
        self.settings = settings
        self.proxies = proxies

    async def models(self) -> list[str]:
        return []
    
    async def generate_text(self, context : context.Context) -> str | typing.AsyncGenerator[str | bytes, None]:
        raise NotImplementedError
    
    async def generate_image(self, context : context.Context) -> bytes:
        raise NotImplementedError
    
    async def generate_audio(self, context : context.Context) -> bytes:
        raise NotImplementedError
    
    async def generate_embedding(self, context : context.Context) -> list[float]:
        raise NotImplementedError
    
    async def count_tokens(self, context : context.Context) -> int:
        raise NotImplementedError
    
    @property
    def proxy(self):
        return self.proxies(self.settings.get("proxy", None))

class WorkerManager(Worker):
    def __init__(self, settings: dict[str, typing.Any], proxies: proxies.ProxyFactory) -> None:
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
                if cls := worker.get("class"):
                    priority = worker.get("priority", 100)
                    workers.append([priority, cls(worker, proxies)])
        
        workers.sort(key=lambda x: x[0], reverse=True)
        self.workers = [worker[1] for worker in workers]
    
    @cache.ttl_cache(300)
    async def models(self) -> list[str]:
        models = []
        for worker in self.workers:
            for model in await worker.models():
                if model not in models:
                    models.append(model)
        return models
    
    async def generate_text(self, context : context.Context) -> str | typing.AsyncIterator[str | bytes, None]:
        for worker in self.workers:
            with contextlib.suppress(NotImplementedError, error.WorkerError):
                return await worker.generate_text(context)
        
        raise error.WorkerError("No avaliable workers")
    
    async def generate_image(self, context : context.Context) -> bytes:
        for worker in self.workers:
            with contextlib.suppress(NotImplementedError, error.WorkerError):
                return await worker.generate_image(context)
        
        raise error.WorkerError("No avaliable workers")
    
    async def generate_audio(self, context : context.Context) -> bytes:
        for worker in self.workers:
            with contextlib.suppress(NotImplementedError, error.WorkerError):
                return await worker.generate_audio(context)
        
        raise error.WorkerError("No avaliable workers")
    
    async def generate_embedding(self, context : context.Context) -> list[float]:
        for worker in self.workers:
            with contextlib.suppress(NotImplementedError, error.WorkerError):
                return await worker.generate_embedding(context)
        
        raise error.WorkerError("No avaliable workers")
    
    async def count_tokens(self, context):
        for worker in self.workers:
            with contextlib.suppress(NotImplementedError, error.WorkerError):
                return await worker.count_tokens(context)
        
        return -1
