import importlib

def create_from_config(config : dict[str, int]) -> list:
    enabled = filter(lambda x: x[1] is not None, config.items())
    ordered = sorted(enabled, key=lambda x: x[1], reverse=True)

    results = []
    for name, _ in ordered:
        split = name.rfind(".")
        module_name = name[:split]
        cls = name[split + 1:]
        module = importlib.import_module(module_name)
        results.append(getattr(module, cls)())
    
    return results
