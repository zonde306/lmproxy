import logging
import blacksheep

logger = logging.getLogger(__name__)

app = blacksheep.Application()
app.add_cors_policy("oldapi", allow_methods="GET,POST,OPTIONS", allow_origins="*")

@blacksheep.get("/v1/models")
@blacksheep.get("/models")
async def models(request : blacksheep.Request) -> blacksheep.Response:
    ...

@blacksheep.post("/v1/chat/completions")
@blacksheep.post("/chat/completions")
async def chat_completions(request : blacksheep.Request) -> blacksheep.Response:
    response = await service.generate(schemas.request.Request(
        headers= { k.decode() : v.decode() for k, v in request.headers.items() },
        body = await request.json(),
        type = "chat",
    ))
    if isinstance(response, schemas.response.Response):
        return blacksheep.Response(response.status_code, response.headers, response.body)
    return blacksheep.StreamedContent("text/event-stream", response)

@blacksheep.post("/v1/completions")
@blacksheep.post("/completions")
async def completions(request : blacksheep.Request) -> blacksheep.Response:
    response = await service.generate(schemas.request.Request(
        headers= { k.decode() : v.decode() for k, v in request.headers.items() },
        body = await request.json(),
        type = "text",
    ))
    if isinstance(response, schemas.response.Response):
        return blacksheep.Response(response.status_code, response.headers, response.body)
    return blacksheep.StreamedContent("text/event-stream", response)
