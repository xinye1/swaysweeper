"""winmine's client-area geometry at zoom 1, in logical pixels. No GTK.

From drawing.c:337-383 (DrawHUDRectangles) with two corrections, both from
the on-screen game rather than the decompiled source:
- the timer's x drops a `WindowWidthInPixels` term (the Win32 non-client
  border leaking into a client coordinate), so the timer mirrors the counter;
- the counter box's top is 15, not 16, like the timer's — the digits are
  drawn at y = 16, inside a 1 px bevel.
The bevel directions follow the screen too: frame raised, the rest sunken.
"""

from typing import NamedTuple

CELL = 16
DIGIT_W, DIGIT_H = 13, 23
FACE = 24
BOARD_X, BOARD_Y = 12, 55
DIGIT_Y = 16
FACE_Y = 16
# Logical pixels reserved for the menu bar, sway's border and the bar when
# judging whether Zoom x2 fits the monitor (GTK4 exposes no work area).
CHROME_ALLOWANCE = 96


class Rect(NamedTuple):
    left: int
    top: int
    right: int      # inclusive
    bottom: int     # inclusive
    bevel: int
    style: str      # "raised" | "sunken" | "flat"


class Layout(NamedTuple):
    width: int
    height: int
    frame: Rect
    panel: Rect
    counter: Rect
    timer: Rect
    smiley: Rect
    board: Rect
    counter_x: tuple
    timer_x: tuple
    face_x: int


def game_size(w, h):
    return CELL * w + 24, CELL * h + 67


def layout(w, h):
    xr, yb = game_size(w, h)
    face_x = (xr - FACE) // 2
    return Layout(
        width=xr,
        height=yb,
        frame=Rect(0, 0, xr - 1, yb - 1, 3, "raised"),
        panel=Rect(9, 9, xr - 10, 45, 2, "sunken"),
        counter=Rect(16, 15, 56, 39, 1, "sunken"),
        timer=Rect(xr - 57, 15, xr - 17, 39, 1, "sunken"),
        smiley=Rect(face_x - 1, 15, face_x + FACE, 40, 1, "flat"),
        board=Rect(9, 52, xr - 10, yb - 10, 3, "sunken"),
        counter_x=(17, 30, 43),
        timer_x=(xr - 56, xr - 43, xr - 30),
        face_x=face_x,
    )


def cell_at(lay, x, y):
    """Board square under game-area point (x, y), or None."""
    w = (lay.width - 24) // CELL
    h = (lay.height - 67) // CELL
    cx = int((x - BOARD_X) // CELL)
    cy = int((y - BOARD_Y) // CELL)
    if x < BOARD_X or y < BOARD_Y or not (0 <= cx < w and 0 <= cy < h):
        return None
    return cx, cy


def on_face(lay, x, y):
    return lay.face_x <= x < lay.face_x + FACE and FACE_Y <= y < FACE_Y + FACE


def zoom_fits(w, h, zoom, mon_w, mon_h):
    gw, gh = game_size(w, h)
    return gw * zoom <= mon_w and gh * zoom + CHROME_ALLOWANCE <= mon_h
