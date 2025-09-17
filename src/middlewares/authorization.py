import middleware
import context
import error

class AuthorizationMiddleware(middleware.Middleware):
    async def process_request(self, ctx: context.Context) -> bool | None:
        auth_token = ctx.headers.get("Authorization", "").removeprefix("Bearer ")
        if auth_token != self.settings.get("token"):
            raise error.TerminationRequest(context.Response(
                { "error": "Unauthorized" },
                401,
                { "WWW-Authenticate": "Bearer" }
            ))
