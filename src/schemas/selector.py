import abc
from . import provider

class Selector(abc.ABC):
    def __init__(self, providers : list[provider.Provider], chat : bool, stream: bool, model: str):
        self.providers = providers
        self.chat = chat
        self.stream = stream
        self.model = model
    
    @abc.abstractmethod
    async def select(self, request : dict, headers : dict) -> provider.Provider:
        ...
    
    def get_available_providers(self, model: str) -> list[provider.Provider]:
        return [p for p in self.providers if model in p.available_models]

