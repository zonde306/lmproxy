import threading

class LazySettings:
    def __init__(self, setting_name: str):
        self.setting_name = setting_name
        self._value = None
        self._lock = threading.Lock()
        self._loaded = False

    def _load(self):
        with self._lock:
            if not self._loaded:
                try:
                    import settings
                    self._value = getattr(settings, self.setting_name)
                    self._loaded = True
                except ImportError as e:
                    raise RuntimeError(f"无法加载 settings 模块：{e}") from e
                except AttributeError as e:
                    raise AttributeError(
                        f"配置项 '{self.setting_name}' 不存在于 settings 中"
                    ) from e
        return self._value

    def __getattr__(self, name):
        return getattr(self._load(), name)

    def __getitem__(self, key):
        return self._load()[key]

    def __setitem__(self, key, value):
        self._load()[key] = value

    def __delitem__(self, key):
        del self._load()[key]

    def __iter__(self):
        return iter(self._load())

    def __len__(self):
        return len(self._load())

    def __contains__(self, item):
        return item in self._load()

    def __repr__(self):
        return repr(self._load())

    def __str__(self):
        return str(self._load())
