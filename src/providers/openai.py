import json
import typing
from ..schemas import provider
from ..schemas import closeai
from ..schemas import request
import rnet

class OpenaiProvider(provider.Provider):
    def __init__(self, config: dict):
        super().__init__(config)
        self.chat_completion = config.get('chat_completions', None)
        self.text_completion = config.get('text_completions', None)
    
    async def create_session(self) -> rnet.Client:
        proxy = await self.proxy.next()
        proxy = [ rnet.Proxy.all(**proxy) ] if proxy else None
        client = rnet.Client(
            cookie_store=False,
            timeout=600,
            proxies=proxy,
        )

        return client
    
    async def stream_chat_completions(self, request: request.Request) -> typing.AsyncGenerator[closeai.ChatStreamResponse]:
        session = await self.create_session()

        async with await session.post(self.chat_completion, json=request.body) as response:
            assert isinstance(response, rnet.Response)
            assert response.status_code.is_success(), f"{response.status_code} {await response.text()}"
            async with response.stream() as streamer:
                assert isinstance(streamer, rnet.Streamer)
                buffer = b""
                async for chunk in streamer:
                    assert isinstance(chunk, bytes)
                    buffer += chunk
                    if buffer.startswith("data:"):
                        try:
                            data = json.loads(buffer[5:])
                        except json.decoder.JSONDecodeError:
                            continue
                    
                    if isinstance(data, dict):
                        data["id"] = request.id.hex
                        data["model"] = request.body["model"]
                        yield data
    
    async def chat_completions(self, request: request.Request) -> closeai.ChatResponse:
        session = await self.create_session()

        async with await session.post(self.chat_completion, json=request.body) as response:
            assert isinstance(response, rnet.Response)
            assert response.status_code.is_success(), f"{response.status_code} {await response.text()}"
            data = await response.json()
            if isinstance(data, dict):
                data["id"] = request.id.hex
                data["model"] = request.body["model"]
                return data
