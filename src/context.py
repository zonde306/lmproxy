import copy
import typing
import dataclasses


class Text(typing.TypedDict):
    type: typing.Literal["text"] = "text"
    content: str | None = None
    reasoning_content: str | None = None
    tool_calls: list[dict[str, typing.Any]] | None = None


class Image(typing.TypedDict):
    type: typing.Literal["image"] = "image"
    content: bytes
    mime_type: str


class Embedding(typing.TypedDict):
    type: typing.Literal["embedding"] = "embedding"
    content: list[float]


class Audio(typing.TypedDict):
    type: typing.Literal["audio"] = "audio"
    content: bytes
    mime_type: str


class Video(typing.TypedDict):
    type: typing.Literal["video"] = "video"
    content: bytes
    mime_type: str


class CountTokens(typing.TypedDict):
    type: typing.Literal["count_tokens"] = "count_tokens"
    content: int


DeltaType = Text | Image | Embedding | Audio | Video


@dataclasses.dataclass
class Response:
    body: (
        DeltaType
        | typing.AsyncGenerator[DeltaType, None]
        | CountTokens
        | dict[str, typing.Any]
    )
    status_code: int = 200
    headers: dict[str, str] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class Context:
    headers: dict[str, str]
    body: dict[str, typing.Any]
    type: typing.Literal["text", "image", "audio", "embedding", "video"]
    response: (
        DeltaType
        | typing.AsyncGenerator[DeltaType, None]
        | CountTokens
        | dict[str, typing.Any]
        | None
    ) = None
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
        body = copy.deepcopy(self.body)
        model = body.get("model", None)
        if model in aliases:
            body["model"] = aliases[model]

        return body

    @property
    def stream(self) -> bool:
        return self.body.get("stream", False)
