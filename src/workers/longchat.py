import typing
import logging
import proxies
import context
from . import openai

logger = logging.getLogger(__name__)


class LongchatWorker(openai.OpenAiWorker):
    def __init__(
        self, settings: dict[str, typing.Any], proxies: proxies.ProxyFactory
    ) -> None:
        settings.setdefault(
            "completions_url", "https://longcat.chat/api/v1/chat-completion-oversea"
        )
        settings.setdefault("streaming", True)
        super().__init__(settings, proxies)
        self.headers = {"Referer": "https://longcat.chat/t"}

    async def models(self) -> list[str]:
        return [
            "longcat-flash",
            "longcat-flash-search",
            "longcat-flash-thinking",
            "longcat-flash-thinking-search",
        ]

    async def _prepare_payload(
        self,
        headers: dict[str, str],
        body: dict[str, typing.Any],
        api_key: str,
        streaming: bool,
        ctx: context.Context,
    ) -> None:
        body["stream"] = streaming

        body["searchEnabled"] = int("-search" in body["model"])
        body["reasonEnabled"] = int("-thinking" in body["model"])

        body["regenerate"] = 0
        body.pop("model")

        content = ""
        for message in body["messages"]:
            if content:
                content += "\n\n"
            content += f"{message['role']}: {message['content']}"

        body["content"] = content

        if api_key:
            headers["Cookie"] = f"passport_token_key={api_key}"

    async def _parse_response(
        self, data: dict[str, typing.Any], ctx: context.Context
    ) -> context.Text:
        if choices := data.get("choices", []):
            text = choices[0].get("delta", {}).get("content", None) or choices[0].get(
                "message", {}
            ).get("content", None)
            reasoning = choices[0].get("delta", {}).get(
                "reasoningContent", None
            ) or choices[0].get("message", {}).get("reasoningContent", None)
            tool_calls = choices[0].get("functionCall", None)

            return context.Text(
                type="text",
                content=text,
                reasoning_content=reasoning,
                tool_calls=tool_calls,
            )

        if event := data.get("event", {}):
            type = event.get("type")
            content = event.get("content")
            usage = event.get("usage")

            if usage:
                ctx.metadata["usage"] = usage

            # 移除重复的消息
            if isinstance(content, str):
                last_length = ctx.metadata.get(f"last_length_{type}", 0)
                if len(content) >= last_length:
                    ctx.metadata[f"last_length_{type}"] = len(content)
                    content = content[last_length:]

                if type == "think":
                    return context.Text(
                        type="text", content=None, reasoning_content=content, tool_calls=None
                    )

                return context.Text(
                    type="text", content=content, reasoning_content=None, tool_calls=None
                )

        logger.error(f"Unknown longchat response: {data}")
        return context.Text(type="text", content=None, reasoning_content=None, tool_calls=None)
