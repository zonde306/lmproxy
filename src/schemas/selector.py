import abc
import request
from . import provider

class Selector(abc.ABC):
    def __init__(self, providers : list[provider.Provider], chat : bool, stream: bool):
        self.providers = providers
        self.chat = chat
        self.stream = stream
    
    @abc.abstractmethod
    async def next(self, request: request.Request) -> provider.Provider:
        ...
    
    def get_available_providers(self, model: str) -> list[provider.Provider]:
        return [p for p in self.providers if model in p.available_models]

