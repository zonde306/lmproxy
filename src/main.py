import logging
import blacksheep
import engine
import schemas.response

logger = logging.getLogger(__name__)

app = blacksheep.Application()
app.add_cors_policy("oldapi", allow_methods="GET,POST,OPTIONS", allow_origins="*")

service = engine.Engine()

@blacksheep.get("/v1/models")
@blacksheep.get("/models")
async def models(request : blacksheep.Request) -> blacksheep.Response:
    ...

@blacksheep.post("/v1/chat/completions")
@blacksheep.post("/chat/completions")
async def chat_completions(request : blacksheep.Request) -> blacksheep.Response:
    response = await service.generate(await request.json(), request.headers, True)
    if isinstance(response, schemas.response.Response):
        return blacksheep.Response(response.status_code, response.headers, response.body)
    return blacksheep.StreamedContent("text/event-stream", response)

@blacksheep.post("/v1/completions")
@blacksheep.post("/completions")
async def completions(request : blacksheep.Request) -> blacksheep.Response:
    response = await service.generate(await request.json(), request.headers, False)
    if isinstance(response, schemas.response.Response):
        return blacksheep.Response(response.status_code, response.headers, response.body)
    return blacksheep.StreamedContent("text/event-stream", response)
