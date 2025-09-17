import sys
import yaml
import os.path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

with open("./example_settings.yaml", "r", encoding="utf-8") as f:
    settings = yaml.safe_load(f)

if os.path.exists("../settings.yaml"):
    with open("../settings.yaml", "r", encoding="utf-8") as f:
        settings.update(yaml.safe_load(f))
else:
    with open("../settings.yaml", "w", encoding="utf-8") as f:
        yaml.dump(settings, f)
