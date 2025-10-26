import re
import logging
import middleware
import context

logger = logging.getLogger(__name__)

class RegexMiddleware(middleware.Middleware):
    async def process_request(self, ctx: context.Context) -> None:
        if ctx.type != "text":
            return
        
        size = len(ctx.body["messages"])
        for i, message in enumerate(ctx.body["messages"]):
            if isinstance(message.get("content", None), str):
                message["content"] = self.apply_regex(message["content"], message["role"], size - i - 1)
            elif isinstance(message.get("content", None), list):
                for part in message["content"]:
                    if part["type"] == "text":
                        part["text"] = self.apply_regex(part["text"], message["role"], size - i - 1)
    
    def apply_regex(self, content: str, role: str, depth: int) -> str:
        for regex in self.settings.get("regexp", []):
            match_role = regex.get("role", "any")
            if match_role != "any" and match_role != role:
                continue
            
            min_depth = regex.get("min_depth", None)
            if min_depth is not None and depth > min_depth:
                continue
            
            max_depth = regex.get("max_depth", None)
            if max_depth is not None and depth < max_depth:
                continue

            count = regex.get("count", 0)

            flags = 0
            if regex.get("case_insensitive", False):
                flags |= re.I
            if regex.get("multiline", False):
                flags |= re.M
            if regex.get("dot_all", False):
                flags |= re.S
            if regex.get("unicode", False):
                flags |= re.U
            if regex.get("verbose", False):
                flags |= re.X

            content = re.sub(regex["pattern"], regex["replacement"], content, count, flags)
            
        return content
