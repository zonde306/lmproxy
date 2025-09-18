import typing
import asyncio
import context
import middleware


class AttemptManager:
    def __init__(self, retrying: "Retrying", attempt_number: int):
        self.retrying = retrying
        self.attempt_number = attempt_number

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_val is None:
            # 成功，不重试，停止迭代
            self.retrying._done = True
            self.retrying.error = None
            return True  # 吞掉异常（这里无异常）

        if not isinstance(exc_val, Exception):
            return False

        self.retrying.error = exc_val

        # 检查是否停止
        if await self.retrying.middleware.process_error(
            self.retrying.context, exc_val, self.attempt_number
        ):
            self.retrying._done = True
            return False  # 不吞异常，让其抛出

        # 检查是否重试
        if not await self.retrying.retry_if(exc_val):
            self.retrying._done = True
            return False  # 不重试，抛出异常

        # 否则继续下一次迭代（重试）
        await asyncio.sleep(self.retrying.settings.get("wait_time", 0))
        return True  # 吞掉异常，继续循环

    @property
    def error(self):
        return self.retrying.error

    @property
    def context(self):
        return self.retrying.context


class Retrying:
    def __init__(
        self,
        settings: dict[str, typing.Any],
        middleware: middleware.MiddlewareManager,
        ctx: context.Context,
    ) -> None:
        self.settings = settings
        self.middleware = middleware
        self.context = ctx
        self._done = False
        self._attempt_number = 0
        self.error: Exception | None = None

    def __aiter__(self) -> typing.AsyncIterator[AttemptManager]:
        self._done = False
        self._attempt_number = 0
        return self

    async def __anext__(self) -> AttemptManager:
        if self._done:
            raise StopAsyncIteration

        self._attempt_number += 1
        return AttemptManager(self, self._attempt_number)

    async def retry_if(self, _: Exception):
        return self._attempt_number < self.settings.get("max_attempts", 3)


class RetryFactory:
    def __init__(
        self, settings: dict[str, typing.Any], middleware: middleware.MiddlewareManager
    ) -> None:
        self.settings = settings
        self.middleware = middleware

    def create(self, ctx: context.Context) -> Retrying:
        return Retrying(self.settings, self.middleware, ctx)

    def __call__(self, ctx: context.Context) -> Retrying:
        return self.create(ctx)
