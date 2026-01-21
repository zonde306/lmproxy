import re
import json
import typing
import asyncio
import logging
import contextlib
import rnet
import worker
import proxies
import context
import error
import resources

logger = logging.getLogger(__name__)

RETRY_EXCEPTIONS = [
    rnet.exceptions.StatusError,
    rnet.exceptions.TimeoutError,
    rnet.exceptions.ConnectionError,
    rnet.exceptions.ConnectionResetError,
    rnet.exceptions.UpgradeError,
    rnet.exceptions.DNSResolverError,
    AssertionError,
]

class AiStudioWorker(worker.Worker):
    def __init__(self, settings: dict[str, typing.Any], proxies: proxies.ProxyFactory):
        super().__init__(settings, proxies)
        self._filters : list[re.Pattern] = [ re.compile(f)  for f in settings.get("filters", []) ]
        self.max_retries = settings.get("max_retries", 3)
        self.wait_time = settings.get("wait_time", 3)

        self.api_keys = settings.get("api_keys", [])
        key = settings.get("api_key")
        if key is not None:
            self.api_keys.append(key)
        self._resources = resources.ResourceManager(
            self.api_keys, **settings.get("key_manager", {})
        )

        self.models_url: str = settings.get(
            "models_url", "https://generativelanguage.googleapis.com/v1beta/models?key={key}"
        )
        self.completions_url: str = settings.get(
            "completions_url", "https://generativelanguage.googleapis.com/v1beta/{model}:{method}?key={key}"
        )
        self.embedding_url: str = settings.get(
            "embedding_url", "https://generativelanguage.googleapis.com/v1beta/{model}:embedContent?key={key}"
        )
    
    async def models(self) -> list[str]:
        if not self.models_url:
            return self.available_models
        
        reverse_aliases = dict(zip(self.aliases.values(), self.aliases.keys()))
        async with self._resources.get() as api_key:
            if api_key is None:
                raise error.WorkerOverloadError("No API keys available")

            url = self.models_url.format(key=api_key)
            async with self.client() as client:
                async with await client.get(url) as response:
                    assert isinstance(response, rnet.Response)
                    assert response.ok, (
                        f"ERROR: {response.status} {await response.text()} of {self.models_url} when {api_key[:len(api_key) // 3]}"
                    )
                    data = await response.json()
                    return [
                        reverse_aliases.get(x["baseModelId"], x["baseModelId"])
                        for x in data["models"]
                        if not self._filters or any(map(lambda f: f.match(x["baseModelId"]), self._filters))
                    ]
    
    async def generate_text(self, context: context.Context) -> context.Text:
        if context.model not in self.available_models:
            raise error.WorkerUnsupportedError(
                f"Model {context.model} not available"
            )

        force_streaming = self.settings.get("streaming", None)
        streaming = context.body.get("stream", False)
        if force_streaming is None:
            if streaming:
                return await self.streaming(context)
            return await self.no_streaming(context)

        if force_streaming:
            if streaming:
                return await self.streaming(context)
            return await self.to_no_streaming(await self.streaming(context))

        if streaming:
            return await self.to_streaming(self.no_streaming(context))

        return await self.no_streaming(context)
    
    async def streaming(self, ctx: context.Context) -> context.Text:
        async def generate() -> typing.AsyncGenerator[str, None]:
            async for attempt in self._resources.get_retying(
                self.max_retries, 
                self.wait_time, 
                RETRY_EXCEPTIONS
            ):
                try:
                    async with attempt as api_key:
                        if api_key is None:
                            raise error.WorkerOverloadError("No API keys available")
                        
                        headers = self.headers.copy()
                        url = self.completions_url.format(model=ctx.model, method="streamGenerateContent", key=api_key)
                        body = self.convert_to_gemini(ctx.payload(self.settings))
                        await self._prepare_payload(headers, body, api_key, True, ctx)

                        async with self.client() as client:
                            async with await client.post(
                                url, json=body, headers=headers
                            ) as response:
                                assert isinstance(response, rnet.Response)
                                assert response.ok, (
                                    f"ERROR: {response.status} {await response.text()} of {self.completions_url}"
                                )

                                async with response.stream() as streamer:
                                    assert isinstance(streamer, rnet.Streamer)
                                    
                                    buffer = b""
                                    with contextlib.suppress(rnet.DecodingError):
                                        async for chunk in streamer:
                                            assert isinstance(chunk, bytes)
                                            buffer += chunk
                                            if not buffer.endswith(b"\n"):
                                                continue

                                            for line in buffer.split(b"\n"):
                                                content = line.strip().removeprefix(b"data:")
                                                if content:
                                                    # SSE end
                                                    if b"[DONE]" in content:
                                                        break

                                                    # SSE commit
                                                    if content.startswith(b":"):
                                                        continue

                                                    data = json.loads(
                                                        content.decode(response.encoding or "utf-8")
                                                    )
                                                    yield await self._parse_response(data, ctx)

                                            buffer = b""
                except resources.NoMoreResourceError as e:
                    raise error.WorkerOverloadError("No API keys available") from e

        return generate()

    async def no_streaming(self, ctx: context.Context) -> context.Text:
        async for attempt in self._resources.get_retying(
            self.max_retries, 
            self.wait_time, 
            RETRY_EXCEPTIONS
        ):
            try:
                async with attempt as api_key:
                    if api_key is None:
                        raise error.WorkerOverloadError("No API keys available")

                    headers = self.headers.copy()
                    url = self.completions_url.format(model=ctx.model, method="generateContent", key=api_key)
                    body = self.convert_to_gemini(ctx.payload(self.settings))
                    await self._prepare_payload(headers, body, api_key, False, ctx)

                    async with self.client() as client:
                        async with await client.post(
                            url, json=body, headers=headers
                        ) as response:
                            assert isinstance(response, rnet.Response)
                            assert response.ok, (
                                f"ERROR: {response.status} {await response.text()} of {self.completions_url}"
                            )

                            data = await response.json()
                            return await self._parse_response(data, ctx)
            except resources.NoMoreResourceError as e:
                raise error.WorkerOverloadError("No API keys available") from e

    async def to_streaming(
        self, response: typing.Awaitable[context.Text]
    ) -> typing.AsyncGenerator[context.Text, None]:
        task = asyncio.create_task(response)
        while not task.done():
            await asyncio.wait(
                {task}, timeout=self.settings.get("fake_streaming_interval", 9)
            )
            yield context.Text(type="text", content=None, reasoning_content=None, tool_calls=[])

        yield task.result()

    async def to_no_streaming(self, response: typing.AsyncGenerator[context.Text, None]) -> context.Text:
        content = context.Text(type="text", content="", reasoning_content="", tool_calls=[])
        async for chunk in response:
            if delta := chunk.get("content", None):
                content["content"] += delta
            if delta := chunk.get("reasoning_content", None):
                content["reasoning_content"] += delta
            if delta := chunk.get("tool_calls", None):
                content["tool_calls"].extend(delta)

        content.update({
            "content": content["content"] if content["content"] else None,
            "reasoning_content": content["reasoning_content"] if content["reasoning_content"] else None,
            "tool_calls": content["tool_calls"] if content["tool_calls"] else None,
        })
        return content

    async def _prepare_payload(
        self,
        headers: dict[str, str],
        body: dict[str, typing.Any],
        api_key: str,
        streaming: bool | None,
        ctx: context.Context,
    ) -> None:
        ...

    async def _parse_response(self, data: "GenerateContentResponse", ctx: context.Context) -> context.Text:
        def iter_text():
            for candidate in data["candidates"]:
                for part in candidate["content"]["parts"]:
                    if not part.get("thought", False) and part.get("text", None):
                        yield part["text"]
        
        def iter_thought():
            for candidate in data["candidates"]:
                for part in candidate["content"]["parts"]:
                    if part.get("thought", False) and part.get("text", None):
                        yield part["text"]
        
        def iter_calls():
            for candidate in data["candidates"]:
                for part in candidate["content"]["parts"]:
                    if part.get("functionCall", None):
                        yield part["functionCall"]

        texts = list(iter_text())
        thoughts = list(iter_thought())
        tool_calls = list(iter_calls())

        if len(texts) == 1:
            texts = texts[0]
        if len(thoughts) == 1:
            thoughts = thoughts[0]
        if len(tool_calls) == 1:
            tool_calls = tool_calls[0]

        return context.Text(type="text", content=texts, reasoning_content=thoughts, tool_calls=tool_calls)
    
    async def convert_to_gemini(self, payload: context.ChatCompletionPayload) -> "GenerateContentRequest":
        thinkingBudget = None
        match payload.get("reasoning_effort"):
            case "none":
                thinkingBudget = 0
            case "low":
                thinkingBudget = 1024
            case "medium":
                thinkingBudget = 8192
            case "high":
                thinkingBudget = 24576
        
        contents : list[Content] = []
        for message in payload["messages"]:
            content : Content = {
                "role": "user" if message["role"] == "user" else "model",
                "parts": []
            }
            if isinstance(message["content"], str):
                content["parts"].append({ "text": message["content"] })
            elif isinstance(message["content"], list):
                for mes in message["content"]:
                    if mes["type"] == "text":
                        content["parts"].append({ "text": mes["text"] })
                    elif mes["type"] == "image_url":
                        if image := self.convert_image_url(mes["image_url"]["url"]):
                            if "data" in image:
                                content["parts"].append({ "inlineData": image })
                            else:
                                content["parts"].append({ "fileData": image })
            
            if content["parts"]:
                contents.append(content)

        return {
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "OFF"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "OFF"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "OFF"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "OFF"},
            ],
            "generationConfig": {
                "candidateCount": payload["n"] or 1,
                "maxOutputTokens": payload["max_tokens"],
                "temperature": payload["temperature"],
                "topP": payload["top_p"],
                "topK": payload["top_k"],
                "frequencyPenalty": payload["frequency_penalty"],
                "presencePenalty": payload["presence_penalty"],
                "responseLogprobs": payload["logprobs"],
                "logprobs": payload["top_logprobs"],
                "thinkingConfig": {
                    "includeThoughts": True,
                    "thinkingBudget": thinkingBudget,
                },
                "seed": payload["seed"],
            },
            "contents": contents,
        }
    
    def convert_image_url(self, url: str) -> typing.Union["Blob", "FileData", None]:
        if url.startswith("data:") and ";base64," in url:
            return { "mimeType": url[5:url.index(";base64,")], "data": url[url.index(";base64,") + 8:]}
        if url.startswith("http"):
            return { "mimeType": f"image/{url.split('.')[-1]}", "fileUri": url }
        return None
    
    async def generate_embedding(self, ctx: context.Context) -> context.Embedding:
        async for attempt in self._resources.get_retying(
            self.max_retries, 
            self.wait_time, 
            RETRY_EXCEPTIONS
        ):
            try:
                async with attempt as api_key:
                    if api_key is None:
                        raise error.WorkerOverloadError("No API keys available")

                    url = self.embedding_url.format(key=api_key, model=ctx.model)
                    headers = self.headers.copy()
                    body = {
                        "content": [ { "parts": [{ "text": ctx.body["input"] }] if isinstance(ctx.body["input"], str) else [ { "text": s } for s in ctx.body["input"] ] } ],
                        "outputDimensionality": ctx.body.get("dimensions")
                    }

                    async with self.client() as client:
                        async with await client.post(
                            url, json=body, headers=headers
                        ) as response:
                            assert isinstance(response, rnet.Response)
                            assert response.ok, (
                                f"ERROR: {response.status} {await response.text()} of {self.completions_url}"
                            )

                            data = await response.json()
                            return { "type": "embedding", "content": data["values"] }
            except resources.NoMoreResourceError as e:
                raise error.WorkerOverloadError("No API keys available") from e

