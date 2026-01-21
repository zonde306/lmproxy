import copy
import typing
import dataclasses

@dataclasses.dataclass
class Response:
    body: (
        "DeltaType"
        | typing.AsyncGenerator["DeltaType", None]
        | "CountTokens"
        | dict[str, typing.Any]
        | "Embeding"
        | list[float]
    )
    status_code: int = 200
    headers: dict[str, str] = dataclasses.field(default_factory=dict)
    metadata: dict[str, typing.Any] = dataclasses.field(default_factory=dict)

@dataclasses.dataclass
class Context:
    headers: dict[str, str]
    body: typing.Union["ChatCompletionPayload", "EmbeddingPayload"]
    type: typing.Literal["text", "image", "audio", "embedding", "video"]
    response: (
        "DeltaType"
        | typing.AsyncGenerator["DeltaType", None]
        | "CountTokens"
        | dict[str, typing.Any]
        | "Embeding"
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
        
        if isinstance(self.response, dict):
            self.response["role"] = "assistant"
        return Response(self.response, self.status_code, self.response_headers, self.metadata)

    @property
    def model(self) -> str:
        return self.body.get("model", "")

    def payload(self, settings: dict[str, typing.Any] = {}):
        """
        复制 body
        """
        body = copy.deepcopy(self.body)
        if aliases := settings.get("aliases", {}):
            model = body.get("model", None)
            if model in aliases:
                body["model"] = aliases[model]
        
        if overrides := settings.get("overrides", {}):
            for key, val in overrides.items():
                if val is None and key in body[key]:
                    del body[key]
                elif val is not None:
                    body[key] = val

        return body

    @property
    def stream(self) -> bool:
        return self.body.get("stream", False)

class BaseMessage(typing.TypedDict):
    role: str
    content: str

class SystemMessage(typing.TypedDict):
    """系统消息，用于设定助手的行为"""
    role: typing.Literal["system"]
    content: str

class UserMessage(typing.TypedDict):
    """用户消息"""
    role: typing.Literal["user"]
    content: str | list["UserContentPart"]

class ToolCallFunction(typing.TypedDict):
    """助手请求调用工具时，函数部分的具体信息"""
    name: str
    arguments: str # 通常是一个 JSON 格式的字符串

class AssistantToolCall(typing.TypedDict):
    """助手消息中的单个工具调用请求"""
    id: str
    type: typing.Literal["function"]
    function: ToolCallFunction

class AssistantMessage(typing.TypedDict, total=False):
    """助手消息。content 可以是 None，当它进行工具调用时"""
    role: typing.Literal["assistant"]
    content: typing.Optional[str] # 当 tool_calls 存在时，content 可能为 null
    tool_calls: typing.List[AssistantToolCall]

class ToolMessage(typing.TypedDict):
    """工具消息，用于返回工具调用的结果"""
    role: typing.Literal["tool"]
    content: str
    tool_call_id: str

Message = typing.Union[SystemMessage, UserMessage, AssistantMessage, ToolMessage]

JSONSchema = typing.Dict[str, typing.Any]

class FunctionDefinition(typing.TypedDict):
    """定义一个可供模型调用的函数"""
    name: str
    description: str
    parameters: JSONSchema

class Tool(typing.TypedDict):
    """定义一个工具，目前仅支持 "function" 类型"""
    type: typing.Literal["function"]
    function: FunctionDefinition

class ToolChoiceFunction(typing.TypedDict):
    """强制模型调用特定函数"""
    name: str

class SpecificToolChoice(typing.TypedDict):
    """强制模型调用特定工具（目前只有函数）"""
    type: typing.Literal["function"]
    function: ToolChoiceFunction

# tool_choice 可以是 "none", "auto", 或者一个指定的工具对象
ToolChoice = typing.Union[typing.Literal["none", "auto"], SpecificToolChoice]

class ResponseFormat(typing.TypedDict):
    """指定响应的格式，例如 JSON 模式"""
    type: typing.Literal["text", "json_object"]

class ChatCompletionPayload(typing.TypedDict, total=False):
    """
    OpenAI Chat Completions API 的主 Payload 类型定义。
    
    使用 `total=False` 意味着所有在这里定义的键都是可选的。
    必需的键 (`model`, `messages`) 在此之后单独列出，以获得更强的类型检查。
    """
    # 必需参数
    model: str
    messages: typing.List[Message]
    
    # 可选参数
    frequency_penalty: float
    logit_bias: typing.Dict[str, int]
    logprobs: bool
    top_logprobs: int
    max_tokens: int
    n: int
    presence_penalty: float
    response_format: ResponseFormat
    seed: int
    stop: typing.Union[str, typing.List[str]]
    stream: bool
    temperature: float
    top_p: float
    tools: typing.List[Tool]
    tool_choice: ToolChoice
    user: str
    reasoning_effort: typing.Literal["none", "low", "high", "medium"]

class TextContentPart(typing.TypedDict):
    """用户消息中的文本内容部分"""
    type: typing.Literal["text"]
    text: str

class ImageURL(typing.TypedDict):
    """用户消息中图片 URL 的具体定义"""
    url: str
    detail: typing.Literal["auto", "low", "high"]

class ImageContentPart(typing.TypedDict):
    """用户消息中的图片内容部分"""
    type: typing.Literal["image_url"]
    image_url: ImageURL

# 用户消息的内容可以是多种类型的组合
UserContentPart = typing.Union[TextContentPart, ImageContentPart]

class EmbeddingPayload(typing.TypedDict, total=False):
    input: str | list[str]
    model: str
    user: str | None
    dimensions: int | None


class Text(typing.TypedDict):
    role: str | None = None
    type: typing.Literal["text"] = "text"
    content: str | None = None
    reasoning_content: str | None = None
    tool_calls: list[dict[str, typing.Any]] | None = None


class Image(typing.TypedDict):
    role: str | None = None
    type: typing.Literal["image"] = "image"
    content: bytes
    mime_type: str


class Embedding(typing.TypedDict):
    role: str | None = None
    type: typing.Literal["embedding"] = "embedding"
    content: list[float]


class Audio(typing.TypedDict):
    role: str | None = None
    type: typing.Literal["audio"] = "audio"
    content: bytes
    mime_type: str


class Video(typing.TypedDict):
    role: str | None = None
    type: typing.Literal["video"] = "video"
    content: bytes
    mime_type: str


class CountTokens(typing.TypedDict):
    embedding: list[float]

class Embeding(typing.TypedDict):
    type: typing.Literal["embedding"] = "embedding"
    content: list[float]

DeltaType = Text | Image | Embedding | Audio | Video
