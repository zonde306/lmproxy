import random
import macro

@macro.macro("random")
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
    num_dice = int(num_dice)
    dice_size = int(dice_size)
    
    total = sum(random.randint(1, dice_size) for _ in range(num_dice))
    return total + modifier
