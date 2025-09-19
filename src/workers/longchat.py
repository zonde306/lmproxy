import typing
import proxies
from . import openai

class LongchatWorker(openai.OpenAiWorker):
    def __init__(
        self, settings: dict[str, typing.Any], proxies: proxies.ProxyFactory
    ) -> None:
        settings.setdefault("completions_url", "https://longcat.chat/api/v1/chat-completion-oversea")
        settings.setdefault("streaming", True)
        super().__init__(settings, proxies)
        self.headers = {
            "Referer": "https://longcat.chat/t"
        }
    
    async def models(self) -> list[str]:
        return [ "longcat-flash", "longcat-flash-search" ]
    
    async def _process_payload(self,
            headers: dict[str, str],
            body: dict[str, typing.Any],
            api_key: str,
            streaming: bool,
        ) -> None:
        body["stream"] = streaming

        if body["model"] == "longcat-flash-search":
            body["model"] = "longcat-flash"
            body["searchEnabled"] = 1
        else:
            body["searchEnabled"] = 0
        
        body["reasonEnabled"] = 0
        body["regenerate"] = 0

        content = ""
        for message in body["messages"]:
            if content:
                content += "\n\n"
            content += f"{message['role']}: {message['content']}"
        
        body["content"] = content

        if api_key:
            headers["Cookie"] = api_key
    
    async def _get_content(self, data: dict[str, typing.Any]) -> tuple[str | None, str | None]:
        text = data["choices"][0].get("delta", {}).get("content", None) or\
            data["choices"][0].get("message", {}).get("content", None)
        reasoning = data["choices"][0].get("delta", {}).get("reasoningContent", None) or \
            data["choices"][0].get("message", {}).get("reasoningContent", None)
        return [ text, reasoning ]

