import typing
import itertools
import schemas.provider
import schemas.response
import schemas.request
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
    
    async def generate(self, request: schemas.request.Request) -> dict[str, typing.Any] | typing.AsyncIterable[dict[str, typing.Any]]:
        stream = request.body['stream']
        selector : schemas.selector.Selector = utils.loader.create(
            self.selector,
            self.providers,
            request.type == "chat",
            stream
        )

        provider = await selector.next(request)
        if provider is None:
            raise schemas.response.ClientError(f'No provider for model {request.body["model"]}', 404)
        
        if request.type == "chat" and stream:
            return provider.stream_chat_completions(request)
        if request.type == "chat":
            return await provider.chat_completions(request)
        
        raise NotImplementedError
    
    async def models(self, request: dict, headers: dict) -> dict[str, typing.Any]:
        all_models = itertools.chain.from_iterable([await x.models(request, headers) for x in self.providers])
        return {
            "object": "list",
            "data": [{ "id": x } for x in all_models ],
        }
    