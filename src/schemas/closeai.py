import typing
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from openai.types.chat.completion_create_params import ResponseFormat, ChatCompletionToolChoiceOptionParam, ChatCompletionToolParam
from openai.types.chat.chat_completion import ChatCompletion
from openai.types.chat.chat_completion import Choice as ChatCompletionChoice
from openai.types.chat.chat_completion import ChatCompletionMessage
from openai.types.chat.chat_completion_chunk import ChatCompletionChunk
from openai.types.chat.chat_completion_chunk import Choice as ChatCompletionChoiceChunk
from openai.types.chat.chat_completion_chunk import ChoiceDelta as ChatCompletionChoiceDelta
from openai.types.completion import Completion
from openai.types.completion_choice import CompletionChoice

class ChatCompletionRequest(typing.TypedDict):
    messages: list[ChatCompletionMessageParam]
    model: str
    frequency_penalty: None | float
    logit_bias: None | dict[str, int]
    logprobs: None | bool
    max_completion_tokens: None | int
    max_tokens: None | int
    metadata: None | dict[str, str]
    modalities: None| list[str]
    n: None | int
    presence_penalty: None | float
    temperature: None | float
    top_p: None | float
    user: None | str
    stop: None | list[str] | str
    stream: None | bool
    parallel_tool_calls: None | bool
    response_format: None | ResponseFormat
    seed: None | int
    tool_choice: None | ChatCompletionToolChoiceOptionParam
    tools: None | list[ChatCompletionToolParam]
    top_logprobs: None | int
