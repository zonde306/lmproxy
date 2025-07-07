import json
import typing
import logging
import schemas.middleware
import schemas.response
import schemas.request
import utils.loader
import scheduler
import utils.lazy_settings

logger = logging.getLogger(__name__)


class Engine:
    middlewares: list[schemas.middleware.Middleware] = []

    def __init__(self, middlewares=utils.lazy_settings.LazySettings("MIDDLEWARES")):
        self.middlewares = utils.loader.create_from_dict(middlewares)
        self.scheduler = scheduler.Scheduler()

    async def generate(
        self, request: schemas.request.Request
    ) -> schemas.response.Response | typing.AsyncGenerator[str]:
        try:
            for middleware in self.middlewares:
                result = await middleware.process_request(request)
                if resp := self.result_to_response(result):
                    return resp

            response = await self.scheduler.generate(request)
            if isinstance(response, dict):
                for middleware in self.middlewares:
                    result = await middleware.process_response(request, response)
                    if resp := self.result_to_response(result):
                        return resp
            elif isinstance(response, typing.AsyncGenerator):
                return self.warpped_response(response, response)
            else:
                logger.warning(f"Unhandled response: {response}")
                return self.result_to_response(response)
        except schemas.response.ErrorResponse as e:
            return e

    async def warpped_response(
        self, request: schemas.request.Request, generator: typing.AsyncGenerator[dict]
    ) -> typing.AsyncGenerator[str]:
        async for chunk in generator:
            for middleware in self.middlewares:
                result = await middleware.process_response_chunk(request, chunk)
                if res := self.result_to_response(result):
                    chunk = res
                    break

            yield chunk
        
        if request.body.get("stream"):
            yield "data: [DONE]"


    def result_to_response(self, result: typing.Any) -> schemas.response.Response:
        if isinstance(result, schemas.response.Response):
            if isinstance(result.body, (dict, list)):
                result.body = json.dumps(result.body, separators=(",", ":")).encode(
                    "utf-8"
                )
                result.headers["Content-Type"] = "application/json; charset=utf-8"
            return result

        if isinstance(result, (dict, list)):
            return schemas.response.Response(
                json.dumps(result, separators=(",", ":")),
                200,
                {"Content-Type": "application/json; charset=utf-8"},
            )

        return result
