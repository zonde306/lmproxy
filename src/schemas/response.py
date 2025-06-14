import typing

class Response:
    def __init__(self, body : str | dict | bytes | list | typing.AsyncGenerator,
                 status_code : int = 200, headers : dict[str, str] = {}):
        self.status_code = status_code
        self.headers = headers
        self.body = body

class ErrorResponse(Response, Exception):
    ...

class ClientError(ErrorResponse):
    def __init__(self, message: str, status_code: int = 400, headers : dict[str, str] = {}):
        super().__init__(message, status_code, headers)

class ServerError(ErrorResponse):
    def __init__(self, message: str, status_code: int = 500, headers : dict[str, str] = {}):
        super().__init__(message, status_code, headers)
