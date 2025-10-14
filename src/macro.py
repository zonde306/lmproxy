import re
import logging
import inspect
from typing import Dict, Callable
import cache

logger = logging.getLogger(__name__)

MACRO_REGISTRY: Dict[str, Callable] = {}

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
        raw_args_list = re.split(r'(?<!\\)\|', raw_content)
        raw_args = raw_args_list[1:]
        args = [
            arg.strip().replace(r'\|', '|').replace(r'\\', '\\')
            for arg in raw_args
        ]

        # inspect.signature with cache
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

async def render(template_string: str, max_iterations: int = 9, /, **kwargs) -> str:
    """
    渲染模板字符串，通过迭代方式处理嵌套宏。

    它会重复扫描字符串，每次都查找并替换最内层的宏，
    直到没有更多的宏可以被替换或者达到最大迭代次数。

    Args:
        template_string: 包含宏的模板字符串。
        max_iterations: 为防止无限循环而设置的最大渲染次数。
        **kwargs: 传递给每个宏的上下文关键字参数。

    Returns:
        渲染完成的字符串。
    """
    # 这个正则表达式只匹配最内层的宏，即 {{...}} 中不含 { 或 } 的部分
    pattern = re.compile(r"\{\{([^}{]+)\}\}")
    
    # 我们将对字符串进行多次处理，直到没有变化为止
    current_template = template_string
    
    for i in range(max_iterations):
        # 在当前模板中查找第一个最内层的宏
        match = pattern.search(current_template)
        
        # 如果找不到任何匹配项，说明所有宏都已渲染，可以退出循环
        if not match:
            break

        # 提取宏的完整内容，例如 "macroname|arg1|arg2"
        full_content = match.group(1).strip()
        
        # 提取宏名称 (处理参数中可能存在的转义'|')
        first_separator_match = re.search(r'(?<!\\)\|', full_content)
        if first_separator_match:
            macro_name = full_content[:first_separator_match.start()].strip()
        else:
            macro_name = full_content.strip()

        # 异步执行宏并获取替换值
        replacement = await _execute_macro(macro_name, full_content, **kwargs)
        
        # 将渲染后的内容替换回模板字符串
        # 我们通过拼接来精确替换，避免 string.replace() 可能导致的意外替换
        start, end = match.span()
        current_template = current_template[:start] + replacement + current_template[end:]
    else:
        # 如果循环因达到 max_iterations 而结束，发出警告
        logger.warning(
            f"宏渲染在达到 {max_iterations} 次迭代上限后停止。"
            "模板中可能仍有未解析的宏，或者存在无限循环。"
        )
    
    return current_template
