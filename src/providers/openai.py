from ..schemas import provider
from ..schemas import closeai

class OpenaiProvider(provider.Provider):
    def __init__(self, config: dict):
        super().__init__(config)
        self.chat_completion = config.get('chat_completions', None)
        self.text_completion = config.get('text_completions', None)
    