import logging
import contextlib
import context


class WorkerError(Exception): ...


class WorkerOverloadError(WorkerError): ...


class WorkerNoAvaliableError(WorkerError): ...

class WorkerUnsupportedError(WorkerError): ...


class TerminationRequest(Exception):
    def __init__(self, response: context.Response) -> None:
        self.response = response

@contextlib.contextmanager
def worker_handler(ctx: context.Context, logger: logging.Logger, worker: str = ""):
    try:
        yield
    except (WorkerError, NotImplementedError, AssertionError) as e:
        logger.warning(f"{worker} unavaliable: {e} for model {ctx.body.get('model')}", extra={"context": ctx})
    except Exception as e:
        logger.critical(f"{worker} error: {e} for model {ctx.body.get('model')}", exc_info=True, extra={"context": ctx})
        raise
