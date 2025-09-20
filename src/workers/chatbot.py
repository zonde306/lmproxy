import uuid
import json
import typing
import base64
import rnet
import worker
import proxies
import context
import error


class ChatbotWorker(worker.Worker):
    def __init__(
        self, settings: dict[str, typing.Any], proxies: proxies.ProxyFactory
    ) -> None:
        settings.setdefault("streaming", True)
        super().__init__(settings, proxies)
        self.headers = {
            "referer": "https://demo.chat-sdk.dev/",
        }

    async def _client_created(self, client: rnet.Client) -> bool:
        if not self.headers.get("cookie", None):
            await self.create_cookie(client)

        # 刷新 cookie
        async with await client.get(
            "https://demo.chat-sdk.dev/api/auth/session",
            headers=self.headers,
        ) as response:
            assert isinstance(response, rnet.Response)
            if response.status == 429:
                raise error.WorkerOverloadError(f"ERROR: {response.status} Too Many Requests")

            assert response.ok, f"ERROR on refresh cookie: {response.status} {await response.text()}"
            data = await response.json()
            assert data is not None, "ERROR: invalid cookie"

        self.update_cookie(client.get_cookies("https://demo.chat-sdk.dev/"))
        return True
    
    async def create_cookie(self, client: rnet.Client) -> bool:
        # 获取 cookie
        async with await client.get(
            "https://demo.chat-sdk.dev/",
            headers=self.headers,
            allow_redirects=True,
            max_redirects=16,
        ) as response:
            assert isinstance(response, rnet.Response)
            if response.status == 429:
                raise error.WorkerOverloadError(f"ERROR: {response.status} Too Many Requests")

            assert response.ok, f"ERROR on fetch cookie: {response.status} {await response.text()}"
            self.update_cookie(client.get_cookies("https://demo.chat-sdk.dev/"))
            return True

    async def models(self) -> list[str]:
        return ["grok-4-fast", "grok-4-fast-reasoning"]

    async def generate_text(self, ctx: context.Context) -> context.Text:
        if ctx.body.get("model") not in self.available_models:
            raise error.WorkerUnsupportedError(
                f"Model {ctx.body['model']} not available"
            )

        payload = {
            "id": str(uuid.uuid4()),
            "message": {
                "id": str(uuid.uuid4()),
                "parts": await self.formatting_messages(ctx.body.get("messages", [])),
                "role": "user",
            },
            "selectedChatModel": self.aliases.get(ctx.model, "chat-model"),
            "selectedVisibilityType": "private",
        }

        headers = self.headers.copy()
        headers["referer"] = f"https://demo.chat-sdk.dev/chat/{payload['id']}"

        async def generate():
            async with self.client() as client:
                async with await client.post(
                    "https://demo.chat-sdk.dev/api/chat",
                    json=payload,
                    headers=headers,
                ) as response:
                    assert isinstance(response, rnet.Response)
                    if response.status == 429:
                        raise error.WorkerOverloadError(f"ERROR: {response.status} Too Many Requests")
                    
                    assert response.ok, (
                        f"ERROR: {response.status} {await response.text()}"
                    )
                    self.update_cookie(client.get_cookies("https://demo.chat-sdk.dev/"))
                    
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

        if ctx.body.get("stream", False):
            return generate()

        data = context.Text(
            type="text", content="", reasoning_content="", tool_calls=None
        )
        async for chunk in generate():
            if delta := chunk.get("content", None):
                data["content"] += delta
            if delta := chunk.get("reasoning_content", None):
                data["reasoning_content"] += delta

        data.update(
            {
                "content": data["content"] if data["content"] else None,
                "reasoning_content": data["reasoning_content"]
                if data["reasoning_content"]
                else None,
            }
        )

        return data

    async def formatting_messages(
        self, messages: list[context.Message]
    ) -> list[dict[str, typing.Any]]:
        texts = []
        images = []
        for x in messages:
            if isinstance(x.get("content", None), str):
                texts.append(x['content'])
            elif isinstance(x.get("content", None), list):
                for part in x["content"]:
                    if isinstance(part, str):
                        texts.append(part)
                    elif isinstance(part, dict):
                        if part.get("type", None) == "text":
                            texts.append(part["text"])
                        elif part.get("type", None) == "image":
                            images.append(part["image_url"]["url"])

        # 上传图片
        url, mime_type = None, None
        if images:
            for image in reversed(images):
                file_data, mime_type = self.parse_file(image)
                if not file_data or not mime_type:
                    continue

                async with await self.client() as client:
                    assert isinstance(client, rnet.Client)
                    async with await client.post(
                        "https://demo.chat-sdk.dev/api/files/upload",
                        multipart=rnet.Multipart(
                            rnet.Part(
                                name="file",
                                filename=f"image.{mime_type.split('/')[-1]}",
                                content=file_data,
                                content_type=mime_type,
                            )
                        ),
                        headers=self.headers,
                    ) as response:
                        assert isinstance(response, rnet.Response)
                        if not response.ok:
                            continue

                        data = await response.json()
                        url = data.get("url", None)
                        if url:
                            break

        results = []
        if url and mime_type:
            results.append(
                {
                    "mediaType": mime_type,
                    "name": f"image.{mime_type.split('/')[-1]}",
                    "type": "file",
                    "url": url,
                }
            )

        if texts:
            results.append(
                {
                    "text": "\n\n".join(texts),
                    "type": "text",
                }
            )

        return results

    def parse_file(self, file_url: str) -> tuple[str, bytes] | tuple[None, None]:
        if file_url.startswith("http"):
            return [file_url, f"image/{file_url.split('.')[-1]}"]

        if file_url.startswith("data:"):
            b64_prefix = file_url.find(";base64,")
            mime_type = file_url[5:b64_prefix]
            return [base64.b64decode(file_url[b64_prefix + 8 :]), mime_type]

        return [None, None]

    async def _parse_response(self, data: dict[str, typing.Any]) -> context.Text:
        text = None
        if data.get("type", None) == "text-delta":
            text = data.get("delta", None)

        reasoning = None
        if data.get("type", None) == "reasoning-delta":
            reasoning = data.get("delta", None)

        return context.Text(
            type="text", content=text, reasoning_content=reasoning, tool_calls=None
        )
    
    def update_cookie(self, cookies: bytes | str):
        if isinstance(cookies, bytes):
            cookies = cookies.decode("utf-8")
        
        self.headers["cookie"] = cookies
    