import time
import json
import random
import logging
import inspect
import blacksheep
import engine
import conf

logger = logging.getLogger(__name__)

app = blacksheep.Application()
app.add_cors_policy("lmproxy", allow_methods="GET,POST,OPTIONS", allow_origins="*")

_engine = engine.Engine(conf.settings)


@blacksheep.get("/v1/models")
@blacksheep.get("/models")
async def models(request: blacksheep.Request) -> blacksheep.Response:
    data = await _engine.models()
    return blacksheep.json(
        {
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
            # OLlama compatibility
            "models": [
                {
                    "name": x,
                    "modified_at": "",
                    "size": 0,
                    "digest": "",
                    "details": {},
                }
                for x in data
            ]
        }
    )


@blacksheep.post("/v1/chat/completions")
@blacksheep.post("/chat/completions")
async def chat_completions(request: blacksheep.Request) -> blacksheep.Response:
    payload = await request.json()
    result = await _engine.generate_text(
        payload, {k.decode(): v.decode() for k, v in request.headers.items()}
    )
    if isinstance(result.body, dict) and not result.body.get("type", None):
        return blacksheep.Response(
            result.status_code,
            list(result.headers.items()),
            blacksheep.JSONContent(result.body),
        )

    if inspect.isasyncgen(result.body):

        async def generate():
            id = random.randint(0x10000000, 0xFFFFFFFF)
            async for delta in result.body:
                data = json.dumps(
                    {
                        "id": id,
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": payload.get("model", "unknown"),
                        "choices": [{
                            "index": 0,
                            "delta": delta,
                        }],
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                yield f"data: {data}\n\n".encode("utf-8")
            
            if usage := result.metadata.get("usage", None):
                data = json.dumps(
                    {
                        "id": id,
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": payload.get("model", "unknown"),
                        "choices": [{
                            "index": 0,
                            "delta": {
                                "user": "assistant",
                            },
                            "finish_reason": "stop",
                        }],
                        "usage": usage,
                        "worker": result.metadata.get("worker", "unknown"),
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                yield f"data: {data}\n\n".encode("utf-8")

            yield b"data: [DONE]\n\n"

        return blacksheep.Response(
            result.status_code,
            list(result.headers.items()),
            blacksheep.StreamedContent(b"text/event-stream", generate),
        )

    return blacksheep.Response(
        result.status_code,
        list(result.headers.items()),
        blacksheep.JSONContent(
            {
                "id": random.randint(0x10000000, 0xFFFFFFFF),
                "object": "chat.completion",
                "created": int(time.time()),
                "model": payload.get("model", "unknown"),
                "choices": [
                    {
                        "index": 0,
                        "message": result.body,
                        "finish_reason": "stop",
                    }
                ],
                "usage": result.metadata.get("usage", None),
                "worker": result.metadata.get("worker", "unknown"),
            }
        ),
    )

@blacksheep.post("/v1/embeddings")
@blacksheep.post("/embeddings")
async def embeddings(request: blacksheep.Request) -> blacksheep.Response:
    payload = await request.json()
    result = await _engine.generate_embedding(
        payload, 
        {k.decode(): v.decode() for k, v in request.headers.items()}
    )

    if isinstance(result.body, list):
        return blacksheep.Response(
            result.status_code,
            list(result.headers.items()),
            blacksheep.JSONContent(
                {
                    "object": "embedding",
                    "embedding": result.body,
                    "index": 0,
                }
            ),
        )

    return blacksheep.Response(
        result.status_code,
        list(result.headers.items()),
        blacksheep.JSONContent(result.body),
    )