class Blob(typing.TypedDict):
    mimeType: str
    data: str  # Base64

class FileData(typing.TypedDict):
    mimeType: str
    fileUri: str

class VideoMetadata(typing.TypedDict):
    start_offset: typing.Optional[str]  # e.g. "1.5s"
    end_offset: typing.Optional[str]

class FunctionCall(typing.TypedDict):
    name: str
    args: typing.Optional[typing.Dict[str, typing.Any]]

class FunctionResponse(typing.TypedDict):
    name: str
    response: typing.Dict[str, typing.Any]

class ExecutableCode(typing.TypedDict):
    language: typing.Literal["LANGUAGE_UNSPECIFIED", "PYTHON"]
    code: str

class CodeExecutionResult(typing.TypedDict):
    outcome: typing.Literal["OUTCOME_UNSPECIFIED", "OK", "FAILED", "DEADLINE_EXCEEDED"]
    output: str

class Part(typing.TypedDict, total=False):
    text: str | None
    inlineData: Blob | None
    functionCall: FunctionCall | None
    functionResponse: FunctionResponse | None
    fileData: FileData | None
    executableCode: ExecutableCode | None
    codeExecutionResult: CodeExecutionResult | None
    thought: bool | None
    thoughtSignature: str | None # Base64

class Content(typing.TypedDict):
    parts: typing.List[Part]
    role: typing.Optional[typing.Literal["user", "model"]]

