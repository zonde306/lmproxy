import time
import datetime
import macro

@macro.macro("datetime")
def now(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    return datetime.datetime.now().strftime(fmt)

@macro.macro("timestamp")
def timestamp() -> str:
    return str(int(time.time()))
