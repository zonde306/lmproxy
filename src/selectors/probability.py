import random
import schemas.selector
import schemas.provider
import schemas.request

class ProbabilitySelector(schemas.selector.Selector):
    async def next(self, request: schemas.request.Request) -> schemas.provider.Provider:
        providers = self.get_available_providers(request.body['model'])
        if not providers:
            return None
        
        total = sum([ abs(provider.metadata.get("probability", 1)) for provider in providers ])
        choice = random.randint(0, total)
        for provider in providers:
            choice -= abs(provider.metadata.get("probability", 1))
            if choice <= 0:
                return provider
        
        return None
