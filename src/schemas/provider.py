import uuid
import typing
import closeai
import request
from . import proxies
from ..utils import loader
from ..proxies import noproxy

class Provider:
    name: str = ""
    metadata: dict[str, typing.Any]
    available_models : list[str] = []
    proxy: proxies.Proxies = None

    def __init__(self, config: dict):
        self.config = config
        self.name = config.get("name", uuid.uuid1().hex)
        self.metadata = config.get("metadata", self.metadata)
        self.available_models = config.get("models", self.available_models)

        if proxy := config.get("proxy", None):
            self.proxy = loader.create(proxy["name"], proxy)
        else:
            self.proxy = noproxy.NoProxy()

    def __hash__(self):
        return hash(f"provider-{self.name}")

    async def models(self, request: request.Request) -> closeai.ModelListResponse:
        return {
            "object": "list",
            "data": [ { "id": x } for x in self.available_models ]
        }
    
    async def chat_completions(self, request: request.Request) -> closeai.ChatResponse:
        content = ""
        for chunk in self.stream_chat_completions(request):
            assert isinstance(chunk, closeai.ChatResponse)
            content += chunk["choices"][0]["message"]["content"] or ""
        
        return {
            "id": chunk["id"],
            "object": "chat.completion",
            "created": chunk["created"],
            "model": chunk["model"],
            "usage": chunk["usage"],
            "choices": [
                {
                    "index": 0,
                    "finish_reason": chunk["choices"][0]["finish_reason"],
                    "message": {
                        "content": chunk["choices"][0]["message"]["content"],
                        "role": chunk["choices"][0]["message"]["role"],
                        "tool_calls": chunk["choices"][0]["message"]["tool_calls"],
                    }
                }
            ]
        }
    
    async def stream_chat_completions(self, request: request.Request) -> typing.AsyncGenerator[closeai.ChatStreamResponse]:
        completion = await self.chat_completions(request)
        yield {
            "id": completion["id"],
            "object": "chat.completion",
            "created": completion["created"],
            "model": completion["model"],
            "usage": completion["usage"],
            "choices": [
                {
                    "index": 0,
                    "finish_reason": completion["choices"][0]["finish_reason"],
                    "delta": {
                        "content": completion["choices"][0]["message"]["content"],
                        "role": completion["choices"][0]["message"]["role"],
                        "tool_calls": completion["choices"][0]["message"]["tool_calls"],
                    }
                }
            ]
        }
    
    async def count_tokens(self, request: request.Request) -> int | None:
        return None
    
    async def embedding(self, request: request.Request) -> bytes:
        ...
