
class WorkerError(Exception):
    ...

class WorkerOverloadError(WorkerError):
    ...


class WorkerNoAvaliableError(WorkerError):
    ...

