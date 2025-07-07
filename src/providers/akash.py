import json
import time
import typing
from ..schemas import provider
from ..schemas import closeai
from ..schemas import request
import rnet

class AkashProvider(provider.Provider):
    def __init__(self, config: dict):
        super().__init__(config)
    
    async def create_session(self) -> rnet.Client:
        client = rnet.Client(
            impersonate=rnet.Impersonate.Chrome136,
            referer="https://chat.akash.network/",
            cookie_store=True,
            timeout=600,
            proxies=await self.proxy.next(),
        )
        
        response = await client.get("https://chat.akash.network/api/auth/session/")
        if response.status != 200:
            raise RuntimeError("Failed to create session")
        
        data = await response.json()
        if not data.get("success", False):
            raise RuntimeError(f"Failed to create session {data}")
        
        return client
    
    async def models(self, request: request.Request) -> closeai.ModelListResponse:
        session = await self.create_session()
        response = await session.get("https://chat.akash.network/api/models/")
        if response.status != 200:
            raise RuntimeError("Failed to get models")
        
        data : list[dict] = await response.json()
        self.available_models = [ x["id"] for x in data ]
        return await super().models(request)
    
    async def stream_chat_completions(self, request: request.Request) -> typing.AsyncGenerator[closeai.ChatStreamResponse]:
        session = await self.create_session()
        
        async with await session.post("https://chat.akash.network/api/chat", json=request.body) as response:
            assert isinstance(response, rnet.Response)
            assert response.status_code.is_success(), f"{response.status_code} {await response.text()}"
            async with response.stream() as streamer:
                assert isinstance(streamer, rnet.Streamer)
                async for chunk in streamer:
                    assert isinstance(chunk, bytes)
                    data = json.loads(chunk[chunk.find(b':') + 1:])
                    if isinstance(data, str):
                        yield {
                            "id": request.id.hex,
                            "created": int(time.time()),
                            "model": request.body["model"],
                            "object": "chat.completion.chunk",
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {
                                        "content": data,
                                        "role": "assistant",
                                    }
                                }
                            ]
                        }
                
                # Send stop signal
                yield {
                    "id": request.id.hex,
                    "created": int(time.time()),
                    "model": request.body["model"],
                    "object": "chat.completion.chunk",
                    "choices": [
                        {
                            "index": 0,
                            "delta": {
                                "content": "",
                                "role": "assistant",
                            },
                            "finish_reason": "stop",
                        }
                    ]
                }

