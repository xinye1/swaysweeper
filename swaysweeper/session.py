"""One game window's play, minus the toolkit: events in, effects out. No GTK.

app.py and view.py host it on Linux; win/core.c ports it for Windows, and
tests/test_win_parity.py replays the same scripts through both.

Pointer coordinates are game-area pixels at zoom 1. Key names are
`Left Right Up Down h j k l space Return f c question`; anything else is
unhandled. Effects come back in the order a host applies them:

  ("save",) | ("delete",)   write the game file, or remove it (not PLAYING)
  ("sound", name)           tick, win or lose; only with Sound on
  ("best", level, seconds)  a new best time, already recorded as Anonymous
  ("new_game",)             build a fresh Game and pass it to new()
  ("show_keys",)            open the Keys dialog
  ("unhandled",)            a key this session doesn't use
  ("redraw",)               repaint
"""

from . import geometry as G
from .board import LOST, PLAYING, READY, REVEALED, WON
from .game import DIFFICULTIES
from .gestures import Gestures

KEYS = """Mouse
  Left click             open a square
  Right click            flag, then ?, then clear
  Both buttons, middle,  open around a satisfied number
  or Shift+left
  Smiley                 new game

Keyboard
  Arrows or h j k l      move the cursor
  Space or Enter         open (around a number: chord)
  f                      flag, then ?, then clear
  c                      open around a number
  F2                     new game
  ?                      this list
  Ctrl+Q                 exit"""

MOVES = {"Left": (-1, 0), "h": (-1, 0), "Right": (1, 0), "l": (1, 0),
         "Up": (0, -1), "k": (0, -1), "Down": (0, 1), "j": (0, 1)}


class Session:
    def __init__(self, game, settings, best):
        """`settings` and `best` are the host's dicts, shared, not copied."""
        self.game = game
        self.settings = settings
        self.best = best
        self.gestures = Gestures()
        self.cursor = None

    # --- events --------------------------------------------------------------

    def press(self, button, px, py, shift=False, held=None):
        cell, face = self._hit(px, py)
        return self._run(self.gestures.press(button, cell, face, shift=shift,
                                             active=not self.game.board.over, held=held))

    def release(self, button, px, py, held=None):
        cell, face = self._hit(px, py)
        return self._run(self.gestures.release(button, cell, face, held=held))

    def motion(self, px, py):
        cell, face = self._hit(px, py)
        self.gestures.motion(cell, face)
        had_cursor = self.cursor is not None
        if cell is not None:
            self.cursor = None
        if self.gestures.mode or (had_cursor and self.cursor is None):
            return [("redraw",)]
        return []

    def key(self, name):
        b = self.game.board
        if name in MOVES:
            if self.cursor is None:
                self.cursor = (b.width // 2, b.height // 2)
            else:
                dx, dy = MOVES[name]
                x, y = self.cursor
                self.cursor = (min(max(x + dx, 0), b.width - 1),
                               min(max(y + dy, 0), b.height - 1))
            return [("redraw",)]
        if name == "question":
            return [("show_keys",)]
        if self.cursor is None:
            return [("unhandled",)]
        x, y = self.cursor
        if name in ("space", "Return"):
            kind = "chord" if b.marks[y][x] == REVEALED else "reveal"
        elif name == "f":
            kind = "mark"
        elif name == "c":
            kind = "chord"
        else:
            return [("unhandled",)]
        return self._run([(kind, x, y)])

    def tick(self):
        if not self.game.tick():
            return []
        return [("save",)] + self._sound("tick") + [("redraw",)]

    def new(self, game):
        self.game = game
        self.cursor = None
        self.gestures.mode = None
        return [("delete",), ("redraw",)]

    def paint_state(self):
        b = self.game.board
        return (self.gestures.face(self.game.status),
                self.gestures.preview(b.width, b.height), self.cursor)

    # --- internals -----------------------------------------------------------

    def _hit(self, px, py):
        b = self.game.board
        lay = G.layout(b.width, b.height)
        return G.cell_at(lay, px, py), G.on_face(lay, px, py)

    def _run(self, actions):
        effects = []
        for action in actions:
            effects += self._act(action)
        return effects + [("redraw",)]

    def _sound(self, name):
        return [("sound", name)] if self.settings["sound"] else []

    def _act(self, action):
        if action[0] == "new":
            return [("new_game",)]
        kind, x, y = action
        game = self.game
        before = game.status
        if kind == "mark":
            game.mark(x, y, self.settings["marks"])
        else:
            game.release(x, y, chord=kind == "chord")
        after = game.status
        effects = [("save",) if after == PLAYING else ("delete",)]
        if before == after:
            return effects
        if before == READY and after == PLAYING:
            effects += self._sound("tick")
        elif after == WON:
            effects += self._sound("win")
        elif after == LOST:
            effects += self._sound("lose")
        if after == WON:
            level, seconds = game.difficulty, game.seconds
            if level in DIFFICULTIES and seconds < self.best[level][0]:
                self.best[level] = [seconds, "Anonymous"]
                effects.append(("best", level, seconds))
        return effects
