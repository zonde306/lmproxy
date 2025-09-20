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
        self.models_url: str = settings.get(
            "models_url", "https://api.openai.com/v1/models"
        )
        self.completions_url: str = settings.get(
            "completions_url", "https://api.openai.com/v1/completions"
        )
        self.api_keys: list[str] = settings.get("api_keys", [])
        key = settings.get("api_key")
        if key is not None:
            self.api_keys.append(key)
        self._resources = resources.ResourceManager(
            self.api_keys, settings.get("lock_timeout", 60)
        )

    async def models(self) -> list[str]:
        reverse_aliases = dict(zip(self.aliases.values(), self.aliases.keys()))

        async with self._resources.get() as api_key:
            if api_key is None:
                raise error.WorkerOverloadError("No API keys available")

            headers = self.headers.copy()
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            async with self.client() as client:
                url = urllib.parse.urljoin(self.models_url, "models")
                async with await client.get(url, headers=headers) as response:
                    data = await response.json()
                    return [reverse_aliases.get(x["id"], x["id"]) for x in data["data"]]

    async def generate_text(self, context: context.Context) -> context.Text:
        if context.body.get("model") not in self.available_models:
            raise error.WorkerModelUnsupportedError(
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
            return await self.to_streaming(self.no_streaming(context))

        return await self.no_streaming(context)

    async def streaming(self, context: context.Context) -> context.Text:
        async def generate() -> typing.AsyncGenerator[str, None]:
            async with self._resources.get() as api_key:
                if api_key is None:
                    raise error.WorkerOverloadError("No API keys available")

                headers = self.headers.copy()
                body = context.payload(self.aliases)
                await self._prepare_payload(headers, body, api_key, True)

                async with self.client() as client:
                    async with await client.post(
                        self.completions_url, json=body, headers=headers
                    ) as response:
                        assert isinstance(response, rnet.Response)
                        assert response.ok, (
                            f"ERROR: {response.status} {await response.text()}"
                        )

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

                                        data = json.loads(
                                            content.decode(response.encoding or "utf-8")
                                        )
                                        yield await self._parse_response(data)

                                buffer = b""

        return generate()

    async def no_streaming(self, context: context.Context) -> context.Text:
        async with self._resources.get() as api_key:
            if api_key is None:
                raise error.WorkerOverloadError("No API keys available")

            headers = self.headers.copy()
            body = context.payload(self.aliases)
            await self._prepare_payload(headers, body, api_key, False)

            async with self.client() as client:
                async with await client.post(
                    self.completions_url, json=body, headers=headers
                ) as response:
                    assert isinstance(response, rnet.Response)
                    assert response.ok, (
                        f"ERROR: {response.status} {await response.text()}"
                    )

                    data = await response.json()
                    return await self._parse_response(data)

    async def to_streaming(
        self, response: typing.Awaitable[context.Text]
    ) -> typing.AsyncGenerator[context.Text, None]:
        task = asyncio.create_task(response)
        while not task.done():
            await asyncio.wait(
                {task}, timeout=self.settings.get("fake_streaming_interval", 9)
            )
            yield context.Text(type="text", content=None, reasoning_content=None, tool_calls=[])

        yield task.result()

    async def to_no_streaming(self, response: typing.AsyncGenerator[context.Text, None]) -> context.Text:
        content = context.Text(type="text", content="", reasoning_content="", tool_calls=[])
        async for chunk in response:
            if delta := chunk.get("content", None):
                content["content"] += delta
            if delta := chunk.get("reasoning_content", None):
                content["reasoning_content"] += delta
            if delta := chunk.get("tool_calls", None):
                content["tool_calls"].extend(delta)

        content.update({
            "content": content["content"] if content["content"] else None,
            "reasoning_content": content["reasoning_content"] if content["reasoning_content"] else None,
            "tool_calls": content["tool_calls"] if content["tool_calls"] else None,
        })
        return content

    async def _prepare_payload(
        self,
        headers: dict[str, str],
        body: dict[str, typing.Any],
        api_key: str,
        streaming: bool,
    ) -> None:
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        body["stream"] = streaming

    async def _parse_response(self, data: dict[str, typing.Any]) -> context.Text:
        text = data["choices"][0].get("delta", {}).get("content", None) or data[
            "choices"
        ][0].get("message", {}).get("content", None)
        reasoning = data["choices"][0].get("delta", {}).get(
            "reasoning_content", None
        ) or data["choices"][0].get("message", {}).get("reasoning_content", None)
        tool_calls = data["choices"][0].get("tool_calls", None)
        
        return context.Text(type="text", content=text, reasoning_content=reasoning, tool_calls=tool_calls)
