import json
import typing
import logging
import schemas.middleware
import schemas.response
import utils.loader
import scheduler
import utils.lazy_settings

logger = logging.getLogger(__name__)

class Engine:
    middlewares : list[schemas.middleware.Middleware] = []

    def __init__(self, middlewares = utils.lazy_settings.LazySettings('MIDDLEWARES')):
        self.middlewares = utils.loader.create_from_config(middlewares)
        self.scheduler = scheduler.Scheduler()
    
    async def generate(self, request: dict, headers: dict, chat: bool) -> schemas.response.Response | typing.AsyncIterable[str]:
        try:
            for middleware in self.middlewares:
                result = await middleware.process_request(request, headers, chat)
                if resp := self.result_to_response(result):
                    return resp
            
            response = await self.scheduler.generate(request, headers, chat)
            if isinstance(response, dict):
                for middleware in self.middlewares:
                    result = await middleware.process_response(request, response, headers, chat)
                    if resp := self.result_to_response(result):
                        return resp
            elif isinstance(response, typing.AsyncIterable):
                return self.warpped_response(response, headers, chat, response)
            else:
                logger.warning(f"Unhandled response: {response}")
                return self.result_to_response(response)

        except schemas.response.ErrorResponse as e:
            return e
    
    async def warpped_response(self, request: dict, headers: dict, chat : bool,
                               generator: typing.AsyncIterable[str]) -> typing.AsyncIterable[str]:
        async for response in generator:
            for middleware in self.middlewares:
                result = await middleware.process_stream_response(request, response, headers, chat)
                if res := self.result_to_response(result):
                    response = res
                    break
            
            yield response
    
    def result_to_response(self, result: typing.Any) -> schemas.response.Response:
        if isinstance(result, schemas.response.Response):
            return result
        if isinstance(result, (dict, list)):
            return schemas.response.Response(json.dumps(result, separators=(',', ':')))
        return result
