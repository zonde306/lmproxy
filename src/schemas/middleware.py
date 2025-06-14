class Middleware:
    name : str = ""

    async def process_request(self, request: dict, headers: dict, chat: bool) -> None | dict:
        ...
    
    async def process_response(self, request: dict, response: dict, headers: dict, chat: bool) -> None | dict:
        ...
    
    async def process_stream_response(self, request: dict, response: str, headers: dict, chat: bool) -> None | str:
        ...
