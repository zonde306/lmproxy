import random
import typing
import urllib.parse
import proxies
import context
import error
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

    async def models(self) -> list[str]:
        async with self.client() as client:
            async with await client.get(
                "https://image.pollinations.ai/models"
            ) as response:
                self.image_models = await response.json()
            async with await client.get(
                "https://text.pollinations.ai/models"
            ) as response:
                data = await response.json()
                self.text_models = [
                    x["name"] for x in data
                ]

        return self.image_models + self.text_models

    async def generate_text(self, context: context.Context) -> context.Text:
        if context.body.get("model") not in self.text_models:
            raise error.WorkerUnsupportedError(
                f"Model {context.body['model']} not available for text generation"
            )

        return await super().generate_text(context)

    async def generate_image(self, context: context.Context) -> context.Image:
        if context.body.get("model") not in self.image_models:
            raise error.WorkerUnsupportedError(
                f"Model {context.body['model']} not available for image generation"
            )
        
        prompt = urllib.parse.quote(context.body.get("prompt", ""), safe="")
        data = {
            "model": context.body.get("model", "flux"),
            "seed": context.body.get("seed", random.randint(0, 0xFFFFFFFF)),
            "width": context.body.get("width", 1024),
            "height": context.body.get("height", 1024),
            "enhance": context.body.get("enhance", "true"),
            "safe": context.body.get("enhance", "false"),
        }
        if image := context.body.get("image", None):
            data["image"] = image
        
        async with self._resources.get() as api_key:
            if api_key is None:
                raise error.WorkerOverloadError("No API keys available")

            headers = self.headers.copy()
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            
            data["nologo"] = str(bool(api_key))

            async with self.client() as client:
                async with await client.get(
                    f"https://image.pollinations.ai/prompt/{prompt}?{urllib.parse.urlencode(data)}", json=context.body, headers=headers
                ) as response:
                    assert isinstance(response, rnet.Response)
                    assert response.ok, f"ERROR: {response.status} {await response.text()}"
                    
                    binary = await response.bytes()
                    return [ binary, "image/jpeg" ]

