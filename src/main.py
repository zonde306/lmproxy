import time
import json
import random
import logging
import inspect
import blacksheep
import router
import conf

logger = logging.getLogger(__name__)

app = blacksheep.Application()
app.add_cors_policy("lmproxy", allow_methods="GET,POST,OPTIONS", allow_origins="*")

engine = router.Router(conf.settings)

@blacksheep.get("/v1/models")
@blacksheep.get("/models")
async def models(request : blacksheep.Request) -> blacksheep.Response:
    data = await engine.models()
    return blacksheep.json({
        "object": "list",
        "data": [
            {
                "id": x,
                "object": "model",
                "name": x,
                "created": int(time.time()),
                "owned_by": "anonymous",
            }
            for x in data
        ],
    })

@blacksheep.post("/v1/chat/completions")
@blacksheep.post("/chat/completions")
async def chat_completions(request : blacksheep.Request) -> blacksheep.Response:
    payload = await request.json()
    result = await engine.generate_text(payload, { k.decode(): v.decode() for k, v in request.headers.items() })
    if inspect.isasyncgen(result.body):
        async def generate():
            async for chunk in result.body:
                data = json.dumps({
                    "id": random.randint(0x10000000, 0xffffffff),
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": payload.get("model", "unknown"),
                    "choices": [{
                        "index": 0,
                        "delta": {
                            "content": chunk
                        }
                    }]
                }, ensure_ascii=False)
                yield f"data: {data}\n\n"
            yield "data: [DONE]\n\n"

        return blacksheep.StreamedContent("text/event-stream", generate())

    return blacksheep.json({
        "id": random.randint(0x10000000, 0xffffffff),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": payload.get("model", "unknown"),
        "choices": [{
            "index": 0,
            "message": {
                "content": result.body
            }
        }]
    })