class Schema(typing.TypedDict, total=False):
    type: typing.Literal["TYPE_UNSPECIFIED", "STRING", "NUMBER", "INTEGER", "BOOLEAN", "ARRAY", "OBJECT", "NULL"]
    format: str | None
    description: str | None
    nullable: bool | None
    enum: typing.List[str] | None
    properties: typing.Dict[str, 'Schema']
    required: typing.List[str]
    items: 'Schema'
    maxItems: str
    minItems: str

class FunctionDeclaration(typing.TypedDict):
    name: str
    description: str
    parameters: typing.Optional[Schema]
    parametersJsonSchema: str # JSON Schema
    response: Schema | None

class DynamicRetrievalConfig(typing.TypedDict):
    mode: typing.Literal["MODE_UNSPECIFIED", "MODE_DYNAMIC"]
    dynamic_threshold: typing.Optional[float]

class GoogleSearchRetrieval(typing.TypedDict):
    dynamic_retrieval_config: typing.Optional[DynamicRetrievalConfig]

class CodeExecution(typing.TypedDict):
    pass

class Tool(typing.TypedDict, total=False):
    functionDeclarations: typing.List[FunctionDeclaration]
    googleSearchRetrieval: GoogleSearchRetrieval
    codeExecution: CodeExecution
    googleSearch: GoogleSearchRetrieval

