"""The two colour sets winmine has: Color on (Windows 95) and Color off."""

SLOTS = (
    "face", "light", "shadow", "grid", "revealed", "backdrop", "text",
    "led_bg", "led_on", "led_off",
    "mine", "glint", "flag", "ink", "exploded", "smiley", "smiley_ink", "cursor",
    "num1", "num2", "num3", "num4", "num5", "num6", "num7", "num8",
)

WIN95 = {
    "face": "#c0c0c0", "light": "#ffffff", "shadow": "#808080", "grid": "#808080",
    "revealed": "#c0c0c0", "backdrop": "#008080", "text": "#000000",
    "led_bg": "#000000", "led_on": "#ff0000", "led_off": "#800000",
    "mine": "#000000", "glint": "#ffffff", "flag": "#ff0000", "ink": "#000000",
    "exploded": "#ff0000", "smiley": "#ffff00", "smiley_ink": "#000000",
    "cursor": "#ff00ff",
    "num1": "#0000ff", "num2": "#008000", "num3": "#ff0000", "num4": "#000080",
    "num5": "#800000", "num6": "#008080", "num7": "#000000", "num8": "#808080",
}

MONO = {
    "face": "#c0c0c0", "light": "#ffffff", "shadow": "#808080", "grid": "#808080",
    "revealed": "#c0c0c0", "backdrop": "#808080", "text": "#000000",
    "led_bg": "#000000", "led_on": "#ffffff", "led_off": "#404040",
    "mine": "#000000", "glint": "#ffffff", "flag": "#000000", "ink": "#000000",
    "exploded": "#808080", "smiley": "#ffffff", "smiley_ink": "#000000",
    "cursor": "#000000",
    **{f"num{i}": "#000000" for i in range(1, 9)},
}


def rgb(hexstr):
    return tuple(int(hexstr[i:i + 2], 16) / 255 for i in (1, 3, 5))
