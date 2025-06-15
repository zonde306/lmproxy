import json
import uuid
import time
import typing
from ..schemas import provider
from ..schemas import closeai
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
        )

        response = await client.get("https://chat.akash.network/api/auth/session/")
        if response.status != 200:
            raise RuntimeError("Failed to create session")
        
        data = await response.json()
        if not data.get("success", False):
            raise RuntimeError(f"Failed to create session {data}")
        
        return client
    
    async def models(self, request: dict, headers: dict) -> list[str]:
        session = await self.create_session()
        response = await session.get("https://chat.akash.network/api/models/")
        if response.status != 200:
            raise RuntimeError("Failed to get models")
        
        data : list[dict] = await response.json()
        return [ x["id"] for x in data ]
    
    async def stream_chat_completions(self, request: dict, headers: dict) -> typing.AsyncIterable[closeai.ChatCompletionChunk]:
        session = await self.create_session()
        request_id = uuid.uuid4().hex
        
        async with await session.post("https://chat.akash.network/api/chat", json=request) as response:
            assert isinstance(response, rnet.Response)
            assert response.status_code.is_success(), f"{response.status_code} {await response.text()}"
            async with response.stream() as streamer:
                assert isinstance(streamer, rnet.Streamer)
                async for chunk in streamer:
                    assert isinstance(chunk, bytes)
                    data = json.loads(chunk[chunk.find(':') + 1:])
                    if isinstance(data, str):
                        yield closeai.ChatCompletionChunk(
                            id=request_id,
                            created=time.time(),
                            model=request['model'],
                            choices=[
                                closeai.ChatCompletionChoiceChunk(
                                    index=0,
                                    delta=closeai.ChatCompletionChoiceDelta(
                                        content=data,
                                        role="assistant",
                                    )
                                )
                            ]
                        )
                
                yield closeai.ChatCompletionChunk(
                    id=request_id,
                    created=time.time(),
                    model=request['model'],
                    choices=[
                        closeai.ChatCompletionChoiceChunk(
                            index=0,
                            finish_reason="stop",
                            delta=closeai.ChatCompletionChoiceDelta(
                                role="assistant",
                            )
                        )
                    ]
                )