class FunctionCallingConfig(typing.TypedDict):
    mode: typing.Optional[typing.Literal["MODE_UNSPECIFIED", "AUTO", "ANY", "NONE"]]
    allowed_function_names: typing.Optional[typing.List[str]]

class ToolConfig(typing.TypedDict):
    function_calling_config: typing.Optional[FunctionCallingConfig]

class UsageMetadata(typing.TypedDict):
    total_token_count: int
    text_count: typing.Optional[int]
    image_count: typing.Optional[int]
    video_duration_seconds: typing.Optional[int]
    audio_duration_seconds: typing.Optional[int]

class CachedContent(typing.TypedDict):
    name: typing.Optional[str]  # cachedContents/{id}
    display_name: typing.Optional[str]
    model: str
    
    system_instruction: typing.Optional[Content]
    contents: typing.Optional[typing.List[Content]]
    tools: typing.Optional[typing.List[Tool]]
    tool_config: typing.Optional[ToolConfig]
    
    expire_time: typing.Optional[str]  # RFC 3339 timestamp
    ttl: typing.Optional[str]         # e.g. "3600s"
    
    create_time: typing.Optional[str]
    update_time: typing.Optional[str]
    usage_metadata: typing.Optional[UsageMetadata]

class SpeechConfig(typing.TypedDict, total=False):
    voiceConfig: typing.Optional[typing.Dict[str, typing.Any]]

