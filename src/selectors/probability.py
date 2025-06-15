import random
import schemas.selector
import schemas.provider

class ProbabilitySelector(schemas.selector.Selector):
    async def select(self, request : dict, headers : dict) -> schemas.provider.Provider:
        providers = self.get_available_providers(request['model'])
        if not providers:
            return None
        
        total = sum([ abs(provider.probability) for provider in providers ])
        choice = random.randint(0, total)
        for provider in providers:
            choice -= abs(provider.probability)
            if choice <= 0:
                return provider
        
        return None
