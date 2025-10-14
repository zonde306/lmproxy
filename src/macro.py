import re
import logging
import inspect
from typing import Dict, Callable
import cache

logger = logging.getLogger(__name__)

# 1. 宏注册表
MACRO_REGISTRY: Dict[str, Callable] = {}

# 2. @macro 装饰器
def macro(name: str) -> Callable:
    """
    一个装饰器，用于将一个函数注册为指定名称的宏。
    """
    def decorator(func: Callable) -> Callable:
        if name in MACRO_REGISTRY:
            print(f"警告：宏 '{name}' 已被重定义。")
        MACRO_REGISTRY[name] = func
        return func
    return decorator

async def _execute_macro(macro_name: str, raw_content: str, /, **kwargs) -> str:
    """
    内部函数，用于查找、解析参数、绑定并执行宏。
    """
    if macro_name not in MACRO_REGISTRY:
        return f"{{{{{raw_content}}}}}"

    func = MACRO_REGISTRY[macro_name]

    try:
        # --- 参数解析更新 ---
        # 使用正则表达式分割参数，忽略被转义的'|' (即 '\|')
        # (?<!\\) 是一个负向先行断言，表示'|'前面不能是'\'
        raw_args_list = re.split(r'(?<!\\)\|', raw_content)
        
        # 第一个部分是宏名称，其余是参数
        # 移除宏名称部分，我们已经有了
        raw_args = raw_args_list[1:]
        
        # 清理参数：去除首尾空格，并将转义字符还原
        # '\|' -> '|'
        # '\\' -> '\'
        args = [
            arg.strip().replace(r'\|', '|').replace(r'\\', '\\')
            for arg in raw_args
        ]
        # --- 参数解析结束 ---

        sig = cache.inspect_signature(func)
        params = list(sig.parameters.values())
        accepts_kwargs = any(
            param.kind == inspect.Parameter.VAR_KEYWORD 
            for param in sig.parameters.values()
        )
        if not accepts_kwargs:
            kwargs = {
                k: v for k, v in kwargs.items() 
                if k in sig.parameters
            }

        bound_args = []
        for i, param in enumerate(params):
            if i < len(args):
                arg_str = args[i]
                if param.annotation is not inspect.Parameter.empty and param.annotation is not str:
                    try:
                        coerced_arg = param.annotation(arg_str)
                        bound_args.append(coerced_arg)
                    except (ValueError, TypeError):
                        print(f"警告：无法将宏 '{macro_name}' 的参数 '{arg_str}' 转换为类型 {param.annotation.__name__}。")
                        bound_args.append(arg_str)
                else:
                    bound_args.append(arg_str)
            elif param.default is inspect.Parameter.empty:
                raise TypeError(f"宏 '{macro_name}' 缺少必需的位置参数: '{param.name}'")

        if inspect.iscoroutinefunction(func):
            result = await func(*bound_args, **kwargs)
        else:
            result = func(*bound_args, **kwargs)
        
        return str(result)

    except Exception:
        logger.error(f"执行宏 '{macro_name}' 时发生错误：", exc_info=True)
        return f"{{{{{raw_content}}}}}"


async def render(template_string: str, /, **kwargs) -> str:
    """
    渲染模板字符串，查找并替换所有 {{...}} 宏。
    """
    pattern = re.compile(r"\{\{([^}]+)\}\}")
    
    result_parts = []
    last_end = 0

    for match in pattern.finditer(template_string):
        result_parts.append(template_string[last_end:match.start()])

        # content现在是 "macroname|arg1|arg2..." 的完整字符串
        full_content = match.group(1).strip()
        
        # 提取宏名称
        # 我们不能简单地用 split('|') 了，因为'|'可能被转义
        # 先找到第一个未被转义的'|'的位置
        first_separator_match = re.search(r'(?<!\\)\|', full_content)
        if first_separator_match:
            macro_name = full_content[:first_separator_match.start()].strip()
        else:
            macro_name = full_content.strip()

        # 异步执行宏并获取替换值
        replacement = await _execute_macro(macro_name, full_content, **kwargs)
        result_parts.append(replacement)

        last_end = match.end()

    result_parts.append(template_string[last_end:])

    return "".join(result_parts)
