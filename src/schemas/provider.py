import typing
import closeai

class Provider:
    name: str = ""
    probability: int = 100

    def __init__(self, config: dict):
        self.config = config

    def __hash__(self):
        return hash(f'{self.name}:{self.probability}')

    async def models(self, request: dict, headers: dict) -> list[str]:
        ...
    
    async def chat_completions(self, request: dict, headers: dict) -> closeai.ChatCompletion:
        content = ""
        for chunk in self.stream_chat_completions(request, headers):
            assert isinstance(chunk, closeai.ChatCompletion)
            content += chunk.choices[0].message.content or ""
        
        return closeai.ChatCompletion(
            id=chunk.id,
            object="chat.completion",
            created=chunk.created,
            model=chunk.model,
            usage=chunk.usage,
            choices=[
                closeai.ChatCompletionChoice(
                    index=0,
                    finish_reason=chunk.choices[0].finish_reason,
                    logprobs=chunk.choices[0].logprobs,
                    message=closeai.ChatCompletionMessage(
                        content=content,
                        role=chunk.choices[0].message.role,
                        tool_calls=chunk.choices[0].message.tool_calls,
                    )
                )
            ]
        )
    
    async def stream_chat_completions(self, request: dict, headers: dict) -> typing.AsyncIterable[closeai.ChatCompletionChunk]:
        completion = await self.chat_completions(request, headers)
        yield closeai.ChatCompletionChunk(
            id=completion.id,
            object="chat.completion.chunk",
            created=completion.created,
            model=completion.model,
            usage=completion.usage,
            choices=[
                closeai.ChatCompletionChoiceChunk(
                    index=0,
                    finish_reason=completion.choices[0].finish_reason,
                    logprobs=completion.choices[0].logprobs,
                    delta=closeai.ChatCompletionChoiceDelta(
                        content=completion.choices[0].message.content,
                        role=completion.choices[0].message.role,
                        tool_calls=completion.choices[0].message.tool_calls,
                    )
                )
            ]
        )
    
    async def completion(self, request: dict, headers: dict) -> closeai.Completion:
        content = ""
        for chunk in self.stream_completion(request, headers):
            assert isinstance(chunk, closeai.Completion)
            content += chunk.choices[0].text
        
        return closeai.Completion(
            id=chunk.id,
            object="text_completion",
            created=chunk.created,
            model=chunk.model,
            usage=chunk.usage,
            choices=[
                closeai.CompletionChoice(
                    text=content,
                    finish_reason=chunk.choices[0].finish_reason,
                    index=chunk.choices[0].index,
                    logprobs=chunk.choices[0].logprobs,
                )
            ]
        )
    
    async def stream_completion(self, request: dict, headers: dict) -> typing.AsyncIterable[closeai.Completion]:
        completion = await self.chat_completions(request, headers)
        yield completion
    
    async def count_tokens(self, request: dict, headers: dict) -> int | None:
        return None
    
    async def embedding(self, request: dict, headers: dict) -> bytes:
        ...
