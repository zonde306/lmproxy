import typing
import dataclasses

Text = typing.TypeVar("Text", str, typing.AsyncGenerator[str, None])
Image = typing.TypeVar("Image", bytes, tuple[bytes, str])
Embedding = typing.TypeVar("Embedding", list[float])
Audio = typing.TypeVar("Audio", bytes, typing.AsyncGenerator[bytes, None])
CountTokens = typing.TypeVar("CountTokens", int)
Video = typing.TypeVar("Audio", bytes, typing.AsyncGenerator[bytes, None])

@dataclasses.dataclass
class Context:
    headers: dict[str, str]
    body: dict[str, typing.Any]
    type: typing.Literal["text", "image", "audio", "embedding", "video"]
    response: Text | Image | Embedding | Audio | CountTokens | Video
    response_headers: dict[str, str] = {}
    metadata: dict[str, typing.Any] = {}

@dataclasses.dataclass
class Response:
    status_code: int
    headers: dict[str, str]
    body: Text | Image | Embedding | Audio | CountTokens | Video
