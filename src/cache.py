import time
import asyncio
import inspect
import functools
from typing import Any, Callable, Dict, Tuple

def ttl_cache(seconds: int):
    """
    支持同步和异步函数的时间缓存装饰器（TTL Cache）
    缓存 n 秒后自动过期

    :param seconds: 缓存过期时间（秒）
    :return: 装饰器
    """
    def decorator(func: Callable) -> Callable:
        cache: Dict[Tuple, Dict[str, Any]] = {}  # {key: {"result": ..., "timestamp": ...}}

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            try:
                key = (args, tuple(sorted(kwargs.items())))
            except TypeError:
                # 参数不可哈希，跳过缓存
                return await func(*args, **kwargs)

            current_time = time.time()

            # 检查缓存
            if key in cache:
                cached = cache[key]
                if current_time - cached["timestamp"] < seconds:
                    return cached["result"]
                else:
                    del cache[key]

            # 调用异步函数并缓存
            result = await func(*args, **kwargs)
            cache[key] = {
                "result": result,
                "timestamp": current_time
            }
            return result

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            try:
                key = (args, tuple(sorted(kwargs.items())))
            except TypeError:
                return func(*args, **kwargs)

            current_time = time.time()

            if key in cache:
                cached = cache[key]
                if current_time - cached["timestamp"] < seconds:
                    return cached["result"]
                else:
                    del cache[key]

            result = func(*args, **kwargs)
            cache[key] = {
                "result": result,
                "timestamp": current_time
            }
            return result

        # 自动判断是同步还是异步函数
        if asyncio.iscoroutinefunction(func):
            wrapper = async_wrapper
        else:
            wrapper = sync_wrapper

        # 添加清除缓存方法
        def clear_cache():
            cache.clear()

        wrapper.clear_cache = clear_cache
        return wrapper

    return decorator

inspect_signature = functools.lru_cache(maxsize=128)(inspect.signature)
