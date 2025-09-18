import json
import typing
import asyncio
import urllib.parse
import rnet
import worker
import proxies
import context
import error
import resources


class OpenAiWorker(worker.Worker):
    def __init__(
        self, settings: dict[str, typing.Any], proxies: proxies.ProxyFactory
    ) -> None:
        super().__init__(settings, proxies)
        self.headers: dict[str, str] = settings.get("headers", {})
        self.base_url: str = settings.get("base_url", "https://api.openai.com/v1")
        self.api_keys: list[str] = settings.get("api_keys", [])
        if key := settings.get("api_key"):
            self.api_keys.append(key)
        self._resources = resources.ResourceManager(
            self.api_keys, settings.get("lock_timeout", 60)
        )

    async def models(self) -> list[str]:
        async with self._resources.get() as api_key:
            if not api_key:
                raise error.WorkerOverloadError("No API keys available")

            headers = self.headers.copy()
            headers["Authorization"] = f"Bearer {api_key}"
            async with self.client() as client:
                url = urllib.parse.urljoin(self.base_url, "models")
                async with await client.get(url, headers=headers) as response:
                    data = await response.json()
                    return [x["id"] for x in data["data"]]

    async def generate_text(self, context: context.Context) -> context.Text:
        if context.body.get("model") not in self.available_models:
            raise error.WorkerUnsupportedError(
                f"Model {context.body['model']} not available"
            )

        force_streaming = self.settings.get("streaming", None)
        streaming = context.body.get("stream", False)
        if force_streaming is None:
            if streaming:
                return await self.streaming(context)
            return await self.no_streaming(context)

        if force_streaming:
            if streaming:
                return await self.streaming(context)
            return await self.to_no_streaming(await self.streaming(context))

        if streaming:
            return await self.to_streaming(await self.no_streaming(context))

        return await self.no_streaming(context)

    async def streaming(self, context: context.Context) -> context.Text:
        async def generate() -> typing.AsyncGenerator[str, None]:
            async with self._resources.get() as api_key:
                if not api_key:
                    raise error.WorkerOverloadError("No API keys available")

                headers = self.headers.copy()
                headers["Authorization"] = f"Bearer {api_key}"
                body = context.body.copy()
                body["stream"] = True

                async with self.client() as client:
                    url = urllib.parse.urljoin(self.base_url, "chat/completions")
                    async with await client.post(
                        url, json=body, headers=headers
                    ) as response:
                        assert isinstance(response, rnet.Response)
                        async with response.stream() as streamer:
                            assert isinstance(streamer, rnet.Streamer)
                            buffer = b""
                            async for chunk in streamer:
                                assert isinstance(chunk, bytes)
                                buffer += chunk
                                if not buffer.endswith(b"\n"):
                                    continue

                                for line in buffer.split(b"\n"):
                                    content = line.strip().removeprefix(b"data:")
                                    if content:
                                        if b"[DONE]" in content:
                                            break
                                        
                                        data = json.loads(content.decode(response.encoding or "utf-8"))
                                        text = data["choices"][0]["delta"].get("content", None)
                                        reasoning = data["choices"][0]["delta"].get("reasoning_content", None)
                                        yield [ text, reasoning ]
                                
                                buffer = b""

        return generate()

    async def no_streaming(self, context: context.Context) -> context.Text:
        async with self._resources.get() as api_key:
            if not api_key:
                raise error.WorkerOverloadError("No API keys available")

            headers = self.headers.copy()
            headers["Authorization"] = f"Bearer {api_key}"
            body = context.body.copy()
            body["stream"] = False

            async with self.client() as client:
                url = urllib.parse.urljoin(self.base_url, "chat/completions")
                async with await client.post(
                    url, json=context.body, headers=headers
                ) as response:
                    data = await response.json()
                    text = data["choices"][0]["message"].get("content", None)
                    reasoning = data["choices"][0]["message"].get("reasoning_content", None)
                    return [ text, reasoning ]

    async def to_streaming(self, response: context.Text) -> context.Text:
        task = asyncio.create_task(response)
        while not task.done():
            await asyncio.wait(
                {task}, timeout=self.settings.get("fake_streaming_interval", 9)
            )
            yield ""

        yield task.result()

    async def to_no_streaming(self, response: context.Text) -> context.Text:
        text = ""
        reasoning = ""
        async for chunk in response:
            text += chunk[0] or ""
            reasoning += chunk[1] or ""

        return [ text or None, reasoning or None ]
