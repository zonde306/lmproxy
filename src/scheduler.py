import typing
import schemas.provider
import utils.loader
import utils.lazy_settings

class Scheduler:
    providers: list[schemas.provider.Provider] = []

    def __init__(self, providers = utils.lazy_settings.LazySettings('PROVIDERS')) -> None:
        self.providers = utils.loader.create_from_config(providers)

    async def generate(self, request: dict, headers: dict, chat: bool) -> dict[str, typing.Any] | typing.AsyncGenerator[str]:
        ...
