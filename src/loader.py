import importlib

def get_class(name: str) -> object | None:
    path = name[:name.rindex('.')]
    module = importlib.import_module(path)
    return getattr(module, name[name.rindex('.') + 1:], None)
