import typing
import dataclasses

@dataclasses.dataclass
class Context:
    headers: dict[str, str]
    body: dict[str, typing.Any]
    type: typing.Literal["text", "image", "audio", "embedding"]
    response: str | bytes | list[float] | int | typing.AsyncGenerator[str | bytes, None] = None
    response_headers: dict[str, str] = {}
    metadata: dict[str, typing.Any] = {}

@dataclasses.dataclass
class Response:
    status_code: int
    headers: dict[str, str]
    body: str | dict[str, typing.Any] | typing.AsyncGenerator[str | bytes, None]
