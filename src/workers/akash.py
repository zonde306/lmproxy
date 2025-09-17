import re
import json
import typing
import asyncio
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
        async with client.get("https://chat.akash.network/api/auth/session/") as response:
            data = await response.json()
        return data.get("success", False)
    
    async def models(self) -> list[str]:
        async with self.proxy as proxy:
            client = rnet.Client(proxies = rnet.Proxy.all(proxy.proxy) if proxy.proxy else None)
            assert await self.create_session(client), "Akash error"
            async with await client.get("https://chat.akash.network/api/models/") as response:
                self.available_models = [ x["id"] for x in await response.json() if x["available"] ]
            return self.available_models
    
    async def generate_text(self, context : context.Context) -> context.Text:
        if context.body["model"] not in self.available_models:
            raise error.WorkerError(f"Model {context.body['model']} not available")
        if context.body["model"] == "AkashGen":
            raise error.WorkerError(f"Model {context.body['model']} for image generation only")

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
                            chunks = b""
                            if isinstance(data, str):
                                yield data
        
        if context.body.get("stream", False):
            return generate()
        
        data = ""
        async for chunk in generate():
            data += chunk
        
        return data
    
    async def generate_image(self, context : context.Context) -> context.Image:
        async with self.proxy as proxy:
            client = rnet.Client(proxies = rnet.Proxy.all(proxy.proxy) if proxy.proxy else None)
            assert await self.create_session(client), "Akash error"

            job_id = None
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
                        chunks = b""
                        if isinstance(data, str) and "jobId=" in data:
                            job_id = re.search(r"jobId='([^']+?)'", data).group(1)
                            break
            
            if not job_id:
                raise error.WorkerNoAvaliableError("Akash error")
            
            while True:
                async with client.get(f"https://chat.akash.network/api/image-status/?ids={job_id}") as response:
                    data = await response.json()
                
                if data[0].get("status") == "pending":
                    await asyncio.sleep(1)
                    continue
                
                if data[0].get("status") == "succeeded":
                    if url := data[0].get("result"):
                        async with client.get(url) as response:
                            assert isinstance(response, rnet.Response)
                            return ( await response.bytes(), response.headers.get("content-type").decode("utf-8") )
                
                raise error.WorkerNoAvaliableError(f"Akash unkown error {data}")

