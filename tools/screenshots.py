#!/usr/bin/python3
"""Render the README's screenshots: one lost Intermediate board, per colour set.

    tools/screenshots.py [NAME=colors.toml ...]

Always writes screenshots/win95.png; each NAME=FILE adds screenshots/NAME.png
drawn from that theme file (render one with dotfiles' `theme`, or point at
~/.config/swaysweeper/colors.gen.toml). Offscreen Cairo, so no window opens;
the board is the game area only, without the menu bar or sway's border.
"""

import random
import sys
from pathlib import Path

import cairo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from swaysweeper import geometry as G  # noqa: E402
from swaysweeper import render, theme  # noqa: E402
from swaysweeper.board import COVERED, REVEALED, Board  # noqa: E402
from swaysweeper.game import Game  # noqa: E402

ZOOM = 2


def lost_game():
    """The same board every time: a first click that opens a good region,
    some right flags, one wrong flag, a ?, then a mine."""
    for seed in range(1000):
        board = Board.random(16, 16, 40, random.Random(seed))
        game = Game("intermediate", board)
        game.release(7, 8)
        if 70 <= board.revealed_count <= 120 and not board.over:
            break
    border = [(x, y) for y in range(16) for x in range(16)
              if board.marks[y][x] == COVERED
              and any(board.marks[ny][nx] == REVEALED for nx, ny in board.neighbours(x, y))]
    mines = [c for c in border if board.is_mine(*c)]
    safe = [c for c in border if not board.is_mine(*c)]
    for x, y in mines[:6]:
        game.mark(x, y, True)
    game.mark(*safe[0], True)                       # a wrong flag
    game.mark(*safe[1], True)
    game.mark(*safe[1], True)                       # flag -> ?
    game.seconds = 87
    game.release(*mines[6])                         # and the mine that ends it
    assert board.over
    return game


def shoot(game, colours, out):
    lay = G.layout(game.board.width, game.board.height)
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, lay.width * ZOOM, lay.height * ZOOM)
    cr = cairo.Context(surface)
    cr.scale(ZOOM, ZOOM)
    render.draw(cr, game, colours, face="dead")
    out.parent.mkdir(exist_ok=True)
    surface.write_to_png(str(out))
    print(out.relative_to(ROOT))


def main(argv):
    game = lost_game()
    shoot(game, theme.WIN95, ROOT / "screenshots" / "win95.png")
    for arg in argv:
        name, _, path = arg.partition("=")
        colours, problems = theme.load_first(path)
        if problems:
            sys.exit(f"{path}: " + "; ".join(problems))
        shoot(game, colours, ROOT / "screenshots" / f"{name}.png")


if __name__ == "__main__":
    main(sys.argv[1:])
