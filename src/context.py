import typing
import dataclasses

Text = typing.TypeVar("Text", str, typing.AsyncGenerator[str, None])
Image = typing.TypeVar("Image", bytes, tuple[bytes, str])
Embedding = typing.TypeVar("Embedding", bound=list[float])
Audio = typing.TypeVar("Audio", bytes, typing.AsyncGenerator[bytes, None])
CountTokens = typing.TypeVar("CountTokens", bound=int)
Video = typing.TypeVar("Audio", bytes, typing.AsyncGenerator[bytes, None])


@dataclasses.dataclass
class Context:
    headers: dict[str, str]
    body: dict[str, typing.Any]
    type: typing.Literal["text", "image", "audio", "embedding", "video"]
    response: Text | Image | Embedding | Audio | CountTokens | Video | None = None
    status_code: int = 200
    response_headers: dict[str, str] = dataclasses.field(default_factory=dict)
    metadata: dict[str, typing.Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class Response:
    body: Text | Image | Embedding | Audio | CountTokens | Video | dict[str, typing.Any]
    status_code: int = 200
    headers: dict[str, str] = dataclasses.field(default_factory=dict)
