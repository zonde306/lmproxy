import re
import json
import typing
import rnet
import worker
import proxies
import context
import error

class K2ThinkWorker(worker.Worker):
    def __init__(
        self, settings: dict[str, typing.Any], proxies: proxies.ProxyFactory
    ) -> None:
        super().__init__(settings, proxies)
        self.headers = {
            "referer": "https://www.k2think.ai/guest/",
        }
        self.aliases = {
            "K2-Think": "MBZUAI-IFM/K2-Think",
        }
    
    async def models(self) -> list[str]:
        reverse_aliases = dict(zip(self.aliases.values(), self.aliases.keys()))

        async with self.client() as client:
            async with await client.get(
                "https://www.k2think.ai/api/guest/models", headers=self.headers
            ) as response:
                assert isinstance(response, rnet.Response)
                assert response.ok, f"ERROR: {response.status} {await response.text()}"

                data = await response.json()
                return [
                    reverse_aliases.get(x["id"], x["id"])
                    for x in data["data"]
                    if x["status"] == "active"
                ]
    
    async def generate_text(self, ctx: context.Context) -> context.Text:
        if ctx.body.get("model") not in self.available_models:
            raise error.WorkerUnsupportedError(
                f"Model {ctx.body['model']} not available"
            )
        
        async def generate():
            payload = ctx.payload(self.aliases)
            payload["params"] = {}
            payload["stream"] = True

            async with self.client() as client:
                async with await client.post(
                    "https://www.k2think.ai/api/guest/chat/completions",
                    json=payload,
                    headers=self.headers,
                ) as response:
                    assert isinstance(response, rnet.Response)
                    assert response.ok, (
                        f"ERROR: {response.status} {await response.text()}"
                    )
                    previous_content = ""
                    previous_reasoning = ""

                    async with response.stream() as streamer:
                        assert isinstance(streamer, rnet.Streamer)
                        buffer = b""
                        async for chunk in streamer:
                            assert isinstance(chunk, bytes)
                            buffer += chunk
                            if not buffer.endswith(b"\n"):
                                continue

                            for line in buffer.split(b"\n"):
                                line = line[line.find(b":") + 1 :].strip()
                                if line:
                                    data = json.loads(
                                        line.decode(response.encoding or "utf-8")
                                    )
                                    text = data.get("content", "")
                                    if text:
                                        content, reasoning = self._parse_content(text)
                                        content = content[len(previous_content):]
                                        previous_content += content
                                        reasoning = reasoning[len(previous_reasoning):]
                                        previous_reasoning += reasoning
                                        
                                        yield context.Text(
                                            type="text",
                                            content=content,
                                            reasoning_content=reasoning,
                                            tool_calls=None
                                        )

                            buffer = b""

        if ctx.body.get("stream", False):
            return generate()

        data = context.Text(type="text", content="", reasoning_content="", tool_calls=None)
        async for chunk in generate():
            if delta := chunk.get("content", None):
                data["content"] += delta
            if delta := chunk.get("reasoning_content", None):
                data["reasoning_content"] += delta

        return data
    
    def _parse_content(self, content: str) -> tuple[str, str]:
        content = re.sub(r"<summary>[\s\S]*?</summary>", "", content)
        reasoning = ""
        if match := re.search(r"(<details type=[\s\S]*?>)([\s\S]*?)(</details>)", content, re.DOTALL):
            reasoning = match.group(2)
            content = content.replace(match.group(0), "")
        
        reasoning = reasoning.removeprefix("\n\n>").removeprefix("\n>").strip()
        content = content.removeprefix("\n\n>").removeprefix("\n>")
        content = content.replace("<answer>", "").replace("</answer>", "").strip()
        return content, reasoning
