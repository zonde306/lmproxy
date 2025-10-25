import collections
import macro

VARIABLES = collections.defaultdict(str)

@macro.macro("setvar")
def setvar(name: str, value: str) -> str:
    VARIABLES[name] = str(value)
    return ""

@macro.macro("getvar")
def getvar(name: str) -> str:
    return VARIABLES[name]

@macro.macro("delvar")
def delvar(name: str) -> str:
    del VARIABLES[name]
    return ""

@macro.macro("appendvar")
def appendvar(name: str, value: str, newline: int = 2) -> str:
    if newline and VARIABLES[name]:
        VARIABLES[name] += "\n" * newline
    VARIABLES[name] += str(value)
    return ""

@macro.macro("prependvar")
def prependvar(name: str, value: str, newline: int = 2) -> str:
    if newline:
        VARIABLES[name] = str(value) + '\n' * newline + VARIABLES[name]
    else:
        VARIABLES[name] = str(value) + VARIABLES[name]
    return ""

@macro.macro("incvar")
def incvar(name: str, value: int = 1) -> str:
    if not VARIABLES[name].isdigit():
        return ""

    VARIABLES[name] = str(int(VARIABLES[name]) + value)
    return ""

@macro.macro("decvar")
def decvar(name: str, value: int = 1) -> str:
    if not VARIABLES[name].isdigit():
        return ""
    
    VARIABLES[name] = str(int(VARIABLES[name]) - value)
    return ""
