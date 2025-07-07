import request

class Middleware:
    name : str = ""

    def __init__(self, config: dict):
        self.config = config

    async def process_request(self, request: request.Request) -> None | dict:
        ...
    
    async def process_response(self, request: request.Request) -> None | dict:
        ...
    
    async def process_response_chunk(self, request: request.Request) -> None | str:
        ...
