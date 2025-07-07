import typing

class ChatRequest(typing.TypedDict):
    class Message(typing.TypedDict):
        class TextMessage(typing.TypedDict):
            type: typing.Literal["text"]
            text: str

        class ImageMessage(typing.TypedDict):
            class ImageUrl(typing.TypedDict):
                url: str
                detail: typing.Literal["auto", "low", "high"]

            type: typing.Literal["image"]
            image: ImageUrl

        class AudioMessage(typing.TypedDict):
            class InputAudio(typing.TypedDict):
                data: str # base64 encoded
                format: typing.Literal["wav", "mp3"]

            type: typing.Literal["input_audio"]
            input_audio: InputAudio

        class FileMessage(typing.TypedDict):
            class File(typing.TypedDict):
                file_data: str # base64 encoded
                file_id: str
                filename: str
            
            type: typing.Literal["file"]
            file: File


        role: str
        content: str | TextMessage | ImageMessage | AudioMessage | FileMessage

    class ToolDefinition(typing.TypedDict):
        class Function(typing.TypedDict):
            class Paramter(typing.TypedDict):
                class Property(typing.TypedDict):
                    type: str
                    description: str

                type: typing.Literal["object"]
                properties: dict[str, Property]

            name: str # [a-zA-Z0-9_\-]{1,64}
            description: str
            parameters: dict[str, Paramter]

        type: typing.Literal["function"]
        function: Function

    class ToolChoice(typing.TypedDict):
        class Function(typing.TypedDict):
            name: str
        
        type: typing.Literal["function"]
        function: Function

    messages: list[Message]
    model: str
    stream: None | bool
    frequency_penalty: None | float
    max_tokens: None | int
    max_completion_tokens: None | int
    n: None | int
    presence_penalty: None | float
    temperature: None | float
    top_p: None | float
    tool_choice: None | typing.Literal["none", "auto", "required"] | ToolChoice
    tools: None | list[ToolDefinition]

class ChatResponse(typing.TypedDict):
    class Choice(typing.TypedDict):
        class Message(typing.TypedDict):
            class ToolCall(typing.TypedDict):
                class Function:
                    name: str
                    arguments: str
                
                type: typing.Literal["function"]
                id: str
                function: Function

            content: str | None
            role: typing.Literal["assistant"] | None
            tool_calls: list[ToolCall] | None

        finish_reason: typing.Literal["stop"]
        index: int
        message: Message

    class Usage(typing.TypedDict):
        completion_tokens: int
        prompt_tokens: int
        total_tokens: int

    object: typing.Literal["chat.completion"]
    id: str
    choices: list[Choice]
    created: int
    model: str
    usage: Usage

class ChatStreamResponse(typing.TypedDict):
    class Choice(typing.TypedDict):
        class Delta(typing.TypedDict):
            class ToolCall(typing.TypedDict):
                class Function:
                    name: str
                    arguments: str
                
                index: int
                type: typing.Literal["function"]
                id: str
                function: Function

            content: str
            role: typing.Literal["assistant"] | None
            tool_calls: list[ToolCall] | None

        finish_reason: typing.Literal["stop"]
        index: int
        delta: Delta

    class Usage(typing.TypedDict):
        completion_tokens: int
        prompt_tokens: int
        total_tokens: int

    object: typing.Literal["chat.completion.chunk"]
    id: str
    choices: list[Choice]
    created: int
    model: str
    usage: dict

class ModelListResponse(typing.TypedDict):
    class Model(typing.TypedDict):
        id: str
        name: str | None
        description: str | None

    object: typing.Literal["list"]
    data: list[Model]
