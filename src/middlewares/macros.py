import logging
import middleware
import context
import macro

logger = logging.getLogger(__name__)

class MacroMiddleware(middleware.Middleware):
    async def process_request(self, ctx: context.Context) -> None:
        if ctx.type != "text":
            return
        
        for message in ctx.body["messages"]:
            if "{{" not in message["content"]:
                continue
            
            if isinstance(message["content"], str):
                message["content"] = await macro.render(message["content"])
            elif isinstance(message["content"], list):
                for content_part in message["content"]:
                    if content_part["type"] == "text":
                        content_part["text"] = await macro.render(content_part["text"])
