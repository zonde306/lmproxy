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
    
    async def generate(self, request: dict, headers: dict, chat: bool) -> schemas.response.Response | str:
        try:
            for middleware in self.middlewares:
                result = await middleware.process_request(request, headers, chat)
                if isinstance(result, schemas.response.Response):
                    return result
            
            response = await self.scheduler.generate(request, headers, chat)
            if isinstance(response, dict):
                for middleware in self.middlewares:
                    result = await middleware.process_response(request, response, headers, chat)
                    if isinstance(result, schemas.response.Response):
                        return result
            elif isinstance(response, typing.AsyncGenerator[str]):
                return self.warpped_response(response, headers, chat, response)
            else:
                logger.warning(f"Unknown response: {response}")
                return response

        except schemas.response.ErrorResponse as e:
            return e
    
    async def warpped_response(self, request: dict, headers: dict, chat : bool,
                               generator: typing.AsyncGenerator[str]) -> typing.AsyncGenerator[str]:
        async for response in generator:
            for middleware in self.middlewares:
                result = await middleware.process_stream_response(request, response, headers, chat)
                if isinstance(result, str):
                    response = result
                    break
            
            yield response
