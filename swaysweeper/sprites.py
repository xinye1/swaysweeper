"""Every glyph as text pixel art. Each character names a colour slot; '.' is
transparent. Nothing here is a bitmap, so recolouring is a dictionary lookup.
"""

from .colours import rgb

LEGEND = {
    **{str(n): f"num{n}" for n in range(1, 9)},
    "M": "mine", "g": "glint", "F": "flag", "K": "ink", "X": "exploded",
    "Y": "smiley", "S": "smiley_ink",
    "L": "light", "D": "shadow", "f": "face",
    "B": "led_bg", "O": "led_on", "o": "led_off",
}


def _blank(w, h):
    return [["."] * w for _ in range(h)]


def _stamp(grid, art, ox, oy):
    for dy, row in enumerate(art):
        for dx, ch in enumerate(row):
            if ch != ".":
                grid[oy + dy][ox + dx] = ch
    return grid


def _rows(grid):
    return ["".join(r) for r in grid]


# --- numbers: 10x10 glyphs stamped at (3, 3) of a 16x16 cell ---------------

_DIGITS = {
    1: ["....##....",
        "...###....",
        "..####....",
        ".#####....",
        "...###....",
        "...###....",
        "...###....",
        "...###....",
        ".#######..",
        ".#######.."],
    2: ["..######..",
        ".########.",
        ".##....##.",
        ".......##.",
        ".....###..",
        "...###....",
        ".###......",
        ".##.......",
        ".########.",
        ".########."],
    3: [".#######..",
        ".########.",
        ".......##.",
        ".......##.",
        "...#####..",
        "...#####..",
        ".......##.",
        ".......##.",
        ".########.",
        ".#######.."],
    4: ["..##..##..",
        "..##..##..",
        ".##...##..",
        ".##...##..",
        ".########.",
        ".########.",
        "......##..",
        "......##..",
        "......##..",
        "......##.."],
    5: [".########.",
        ".########.",
        ".##.......",
        ".##.......",
        ".#######..",
        ".########.",
        ".......##.",
        ".......##.",
        ".########.",
        ".#######.."],
    6: ["..######..",
        ".#######..",
        ".##.......",
        ".##.......",
        ".#######..",
        ".########.",
        ".##....##.",
        ".##....##.",
        ".########.",
        "..######.."],
    7: [".########.",
        ".########.",
        ".......##.",
        "......##..",
        "......##..",
        ".....##...",
        ".....##...",
        "....##....",
        "....##....",
        "....##...."],
    8: ["..######..",
        ".########.",
        ".##....##.",
        ".##....##.",
        "..######..",
        ".########.",
        ".##....##.",
        ".##....##.",
        ".########.",
        "..######.."],
}

_MINE = [
    "................",
    "................",
    ".......M........",
    ".......M........",
    "...M.MMMMM.M....",
    "....MMMMMMM.....",
    "...MMggMMMMM....",
    "...MMggMMMMM....",
    ".MMMMMMMMMMMMM..",
    "...MMMMMMMMM....",
    "...MMMMMMMMM....",
    "....MMMMMMM.....",
    "...M.MMMMM.M....",
    ".......M........",
    ".......M........",
    "................",
]

_FLAG = [
    "................",
    "................",
    "................",
    "......FF........",
    "....FFFF........",
    "...FFFFF........",
    "....FFFF........",
    "......FF........",
    ".......K........",
    ".......K........",
    ".....KKKK.......",
    "...KKKKKKKK.....",
    "...KKKKKKKK.....",
    "................",
    "................",
    "................",
]

_QUESTION = [
    "................",
    "................",
    "................",
    ".....KKKK.......",
    "....KK..KK......",
    "....KK..KK......",
    "........KK......",
    ".......KK.......",
    "......KK........",
    "......KK........",
    "................",
    "......KK........",
    "......KK........",
    "................",
    "................",
    "................",
]


def _cross():
    grid = _blank(16, 16)
    for i in range(10):
        grid[3 + i][3 + i] = "X"
        grid[3 + i][12 - i] = "X"
    return _rows(grid)


CELLS = {
    **{f"open{n}": _rows(_stamp(_blank(16, 16), [r.replace("#", str(n)) for r in art], 3, 3))
       for n, art in _DIGITS.items()},
    "mine": _MINE,
    "flag": _FLAG,
    "question": _QUESTION,
    "cross": _cross(),
}

# --- faces: a 24x24 button with a 17x17 face ---------------------------------

