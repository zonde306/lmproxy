import importlib


def get_object(name: str) -> object | None:
    if "." not in name:
        return None
    
    path = name[: name.rindex(".")]
    module = importlib.import_module(path)
    cls = name[name.rindex(".") + 1 :]
    return getattr(module, cls, None)
