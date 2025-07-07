import abc
import dataclasses
import request

@dataclasses.dataclass
class Proxy:
    uri : str
    username : str
    password : str

class Proxies(abc.ABC):
    def __init__(self, config: dict = {}):
        self.config = config
    
    @abc.abstractmethod
    async def next(self, request: request.Request) -> Proxy | None:
        ...
