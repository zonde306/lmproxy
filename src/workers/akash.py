import json
import typing
import rnet
from .. import worker
from .. import proxies
from .. import context
from .. import error

class AkashWorker(worker.Worker):
    def __init__(self, settings: dict[str, typing.Any], proxies: proxies.ProxyFactory) -> None:
        super().__init__(settings, proxies)
        self.available_models = settings.get("models", [])
    
    async def create_session(self, client: rnet.Client) -> bool:
        response = await client.get("https://chat.akash.network/api/auth/session/")
        data = await response.json()
        return data.get("success", False)
    
    async def models(self) -> list[str]:
        async with self.proxy as proxy:
            client = rnet.Client(proxies = rnet.Proxy.all(proxy.proxy) if proxy.proxy else None)
            assert await self.create_session(client), "Akash error"
            response = await client.get("https://chat.akash.network/api/models/")
            self.available_models = [ x["id"] for x in await response.json() if x["available"] ]
            return self.available_models
    
    async def generate_text(self, context : context.Context) -> str | typing.AsyncGenerator[str | bytes, None]:
        if context.body["model"] not in self.available_models:
            raise error.WorkerError(f"Model {context.body['model']} not available")

        async def generate():
            async with self.proxy as proxy:
                client = rnet.Client(proxies = rnet.Proxy.all(proxy.proxy) if proxy.proxy else None)
                assert await self.create_session(client), "Akash error"
                
                async with client.post("https://chat.akash.network/api/chat/", json=context.body) as response:
                    assert isinstance(response, rnet.Response)
                    async with response.stream() as streamer:
                        assert isinstance(streamer, rnet.Streamer)
                        chunks = b""
                        async for chunk in streamer:
                            assert isinstance(chunk, bytes)
                            chunks += chunk
                            if not chunks.endswith(b"\n"):
                                continue
                            
                            data = json.loads(chunks[:chunks.find(":")])
                            if isinstance(data, str):
                                yield data
        
        if context.body.get("stream", False):
            return generate()
        
        data = ""
        async for chunk in generate():
            data += chunk
        
        return data
