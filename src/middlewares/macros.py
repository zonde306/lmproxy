import logging
import middleware
import context
import macro
import loader

logger = logging.getLogger(__name__)

class MacroMiddleware(middleware.Middleware):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._setup_macros(self.settings.get("macros", {}))
    
    def _setup_macros(self, defines: dict[str, str]):
        for name, func_name in defines.items():
            impl = loader.get_object(func_name)
            if not impl:
                logger.warning(f"无法加载宏 {name} 的实现 {func_name}")
                continue
            
            macro.macro(name)(impl)

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
