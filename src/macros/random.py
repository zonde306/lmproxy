import random
import macro
import context

@macro.macro("randomint")
def random_int(min: int = 0, max: int = 0x7FFFFFFF) -> int:
    if min > max:
        min, max = max, min
    return random.randint(min, max)

@macro.macro("roll")
def roll_dice(dice: str) -> int:
    """
    roll dice with the format "XdY" or "XdY+Z" or "XdY-Z"
    where X is the number of dice and Y is the modifier
    e.g. "1d20" or "2d20+5"
    """
    
    if "+" in dice:
        dice, modifier = dice.split("+", 2)
        modifier = int(modifier)
    elif "-" in dice:
        dice, modifier = dice.split("-", 2)
        modifier = -int(modifier)
    else:
        modifier = 0
    
    num_dice, dice_size = dice.split("d", 2)
    num_dice = int(num_dice or 1)
    dice_size = int(dice_size or 6)
    
    total = sum(random.randint(1, dice_size) for _ in range(num_dice))
    return total + modifier

@macro.macro("random")
def sample(items: str, n: int = 1, serp: str = "") -> str:
    """
    从逗号分隔的字符串中随机选择 n 个项目。
    """
    items = items.split(",")
    return serp.join(random.sample(items, n))

@macro.macro("pick")
def pick(items: str, n: int = 1, serp: str = "", *,
         message: context.Message = None,
         content_part: context.TextContentPart = None) -> str:
    """
    从逗号分隔的字符串中随机选择 n 个项目。
    如果内容不变，则使用相同的随机数种子。
    """
    items = items.split(",")
    if content_part:
        hash_key = hash(content_part['text'])
    else:
        hash_key = hash(message['content'])
    
    random.seed(hash_key)
    return serp.join(random.sample(items, n))
