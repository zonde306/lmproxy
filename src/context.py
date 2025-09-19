import typing
import dataclasses

Text = typing.TypeVar(
    "Text", tuple[str, str], typing.AsyncGenerator[tuple[str, str], None]
)  # [content, reasoning]
Image = typing.TypeVar("Image", bound=tuple[bytes, str])  # [image, mime_type]
Embedding = typing.TypeVar("Embedding", bound=list[float])  # vector
Audio = typing.TypeVar(
    "Audio", tuple[bytes, str], typing.AsyncGenerator[tuple[bytes, str], None]
)  # [audio, mime_type]
CountTokens = typing.TypeVar("CountTokens", bound=int)  # tokens
Video = typing.TypeVar(
    "Audio", tuple[bytes, str], typing.AsyncGenerator[bytes, None]
)  # [video, mime_type]


@dataclasses.dataclass
class Response:
    body: Text | Image | Embedding | Audio | CountTokens | Video | dict[str, typing.Any]
    status_code: int = 200
    headers: dict[str, str] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class Context:
    headers: dict[str, str]
    body: dict[str, typing.Any]
    type: typing.Literal["text", "image", "audio", "embedding", "video"]
    response: Text | Image | Embedding | Audio | CountTokens | Video | None = None
    status_code: int = 200
    response_headers: dict[str, str] = dataclasses.field(default_factory=dict)
    metadata: dict[str, typing.Any] = dataclasses.field(default_factory=dict)

    @property
    def task_id(self) -> str:
        return self.metadata.get("task_id", "")

    @property
    def to_response(self) -> Response | None:
        if not self.response:
            return None
        return Response(self.response, self.status_code, self.response_headers)
    
    @property
    def model(self) -> str:
        return self.body.get("model", "")
    
    def payload(self, aliases: dict[str, str] = {}):
        body = self.body.copy()
        model = body.get("model", None)
        if model in aliases:
            body["model"] = aliases[model]
        
        return body
    
    @property
    def stream(self) -> bool:
        return self.body.get("stream", False)
