import os
import importlib

# default settings
from default_settings import *  # noqa: F403

user_settings_module = os.environ.get('USER_SETTINGS_MODULE', 'settings')

if user_settings_module:
    try:
        user_settings = importlib.import_module(user_settings_module)
        for key in dir(user_settings):
            if key.isupper():
                globals()[key] = getattr(user_settings, key)
    except ImportError:
        ...
