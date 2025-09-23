import re
import json
import typing
import asyncio
import rnet
import worker
import proxies
import context
import error


class AkashWorker(worker.Worker):
    def __init__(
        self, settings: dict[str, typing.Any], proxies: proxies.ProxyFactory
    ) -> None:
        super().__init__(settings, proxies)
        self.headers = {
            "referer": "https://chat.akash.network/",
        }

    async def _client_created(self, client: rnet.Client) -> bool:
        async with await client.get(
            "https://chat.akash.network/api/auth/session/", headers=self.headers
        ) as response:
            assert isinstance(response, rnet.Response)
            assert response.ok, f"ERROR: {response.status} {await response.text()}"
            data = await response.json()

        return data.get("success", False)

    async def models(self) -> list[str]:
        reverse_aliases = dict(zip(self.aliases.values(), self.aliases.keys()))

        async with self.client() as client:
            async with await client.get(
                "https://chat.akash.network/api/models/", headers=self.headers
            ) as response:
                assert isinstance(response, rnet.Response)
                assert response.ok, f"ERROR: {response.status} {await response.text()}"
                return [
                    reverse_aliases.get(x["id"], x["id"])
                    for x in await response.json()
                    if x["available"]
                ]

    async def generate_text(self, ctx: context.Context) -> context.Text:
        if ctx.body.get("model") not in self.available_models:
            raise error.WorkerUnsupportedError(
                f"Model {ctx.body['model']} not available"
            )
        if ctx.body.get("model") == "AkashGen":
            raise error.WorkerUnsupportedError(
                f"Model {ctx.body['model']} for image generation only"
            )

        async def generate():
            async with self.client() as client:
                async with await client.post(
                    "https://chat.akash.network/api/chat/",
                    json=ctx.payload(self.aliases),
                    headers=self.headers,
                ) as response:
                    assert isinstance(response, rnet.Response)
                    assert response.ok, (
                        f"ERROR: {response.status} {await response.text()}"
                    )
                    reasoning = False

                    async with response.stream() as streamer:
                        assert isinstance(streamer, rnet.Streamer)
                        buffer = b""
                        async for chunk in streamer:
                            assert isinstance(chunk, bytes)
                            buffer += chunk
                            if not buffer.endswith(b"\n"):
                                continue

                            for line in buffer.split(b"\n"):
                                content = line[line.find(b":") + 1 :].strip()
                                if content:
                                    data = json.loads(
                                        content.decode(response.encoding or "utf-8")
                                    )
                                    if isinstance(data, str):
                                        if "<think>" in data:
                                            reasoning = True
                                            data = data.replace("<think>", "")
                                        elif "</think>" in data:
                                            reasoning = False
                                            data = data.replace("</think>", "")

                                        if data:
                                            yield context.Text(
                                                type="text",
                                                content=data if not reasoning else None,
                                                reasoning_content=data if reasoning else None,
                                                tool_calls=None,
                                            )
                                    elif isinstance(data, dict):
                                        if usage := data.get("usage", None):
                                            ctx.metadata["usage"] = {
                                                "prompt_tokens": usage.get("promptTokens", None),
                                                "completion_tokens": usage.get("completionTokens", None),
                                                "total_tokens": usage.get("promptTokens", 0) + usage.get("completionTokens", 0) or None,
                                            }

                            buffer = b""

        if ctx.body.get("stream", False):
            return generate()

        data = context.Text(type="text", content="", reasoning_content="", tool_calls=None)
        async for chunk in generate():
            if delta := chunk.get("content", None):
                data["content"] += delta
            if delta := chunk.get("reasoning_content", None):
                data["reasoning_content"] += delta
        
        data.update({
            "content": data["content"] if data["content"] else None,
            "reasoning_content": data["reasoning_content"] if data["reasoning_content"] else None,
        })

        return data

    async def generate_image(self, ctx: context.Context) -> context.Image:
        payload = {
            "model": "AkashGen",
            "messages": [
                {
                    "role": "user",
                    "content": f"""\
Prompt: {ctx.body.get("prompt", "")}

Negative prompt: {ctx.body.get("negative_prompt", "")}
""",
                }
            ],
        }

        async with self.client() as client:
            job_id = None
            # start generate
            async with await client.post(
                "https://chat.akash.network/api/chat/",
                json=payload,
                headers=self.headers,
            ) as response:
                assert isinstance(response, rnet.Response)
                assert response.ok, f"ERROR: {response.status} {await response.text()}"

                async with response.stream() as streamer:
                    assert isinstance(streamer, rnet.Streamer)
                    chunks = b""
                    async for chunk in streamer:
                        assert isinstance(chunk, bytes)
                        chunks += chunk
                        if not chunks.endswith(b"\n"):
                            continue

                        data = json.loads(chunks[: chunks.find(":")])
                        chunks = b""
                        if isinstance(data, str) and "jobId=" in data:
                            job_id = re.search(r"jobId='([^']+?)'", data).group(1)
                            break

            if not job_id:
                raise error.WorkerNoAvaliableError("Akash error")

            # wait for done
            while True:
                async with await client.get(
                    f"https://chat.akash.network/api/image-status/?ids={job_id}",
                    headers=self.headers,
                ) as response:
                    assert isinstance(response, rnet.Response)
                    assert response.ok, (
                        f"ERROR: {response.status} {await response.text()}"
                    )
                    data = await response.json()

                if data[0].get("status") == "pending":
                    await asyncio.sleep(1)
                    continue

                if data[0].get("status") == "succeeded":
                    if url := data[0].get("result"):
                        async with await client.get(
                            url, headers=self.headers
                        ) as response:
                            assert isinstance(response, rnet.Response)
                            return context.Image(
                                type="image",
                                content=await response.bytes(),
                                mime_type=response.headers.get("content-type").decode(
                                    "utf-8"
                                ),
                            )

                raise error.WorkerNoAvaliableError(f"Akash unkown error {data}")
