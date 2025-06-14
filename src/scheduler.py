import typing
import random
import collections
import schemas.provider
import schemas.response
import utils.loader
import utils.lazy_settings

class Scheduler:
    providers: list[schemas.provider.Provider] = []
    available_providers : collections.defaultdict[str, set[schemas.provider.Provider]] = collections.defaultdict(set)
    available_models : list[str] = []

    def __init__(self, providers = utils.lazy_settings.LazySettings('PROVIDERS')) -> None:
        self.providers = utils.loader.create_from_config(providers)

    async def generate(self, request: dict, headers: dict, chat: bool) -> dict[str, typing.Any] | typing.AsyncIterable[str]:
        provider = self.get_provider(request['model'])
        if provider is None:
            raise schemas.response.ClientError(f'No provider for model {request["model"]}', 404)
        
        stream = request['stream']
        
    
    async def models(self, request: dict, headers: dict) -> dict[str, typing.Any]:
        if self.cache_models:
            return {
                "object": "list",
                "data": { "id": x for x in self.available_models },
            }
        
        for provider in self.providers:
            models = await provider.models(request, headers)
            for model in models:
                if model not in self.available_models:
                    self.available_models.append(model)
                self.available_providers[model].add(provider)

        return {
            "object": "list",
            "data": { "id": x for x in self.available_models }
        }
    
    def get_provider(self, model: str) -> schemas.provider.Provider | None:
        providers = self.available_providers[model]
        if not providers:
            return None
        
        total = sum([ abs(provider.probability) for provider in providers ])
        choice = random.randint(0, total)
        for provider in providers:
            choice -= abs(provider.probability)
            if choice <= 0:
                return provider
        
        return None
        