import random
import schemas.selector
import schemas.provider
import schemas.request

class RandomSelector(schemas.selector.Selector):
    async def next(self, request: schemas.request.Request) -> schemas.provider.Provider:
        providers = self.get_available_providers(request.body['model'])
        if not providers:
            return None
        
        return random.choice(providers)
