import importlib

def create(name : str, *args, **kwargs) -> object:
    split = name.rfind(".")
    module_name = name[:split]
    cls = name[split + 1:]
    module = importlib.import_module(module_name)
    return getattr(module, cls)(*args, **kwargs)

def create_from_config(config : dict[str, int | dict]) -> list:
    enabled = filter(lambda x: x[1] is not None, config.items())
    ordered = sorted(enabled, key=lambda x: x[1] if isinstance(x[1], int) else x[1]['priority'], reverse=True)

    results = []
    for name, conf in ordered:
        results.append(create(name, config=conf))
    
    return results
