"""Paint the game area at 1:1 logical pixels. The caller translates and scales.

Cells are rendered once per (name, colours) into 16x16 surfaces and painted
with FILTER_NEAREST, so an Expert redraw is 480 paints, not thousands of
rectangles, and zoom stays crisp.
"""

import cairo

from . import geometry as G
from . import sprites
from .theme import rgb

_BEVEL = {"raised": ("light", "shadow"), "sunken": ("shadow", "light"),
          "flat": ("shadow", "shadow")}


def counter_text(n):
    return f"-{-n:02d}" if n < 0 else f"{n:03d}"


def _fill(cr, colour, x, y, w, h):
    cr.set_source_rgb(*rgb(colour))
    cr.rectangle(x, y, w, h)
    cr.fill()


def bevel(cr, r, colours):
    """`r.bevel` px lines inside Rect r; the top-left colour wins the corners
    above the diagonal, as Windows draws it."""
    first, second = _BEVEL[r.style]
    cr.set_source_rgb(*rgb(colours[first]))
    for i in range(r.bevel):
        cr.rectangle(r.left, r.top + i, r.right - i - r.left + 1, 1)
        cr.rectangle(r.left + i, r.top, 1, r.bottom - i - r.top + 1)
    cr.fill()
    cr.set_source_rgb(*rgb(colours[second]))
    for i in range(r.bevel):
        cr.rectangle(r.left + i + 1, r.bottom - i, r.right - r.left - i, 1)
        cr.rectangle(r.right - i, r.top + i + 1, 1, r.bottom - r.top - i)
    cr.fill()


_COVERED = {"covered": None, "flag": "flag", "question": "question"}
_OVERLAY = {"mine": "mine", "exploded": "mine", "wrong_flag": "mine",
            "question_pressed": "question"}


def draw_cell(cr, name, colours):
    if name in _COVERED:
        _fill(cr, colours["face"], 0, 0, 16, 16)
        bevel(cr, G.Rect(0, 0, 15, 15, 2, "raised"), colours)
        if _COVERED[name]:
            sprites.paint(cr, sprites.CELLS[_COVERED[name]], 0, 0, colours)
        return
    _fill(cr, colours["exploded" if name == "exploded" else "revealed"], 0, 0, 16, 16)
    _fill(cr, colours["grid"], 0, 0, 16, 1)
    _fill(cr, colours["grid"], 0, 0, 1, 16)
    overlay = _OVERLAY.get(name)
    if name.startswith("open") and name != "open0":
        overlay = name
    if overlay:
        sprites.paint(cr, sprites.CELLS[overlay], 0, 0, colours)
    if name == "wrong_flag":
        sprites.paint(cr, sprites.CELLS["cross"], 0, 0, colours)


class CellCache:
    def __init__(self):
        self._key = None
        self._colours = None
        self._surfaces = {}

    def prepare(self, colours):
        key = tuple(sorted(colours.items()))
        if key != self._key:
            self._key, self._colours, self._surfaces = key, dict(colours), {}

    def get(self, name):
        surf = self._surfaces.get(name)
        if surf is None:
            surf = cairo.ImageSurface(cairo.FORMAT_RGB24, 16, 16)
            cr = cairo.Context(surf)
            cr.set_antialias(cairo.ANTIALIAS_NONE)
            draw_cell(cr, name, self._colours)
            self._surfaces[name] = surf
        return surf


def _digits(cr, xs, text, colours):
    for x, ch in zip(xs, text):
        sprites.paint(cr, sprites.LED[ch], x, G.DIGIT_Y, colours)


def draw(cr, game, colours, *, pressed=frozenset(), face="normal", cursor=None, cache=None):
    cr.set_antialias(cairo.ANTIALIAS_NONE)
    b = game.board
    lay = G.layout(b.width, b.height)
    _fill(cr, colours["face"], 0, 0, lay.width, lay.height)
    for r in (lay.frame, lay.panel, lay.counter, lay.timer, lay.smiley, lay.board):
        bevel(cr, r, colours)
    _digits(cr, lay.counter_x, counter_text(game.counter()), colours)
    _digits(cr, lay.timer_x, f"{game.seconds:03d}", colours)
    sprites.paint(cr, sprites.FACES[face], lay.face_x, G.FACE_Y, colours)

    cache = cache or CellCache()
    cache.prepare(colours)
    for y in range(b.height):
        for x in range(b.width):
            name = b.cell_face(x, y)
            if (x, y) in pressed:
                name = {"covered": "open0", "question": "question_pressed"}.get(name, name)
            px, py = G.BOARD_X + G.CELL * x, G.BOARD_Y + G.CELL * y
            cr.set_source_surface(cache.get(name), px, py)
            cr.get_source().set_filter(cairo.FILTER_NEAREST)
            cr.rectangle(px, py, G.CELL, G.CELL)
            cr.fill()

    if cursor is not None:
        cx, cy = G.BOARD_X + G.CELL * cursor[0], G.BOARD_Y + G.CELL * cursor[1]
        c = colours["cursor"]
        _fill(cr, c, cx, cy, 16, 1)
        _fill(cr, c, cx, cy + 15, 16, 1)
        _fill(cr, c, cx, cy, 1, 16)
        _fill(cr, c, cx + 15, cy, 1, 16)
