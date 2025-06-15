import typing
import itertools
import schemas.provider
import schemas.response
import utils.loader
import utils.lazy_settings
import schemas.selector

class Scheduler:
    providers: list[schemas.provider.Provider] = []

    def __init__(self,
                 providers = utils.lazy_settings.LazySettings('PROVIDERS'),
                 selector = utils.lazy_settings.LazySettings('SELECTOR')) -> None:
        self.providers = utils.loader.create_from_dict(providers)
        self.selector = selector
    
    async def generate(self, request: dict, headers: dict, chat: bool) -> dict[str, typing.Any] | typing.AsyncIterable[str]:
        stream = request['stream']
        selector : schemas.selector.Selector = utils.loader.create(self.selector, self.providers, chat, stream)

        provider = await selector.select(request, headers)
        if provider is None:
            raise schemas.response.ClientError(f'No provider for model {request["model"]}', 404)
        
        if chat and stream:
            return provider.stream_chat_completions(request, headers)
        if chat:
            return await provider.chat_completions(request, headers)
        if stream:
            return provider.stream_completion(request, headers)
        return await provider.completion(request, headers)
    
    async def models(self, request: dict, headers: dict) -> dict[str, typing.Any]:
        all_models = itertools.chain.from_iterable([await x.models(request, headers) for x in self.providers])
        return {
            "object": "list",
            "data": [{ "id": x, "name": x } for x in all_models ],
        }
    