import typing

class Provider:
    name: str = ""

    async def models(request: dict, headers: dict) -> dict[str, typing.Any]:
        ...
    
    async def chat_completions(request: dict, headers: dict) -> dict[str, typing.Any]:
        ...
    
    async def completion(request: dict, headers: dict) -> typing.AsyncIterable[str]:
        ...
    
    async def count_tokens(request: dict, headers: dict) -> int | None:
        ...
