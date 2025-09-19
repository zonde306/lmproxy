import logging
import middleware
import context
import error

logger = logging.getLogger(__name__)

class AuthorizationMiddleware(middleware.Middleware):
    async def process_request(self, ctx: context.Context) -> bool | None:
        auth_token = ctx.headers.get("authorization", "").removeprefix("Bearer ")
        if auth_token != str(self.settings.get("token", "")):
            logger.info(f"Unauthorized token: {auth_token}", extra={"context": ctx})
            raise error.TerminationRequest(context.Response(
                { "error": "Unauthorized" },
                401,
                { "WWW-Authenticate": "Bearer" }
            ))
