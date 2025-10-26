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

@macro.macro("repeat")
def repeat(s: str, n: int = 1) -> str:
    return s * n

@macro.macro("replace")
def replace(s: str, old: str, new: str, count: int = -1) -> str:
    return s.replace(old, new, count)

@macro.macro("reverse")
def reverse(s: str) -> str:
    return s[::-1]

@macro.macro("///")
@macro.macro("//")
@macro.macro("comment")
def comment(s: str) -> str:
    return ""

@macro.macro("rotate")
def rotate(s: str, n: int = 1) -> str:
    return s[n:] + s[:n]