_CIRCLE = [
    "......SSSSS......",
    "....SSYYYYYSS....",
    "...SYYYYYYYYYS...",
    "..SYYYYYYYYYYYS..",
    ".SYYYYYYYYYYYYYS.",
    ".SYYYYYYYYYYYYYS.",
    "SYYYYYYYYYYYYYYYS",
    "SYYYYYYYYYYYYYYYS",
    "SYYYYYYYYYYYYYYYS",
    "SYYYYYYYYYYYYYYYS",
    "SYYYYYYYYYYYYYYYS",
    ".SYYYYYYYYYYYYYS.",
    ".SYYYYYYYYYYYYYS.",
    "..SYYYYYYYYYYYS..",
    "...SYYYYYYYYYS...",
    "....SSYYYYYSS....",
    "......SSSSS......",
]

# Features, as (row, art) pairs stamped on the circle.
_EYES = [(5, ".....SS...SS....."), (6, ".....SS...SS.....")]
_SMILE = [(10, "....S.......S...."), (11, ".....S.....S....."), (12, "......SSSSS......")]
_FEATURES = {
    "normal": _EYES + _SMILE,
    "wow": _EYES + [(9, ".......SSS......."), (10, "......S...S......"),
                    (11, "......S...S......"), (12, ".......SSS.......")],
    "dead": [(4, "....S.S...S.S...."), (5, ".....S.....S....."), (6, "....S.S...S.S...."),
             (11, "......SSSSS......"), (12, ".....S.....S....."), (13, "....S.......S....")],
    "cool": [(5, "...SSSSSSSSSSS..."), (6, "...SSSSS.SSSSS..."), (7, "....SSS...SSS....")]
            + _SMILE,
}


def _face(features, pressed):
    grid = [["f"] * 24 for _ in range(24)]
    if pressed:
        for i in range(24):
            grid[0][i] = grid[i][0] = "D"
    else:
        for i in range(2):                       # 2 px raised, diagonal corners
            for x in range(0, 24 - i):
                grid[i][x] = "L"
            for y in range(0, 24 - i):
                grid[y][i] = "L"
            for x in range(i + 1, 24):
                grid[23 - i][x] = "D"
            for y in range(i + 1, 24):
                grid[y][23 - i] = "D"
    face = _stamp(_blank(17, 17), _CIRCLE, 0, 0)
    for row, art in features:
        _stamp(face, [art], 0, row)
    off = 4 if pressed else 3
    return _rows(_stamp(grid, _rows(face), off, off))


FACES = {name: _face(f, pressed=False) for name, f in _FEATURES.items()}
FACES["pressed"] = _face(_FEATURES["normal"], pressed=True)

# --- LED digits: seven tapered segments in 13x23 -----------------------------

_SEGMENTS = {
    "a": [(x, 1) for x in range(2, 11)] + [(x, 2) for x in range(3, 10)] + [(x, 3) for x in range(4, 9)],
    "d": [(x, 21) for x in range(2, 11)] + [(x, 20) for x in range(3, 10)] + [(x, 19) for x in range(4, 9)],
    "g": [(x, 11) for x in range(2, 11)] + [(x, 10) for x in range(3, 10)] + [(x, 12) for x in range(3, 10)],
    "f": [(1, y) for y in range(2, 11)] + [(2, y) for y in range(3, 10)] + [(3, y) for y in range(4, 9)],
    "b": [(11, y) for y in range(2, 11)] + [(10, y) for y in range(3, 10)] + [(9, y) for y in range(4, 9)],
    "e": [(1, y) for y in range(12, 21)] + [(2, y) for y in range(13, 20)] + [(3, y) for y in range(14, 19)],
    "c": [(11, y) for y in range(12, 21)] + [(10, y) for y in range(13, 20)] + [(9, y) for y in range(14, 19)],
}
_LIT = {"0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc", "5": "afgcd",
        "6": "afgedc", "7": "abc", "8": "abcdefg", "9": "abcdfg", "-": "g"}


def _led(lit):
    grid = [["B"] * 13 for _ in range(23)]
    for seg, cells in _SEGMENTS.items():
        for x, y in cells:
            grid[y][x] = "O" if seg in lit else "o"
    return _rows(grid)


LED = {d: _led(lit) for d, lit in _LIT.items()}


def paint(cr, sprite, x, y, colours):
    """One rectangle per run of equal pixels. The caller sets ANTIALIAS_NONE."""
    for dy, row in enumerate(sprite):
        start = 0
        while start < len(row):
            ch = row[start]
            end = start + 1
            while end < len(row) and row[end] == ch:
                end += 1
            if ch != ".":
                cr.set_source_rgb(*rgb(colours[LEGEND[ch]]))
                cr.rectangle(x + start, y + dy, end - start, 1)
                cr.fill()
            start = end
