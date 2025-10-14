import json
import logging
import asyncio
import inspect
from enum import Enum
from typing import Any, Callable, Dict, List, get_origin, get_args, Literal

logger = logging.getLogger(__name__)

# 全局变量
OPENAI_TOOLS = []
AVAILABLE_FUNCTIONS = {}


async def execute_tool_calls(
    tool_calls: List[Dict[str, Any]], available_functions: Dict[str, Callable]
) -> List[Dict[str, Any]]:
    """
    异步并发执行 OpenAI 返回的 tool_calls，生成工具响应消息。

    参数:
        tool_calls: 来自 OpenAI 响应 message.tool_calls 的列表
        available_functions: 可用函数字典 {函数名: 函数对象}（支持同步和异步函数）

    返回:
        List[Dict]: 每个元素是符合 OpenAI 格式的工具响应消息
    """

    async def call_single_tool(tool_call: Dict[str, Any]) -> Dict[str, Any]:
        function_name = tool_call["function"]["name"]
        function_to_call = available_functions.get(function_name)

        if not function_to_call:
            response_content = f"Error: Function '{function_name}' not found."
        else:
            try:
                # 解析参数
                function_args = json.loads(tool_call["function"]["arguments"])

                # 判断是否为异步函数
                if inspect.iscoroutinefunction(function_to_call):
                    function_response = await function_to_call(**function_args)
                else:
                    function_response = function_to_call(**function_args)

                # 序列化为 JSON 字符串
                response_content = json.dumps(
                    function_response, ensure_ascii=False, default=str
                )

            except Exception as e:
                response_content = f"Error: {str(e)}"
                logger.error(f"工具调用失败: {tool_call}", exc_info=True)

        return {
            "tool_call_id": tool_call.get("id", None),
            "role": "tool",
            "name": function_name,
            "content": response_content,
        }

    if not all([ available_functions.get(x["function"]["name"], None) for x in tool_calls ]):
        return []

    # 并发执行所有工具调用
    tasks = [call_single_tool(tc) for tc in tool_calls]
    tool_messages = await asyncio.gather(*tasks, return_exceptions=False)

    return tool_messages


def _get_json_type(py_type):
    """将 Python 类型映射为 JSON Schema 类型"""
    if py_type is str:
        return "string"
    elif py_type is int:
        return "integer"
    elif py_type is float:
        return "number"
    elif py_type is bool:
        return "boolean"
    elif py_type is dict:
        return "object"
    elif py_type is list or get_origin(py_type) is list:
        return "array"
    elif py_type is None or py_type is type(None):
        return "null"
    else:
        return "string"


def tooldef(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    装饰器：将函数转换为 OpenAI API Tools 格式，并注册到全局列表和可用函数字典。
    支持同步和异步函数。
    """
    sig = inspect.signature(func)
    parameters = sig.parameters

    properties = {}
    required = []

    for name, param in parameters.items():
        if param.kind in (
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        ):
            continue

        prop = {}
        annotation = param.annotation

        if annotation is not inspect.Parameter.empty:
            prop["type"] = _get_json_type(annotation)
            if get_origin(annotation) is Literal:
                literals = get_args(annotation)
                prop["enum"] = list(literals)
            elif isinstance(annotation, type) and issubclass(annotation, Enum):
                prop["enum"] = [e.value for e in annotation]
        else:
            prop["type"] = "string"

        properties[name] = prop

        if param.default is inspect.Parameter.empty:
            required.append(name)

    function_def = {
        "name": func.__name__,
        "description": func.__doc__.strip() if func.__doc__ else "",
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }

    tool = {"type": "function", "function": function_def}

    global OPENAI_TOOLS, AVAILABLE_FUNCTIONS
    OPENAI_TOOLS.append(tool)
    AVAILABLE_FUNCTIONS[func.__name__] = func  # 同步/异步函数都支持！

    return func
