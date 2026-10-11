"""The Python side of the parity tests: win/replay.c's twin, over session.py.

Both read the same script and must print the same lines and write the same
files. The commands are documented at the top of win/replay.c.
"""

from pathlib import Path

import cairo

from swaysweeper import colours, render
from swaysweeper import geometry as G
from swaysweeper.board import Board
from swaysweeper.game import Game
from swaysweeper.session import Session

LEVELS = ("beginner", "intermediate", "expert")
_MARK_CHAR = {"covered": ".", "flag": "F", "question": "?", "revealed": "#"}


def _points(cells):
    return ";".join(f"{x},{y}" for x, y in sorted(cells)) or "-"


def _held(text):
    return frozenset() if text == "-" else frozenset(int(b) for b in text.split(","))


def format_effects(effects):
    words = ["fx"]
    for effect in effects:
        if effect[0] == "sound":
            words.append(f"sound:{effect[1]}")
        elif effect[0] == "best":
            words.append(f"best:{effect[1]}:{effect[2]}")
        else:
            words.append(effect[0])
    return " ".join(words)


class Replay:
    def __init__(self, outdir):
        self.outdir = Path(outdir)
        self.settings = {"marks": True, "color": True, "sound": False}
        self.best = {level: [999, "Anonymous"] for level in LEVELS}
        self.session = Session(None, self.settings, self.best)
        self.cache = render.CellCache()

    def run(self, line):
        """One script line in, the lines it prints out."""
        words = line.split()
        if not words:
            return []
        cmd, args = words[0], words[1:]
        s = self.session
        if cmd == "new":
            w, h, level, spec = int(args[0]), int(args[1]), args[2], args[3]
            mines = [] if spec == "-" else [tuple(int(v) for v in p.split(","))
                                           for p in spec.split(";")]
            return [format_effects(s.new(Game(level, Board(w, h, mines))))]
        if cmd == "press":
            return [format_effects(s.press(int(args[0]), int(args[1]), int(args[2]),
                                           shift=args[3] == "1", held=_held(args[4])))]
        if cmd == "release":
            return [format_effects(s.release(int(args[0]), int(args[1]), int(args[2]),
                                             held=_held(args[3])))]
        if cmd == "motion":
            return [format_effects(s.motion(int(args[0]), int(args[1])))]
        if cmd == "key":
            return [format_effects(s.key(args[0]))]
        if cmd == "tick":
            return [format_effects(s.tick())]
        if cmd == "settings":
            for pair in args:
                key, value = pair.split("=")
                self.settings[key] = value == "1"
            return []
        if cmd == "dump":
            return self._dump()
        if cmd == "render":
            self._render(args[0])
            return []
        raise ValueError(f"unknown command {cmd!r}")

    def _dump(self):
        s, g = self.session, self.session.game
        b = g.board
        face, pressed, cursor = s.paint_state()
        cur = "-" if cursor is None else f"{cursor[0]},{cursor[1]}"
        best = ",".join(str(self.best[level][0]) for level in LEVELS)
        return [
            f"dump status={g.status} state={b.state} revealed={b.revealed_count} "
            f"counter={g.counter()} seconds={g.seconds} running={int(g.timer_running)} "
            f"paused={int(g.paused)} mode={s.gestures.mode or 'none'} face={face} "
            f"cursor={cur} best={best}",
            "marks=" + "/".join("".join(_MARK_CHAR[m] for m in row) for row in b.marks),
            "exploded=" + _points(b.exploded),
            "pressed=" + _points(pressed),
        ]

    def _render(self, name):
        g = self.session.game
        lay = G.layout(g.board.width, g.board.height)
        surf = cairo.ImageSurface(cairo.FORMAT_RGB24, lay.width, lay.height)
        face, pressed, cursor = self.session.paint_state()
        palette = colours.WIN95 if self.settings["color"] else colours.MONO
        render.draw(cairo.Context(surf), g, palette, pressed=pressed, face=face, cursor=cursor,
                    cache=self.cache)
        surf.flush()
        if surf.get_stride() != 4 * lay.width:
            raise ValueError("unexpected Cairo stride")
        data = bytes(surf.get_data())      # little-endian RGB24: B, G, R, unused
        rgb = bytearray(lay.width * lay.height * 3)
        rgb[0::3], rgb[1::3], rgb[2::3] = data[2::4], data[1::4], data[0::4]
        (self.outdir / name).write_bytes(f"P6\n{lay.width} {lay.height}\n255\n".encode()
                                         + bytes(rgb))
