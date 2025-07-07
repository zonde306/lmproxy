import schemas.selector
import schemas.provider
import schemas.request

class LRUSelector(schemas.selector.Selector):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.usage = [ [p, 0] for p in self.providers ]
    
    async def next(self, request: schemas.request.Request) -> schemas.provider.Provider:
        providers = self.get_available_providers(request.body['model'])
        if not providers:
            return None
        
        least = min(self.usage, key=lambda x: x[1])
        least[1] += 1
        return least
