import macro

@macro.macro("str")
def to_string(s: str) -> str:
    return str(s)

@macro.macro("upper")
def upper(s: str) -> str:
    return s.upper()

@macro.macro("lower")
def lower(s: str) -> str:
    return s.lower()

@macro.macro("strip")
def strip(s: str, chars: str = " \r\n\t") -> str:
    return s.strip(chars)

@macro.macro("substr")
def substr(s: str, start: int = 0, end: int = -1) -> str:
    return s[start:end]
