import context

class WorkerError(Exception):
    ...

class WorkerOverloadError(WorkerError):
    ...


class WorkerNoAvaliableError(WorkerError):
    ...

class TerminationRequest(Exception):
    def __init__(self, response: context.Response) -> None:
        self.response = response
