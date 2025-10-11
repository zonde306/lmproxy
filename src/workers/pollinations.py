import random
import typing
import urllib.parse
import proxies
import context
import error
import resources
from . import openai
import rnet


class PollinationsWorker(openai.OpenAiWorker):
    def __init__(
        self, settings: dict[str, typing.Any], proxies: proxies.ProxyFactory
    ) -> None:
        settings.setdefault("completions_url", "https://text.pollinations.ai/openai")
        settings.setdefault("streaming", None)

        super().__init__(settings, proxies)
        self.image_models: list[str] = []
        self.text_models: list[str] = []
        self.max_retries = settings.get("max_retries", 3)
        self.wait_time = settings.get("wait_time", 10)

    async def models(self) -> list[str]:
        reverse_aliases = dict(zip(self.aliases.values(), self.aliases.keys()))

        async with self.client() as client:
            async with await client.get(
                "https://image.pollinations.ai/models"
            ) as response:
                self.image_models = [
                    reverse_aliases.get(x, x) for x in await response.json()
                ]
            async with await client.get(
                "https://text.pollinations.ai/models"
            ) as response:
                data = await response.json()
                self.text_models = [
                    reverse_aliases.get(x["name"], x["name"]) for x in data
                ]

        return self.image_models + self.text_models
    
    async def supports_model(self, model: str, type: str) -> bool:
        if type == "text":
            return model in self.text_models
        elif type == "image":
            return model in self.image_models
        return False

    async def generate_text(self, context: context.Context) -> context.Text:
        if context.model in self.image_models:
            raise error.WorkerUnsupportedError(
                f"Model {context.model} only available for text generation"
            )

        return await super().generate_text(context)

    async def generate_image(self, ctx: context.Context) -> context.Image:
        if ctx.model not in self.image_models:
            raise error.WorkerUnsupportedError(
                f"Model {ctx.model} not available for image generation"
            )

        prompt = urllib.parse.quote(ctx.body.get("prompt", ""), safe="")
        data = {
            "model": ctx.body.get("model", "flux"),
            "seed": ctx.body.get("seed", random.randint(0, 0xFFFFFFFF)),
            "width": ctx.body.get("width", 1024),
            "height": ctx.body.get("height", 1024),
            "enhance": ctx.body.get("enhance", "true"),
            "safe": ctx.body.get("enhance", "false"),
        }
        if image := ctx.body.get("image", None):
            data["image"] = image

        async for attempt in self._resources.get_retying(
            self.max_retries, 
            self.wait_time, 
            [rnet.exceptions.StatusError, rnet.exceptions.TimeoutError, AssertionError]
        ):
            try:
                async with attempt as api_key:
                    if api_key is None:
                        raise error.WorkerOverloadError("No API keys available")

                    headers = self.headers.copy()
                    if api_key:
                        headers["Authorization"] = f"Bearer {api_key}"

                    data["nologo"] = str(bool(api_key))

                    async with self.client() as client:
                        async with await client.get(
                            f"https://image.pollinations.ai/prompt/{prompt}?{urllib.parse.urlencode(data)}",
                            json=ctx.body,
                            headers=headers,
                        ) as response:
                            assert isinstance(response, rnet.Response)
                            assert response.ok, (
                                f"ERROR: {response.status} {await response.text()}"
                            )

                            binary = await response.bytes()
                            return context.Image(
                                type="image", content=binary, mime_type="image/jpeg"
                            )
            except resources.NoMoreResourceError as e:
                raise error.WorkerOverloadError("No API keys available") from e
