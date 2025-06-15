import typing
import importlib

def create(name : str, *args, **kwargs) -> object:
    split = name.rfind(".")
    module_name = name[:split]
    cls = name[split + 1:]
    module = importlib.import_module(module_name)
    return getattr(module, cls)(*args, **kwargs)

def create_from_dict(config : dict[str, int | dict[str, typing.Any]]) -> list:
    enabled = filter(lambda x: x[1] is not None, config.items())
    ordered = sorted(enabled, key=lambda x: x[1] if isinstance(x[1], int) else x[1]['priority'], reverse=True)

    return [
        create(name, config=conf) for name, conf in ordered
    ]

def create_from_list(config : list[dict[str, typing.Any]]) -> list:
    enabled = filter(lambda x: not x.get('disabled', False), config)
    ordered = sorted(enabled, key=lambda x: x['priority'], reverse=True)

    return [
        create(conf['service'], config=conf) for conf in ordered
    ]
