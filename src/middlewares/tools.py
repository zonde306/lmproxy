import re
import json
import typing
import logging
import middleware
import context
import tool
import error

logger = logging.getLogger(__name__)

class ToolCallMiddleware(middleware.Middleware):
    async def process_request(self, ctx: context.Context) -> bool | None:
        if ctx.body.get("tools", None):
            ctx.body["tools"] = []
        
        aleady_exists = set([ x["function"]["name"] for x in ctx.body["tools"] ])
        ctx.body["tools"].extend([ x for x in tool.OPENAI_TOOLS if x["function"]["name"] not in aleady_exists ])
        logger.info(f"tools definetions: {ctx.body['tools']}")

    async def process_response(self, ctx: context.Context) -> bool | None:
        if ctx.type != "text" or ctx.stream:
            return
        
        if not isinstance(ctx.response, dict) or ctx.response.get("type", None) != "text":
            return
        
        tool_calls = self.get_tool_calls(ctx)
        if not tool_calls:
            return
        
        results = await tool.execute_tool_calls(tool_calls, tool.AVAILABLE_FUNCTIONS)
        ctx.body["messages"].extend(results)

        response = await self.engine.process_generate(ctx, self.engine.workers.generate_text)
        ctx.response = response.body
        ctx.status_code = response.status_code
        ctx.response_headers = response.headers

        return False
    
    async def process_chunk(self, ctx: context.Context, chunk: context.DeltaType) -> bool | None:
        if ctx.type != "text" or not ctx.stream or chunk["type"] != "text":
            return
        
        tool_calls = self.get_tool_calls(ctx)
        if not tool_calls:
            if "<tool_calls>" in ctx.metadata.get("stream_content", ""):
                return False
            return
        
        results = await tool.execute_tool_calls(tool_calls, tool.AVAILABLE_FUNCTIONS)
        ctx.body["messages"].extend(results)

        response = await self.engine.process_generate(ctx, self.engine.workers.generate_text)
        ctx.response = response.body
        ctx.status_code = response.status_code
        ctx.response_headers = response.headers

        raise error.TerminationRequest(response)
    
    def get_tool_calls(self, ctx: context.Context) -> list[dict[str, typing.Any]]:
        tool_calls = ctx.response.get("tool_calls", [])
        if tool_calls:
            return tool_calls
        
        content = ctx.response.get("content", "")
        if match := re.search(r"<tool_calls>([\s\S]*?)</tool_calls>", content):
            return json.loads(match.group(1))
        
        content = ctx.metadata.get("stream_content", "")
        if match := re.search(r"<tool_calls>([\s\S]*?)</tool_calls>", content):
            return json.loads(match.group(1))
        
        return []

        



