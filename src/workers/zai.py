import time
import uuid
import typing
import datetime
import proxies
import error
import context
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
            "X-FE-Version": "prod-fe-1.0.79",
        }
    
    async def models(self) -> list[str]:
        return [
            "GLM-4.5",
            "GLM-4.5-thinking",
            "GLM-4.5-search",
            "GLM-4.5-search-thinking",
            "GLM-4.5-Air",
            "GLM-4.5-Air-thinking",
            "GLM-4.5-Air-search",
            "GLM-4.5-Air-search-thinking",
            "GLM-4.5v",
            "GLM-4.5v-thinking",
        ]
    
    async def supports_model(self, model: str, type: str) -> bool:
        return type == "text" and model in {
            "GLM-4.5",
            "GLM-4.5-thinking",
            "GLM-4.5-search",
            "GLM-4.5-search-thinking",
            "GLM-4.5-Air",
            "GLM-4.5-Air-thinking",
            "GLM-4.5-Air-search",
            "GLM-4.5-Air-search-thinking",
            "GLM-4.5v",
            "GLM-4.5v-thinking",
        }
    
    async def create_token(self):
        async with self.client() as client:
            async with await client.get("https://chat.z.ai/api/v1/auths/") as response:
                assert isinstance(response, rnet.Response)
                assert response.ok, f"Failed to create token: {response.status} {await response.text()}"
                data = await response.json()
                return data["token"]
    
    async def _prepare_payload(self,
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

        upstream_model = "0727-360B-API"
        upstream_name = "GLM-4.5"
        if "-Air" in model:
            upstream_model = "0727-106B-API"
            upstream_name = "GLM-4.5-Air"
        elif "5v" in model:
            upstream_model = "glm-4.5v"
            upstream_name = "GLM-4.5v"

        body.update({
            "stream": streaming,
            "model": upstream_model,
            "chat_id": str(uuid.uuid4()),
            "id": str(uuid.uuid4()),
            "params": {},
            "features": {
                "enable_thinking": "-thinking" in model,
                "web_search": "-search" in model,
                "auto_web_search": "-search" in model,
                "preview_mode": False,
                "flags": [],
                "features": [],
            },
            "background_tasks": {
                "title_generation": False,
                "tags_generation": False,
            },
            "model_item": {
                "id": upstream_model,
                "name": upstream_name,
                "owned_by": "z.ai"
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

        headers["Referer"] = f"https://chat.z.ai/c/{body['chat_id']}"

        for message in body.get("messages", []):
            if message.get("role", "") == "system":
                message["role"] = "user"
    
    async def _parse_response(self, data: dict[str, typing.Any]) -> context.Text:
        err = data.get("error") or data.get("data", {}).get("error") or data.get("data", {}).get("inner", {}).get("error")
        if err:
            raise error.WorkerOverloadError(f"zAI ERROR: {err}")
        
        inner = data.get("data", {})
        delta = inner.get("delta_content", "")

        if not delta:
            return context.Text(type="text", content=None, reasoning_content=None)
        
        if inner.get("phase", None) == "thinking":
            return context.Text(type="text", content=None, reasoning_content=delta)
        
        if inner.get("phase", None) == "answer":
            if edit := inner.get("edit_content", ""):
                delta += edit + "\n\n" + delta
            return context.Text(type="text", content=delta, reasoning_content=None)
        
        return context.Text(type="text", content=delta, reasoning_content=None)