class GenerationConfig(typing.TypedDict, total=False):
    stopSequences: typing.List[str] | None
    responseMimeType: str | None
    responseSchema: typing.Optional[typing.Any] | None
    candidateCount: int | None
    maxOutputTokens: int | None
    temperature: float | None
    topP: float | None
    topK: int | None
    seed: int | None
    presencePenalty: float | None
    frequencyPenalty: float | None
    responseLogprobs: bool | None
    logprobs: int | None
    enableEnhancedCivicAnswers: bool | None
    speechConfig: typing.Optional[SpeechConfig]
    thinkingConfig: typing.Optional[typing.Dict[str, typing.Any]]

class SafetySetting(typing.TypedDict):
    category: typing.Literal["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]
    threshold: typing.Literal["OFF", "BLOCK_NONE"]

class SafetyRating(typing.TypedDict):
    category: typing.Literal["HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT"]
    probability: typing.Literal["NEGLIGIBLE", "LOW", "MEDIUM", "HIGH"]
    blocked: typing.Optional[bool]

class CitationSource(typing.TypedDict, total=False):
    startIndex: int | None
    endIndex: int | None
    uri: str | None
    license: str | None

class CitationMetadata(typing.TypedDict):
    citationSources: typing.List[CitationSource] | None

class GroundingAttribution(typing.TypedDict, total=False):
    sourceId: typing.Dict[str, typing.Any]
    content: typing.Optional[Content]

class GroundingMetadata(typing.TypedDict, total=False):
    searchEntryPoint: typing.Optional[typing.Dict[str, str]]
    groundingChunks: typing.Optional[typing.List[typing.Dict[str, typing.Any]]]
    groundingSupports: typing.Optional[typing.List[typing.Dict[str, typing.Any]]]
    webSearchQueries: typing.Optional[typing.List[str]]
    googleMapsWidgetContextToken: str | None

class Candidate(typing.TypedDict, total=False):
    content: typing.Optional[Content]
    finishReason: typing.Literal["FINISH_REASON_UNSPECIFIED", "STOP", "MAX_TOKENS", "SAFETY", "OTHER", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII", "MALFORMED_FUNCTION_CALL", "IMAGE_SAFETY", "IMAGE_PROHIBITED_CONTENT", "IMAGE_OTHER", "NO_IMAGE", "IMAGE_RECITATION", "UNEXPECTED_TOOL_CALL", "TOO_MANY_TOOL_CALLS", "MISSING_THOUGHT_SIGNATURE"] | None
    safetyRatings: typing.List[SafetyRating]
    citationMetadata: typing.Optional[CitationMetadata]
    groundingMetadata: typing.Optional[GroundingMetadata]
    avgLogprobs: float
    index: int
    finishMessage: str | None

class PromptFeedback(typing.TypedDict, total=False):
    blockReason: typing.Literal["BLOCK_REASON_UNSPECIFIED", "SAFETY", "OTHER", "BLOCKLIST", "PROHIBITED_CONTENT", "IMAGE_SAFETY"]
    safetyRatings: typing.List[SafetyRating]

class UsageMetadata(typing.TypedDict, total=False):
    promptTokenCount: int
    cachedContentTokenCount: int
    candidatesTokenCount: int
    toolUsePromptTokenCount: int
    thoughtsTokenCount: int
    totalTokenCount: int

class GenerateContentRequest(typing.TypedDict, total=False):
    contents: typing.List[Content]
    tools: typing.Optional[typing.List[Tool]]
    toolConfig: typing.Optional[ToolConfig]
    safetySettings: typing.Optional[typing.List[SafetySetting]]
    systemInstruction: typing.Optional[Content]
    generationConfig: typing.Optional[GenerationConfig]
    cachedContent: typing.Optional[str] # cachedContents/{id}

class GenerateContentResponse(typing.TypedDict, total=False):
    candidates: typing.List[Candidate]
    promptFeedback: typing.Optional[PromptFeedback]
    usageMetadata: typing.Optional[UsageMetadata]
    modelVersion: str
    responseId: str
