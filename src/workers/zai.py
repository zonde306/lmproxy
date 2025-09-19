import time
import math
import uuid
import typing
import datetime
import proxies
import error
from . import openai
import rnet

class ZaiWorker(openai.OpenAiWorker):
    def __init__(
        self, settings: dict[str, typing.Any], proxies: proxies.ProxyFactory
    ) -> None:
        settings.setdefault("completions_url", "https://chat.z.ai/api/chat/completions")
        settings.setdefault("streaming", True)
        super().__init__(settings, proxies)
        self.headers = {
            "Referer": "https://chat.z.ai",
            "X-FE-Version": "prod-fe-1.0.70",
        }
    
    async def models(self) -> list[str]:
        return [ "GLM-4.5", "GLM-4.5-thinking", "GLM-4.5-search", "GLM-4.5-search-thinking" ]
    
    async def create_token(self):
        async with self.client() as client:
            async with await client.get("https://chat.z.ai/api/v1/auths/") as response:
                assert isinstance(response, rnet.Response)
                assert response.ok, f"Failed to create token: {response.status} {await response.text()}"
                data = await response.json()
                return data["token"]
    
    async def _process_payload(self,
            headers: dict[str, str],
            body: dict[str, typing.Any],
            api_key: str,
            streaming: bool,
        ) -> None:
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        else:
            headers["Authorization"] = f"Bearer {await self.create_token()}"
        
        model = body.get("model", "GLM-4.5")

        body.update({
            "stream": streaming,
            "model": "0727-360B-API",
            "chat_id": str(uuid.uuid4()),
            "id": str(uuid.uuid4()),
            "params": {},
            "features": {
                "enable_thinking": "-thinking" in model,
            },
            "background_tasks": {
                "title_generation": False,
                "tags_generation": False,
            },
            "model_item": {
                "id": "0727-360B-API",
                "name": "GLM-4.5",
                "owned_by": "openai"
            },
            "variables": {
                "{{USER_NAME}}": f"Guest-{int(time.time())}",
                "{{USER_LOCATION}}": "Unknown",
                "{{CURRENT_DATETIME}}": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "{{CURRENT_DATE}}": datetime.datetime.now().strftime("%Y-%m-%d"),
                "{{CURRENT_TIMEZONE}}": "Asia/Shanghai",
                "{{CURRENT_TIME}}": datetime.datetime.now().strftime("%H:%M:%S"),
                "{{CURRENT_WEEKDAY}}": datetime.datetime.now().strftime("%A"),
                "{{USER_LANGUAGE}}": "zh-CN",
            },
            "mcp_servers": [ "deep-web-search" ] if "-search" in model else []
        })
    
    async def _get_content(self, data: dict[str, typing.Any]) -> tuple[str | None, str | None]:
        err = data.get("error") or data.get("data", {}).get("error") or data.get("data", {}).get("inner", {}).get("error")
        if err:
            raise error.WorkerOverloadError(f"z.ai ERROR: {err}")
        
        content = data.get("data", {})
        text = content.get("delta_content", None)
        if not text:
            return [ None, None ]
        
        if content.get("phase", None) == "thinking":
            return [ None, text ]
        
        return [ text, None ]
