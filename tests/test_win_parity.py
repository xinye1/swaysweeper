"""win/core.c against the Python implementation, script by script (spec §5).

Builds win/replay with the system C compiler ($CC, else cc, else gcc), or
uses $SWAYSWEEPER_REPLAY as the Windows CI job does; runs each script
through it and through tests/replay.py; compares every printed line and
every written file. Skipped when there's no C compiler.
"""

import os
import random
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from swaysweeper import geometry as G
from swaysweeper.game import DIFFICULTIES
from tests.replay import Replay

ROOT = Path(__file__).resolve().parent.parent
_exe = None
_tmp = None


def setUpModule():
    global _exe, _tmp
    prebuilt = os.environ.get("SWAYSWEEPER_REPLAY")
    if prebuilt:
        _exe = str(Path(prebuilt).resolve())
        return
    cc = shlex.split(os.environ["CC"]) if os.environ.get("CC") else \
        [shutil.which("cc") or shutil.which("gcc")]
    if cc[0] is None:
        raise unittest.SkipTest("no C compiler")
    _tmp = tempfile.TemporaryDirectory()
    _exe = os.path.join(_tmp.name, "replay")
    subprocess.run([*cc, "-std=c11", "-O2", "-Wall", "-Wextra", "-pedantic", "-Werror",
                    "-o", _exe, str(ROOT / "win" / "replay.c"), str(ROOT / "win" / "core.c"),
                    "-lm"], check=True)


def tearDownModule():
    if _tmp is not None:
        _tmp.cleanup()


# --- script helpers ------------------------------------------------------------

def centre(x, y):
    return G.BOARD_X + G.CELL * x + 8, G.BOARD_Y + G.CELL * y + 8


def click(x, y, button=1):
    px, py = centre(x, y)
    return [f"press {button} {px} {py} 0 -", f"release {button} {px} {py} {button}"]


def mines(cells):
    return ";".join(f"{x},{y}" for x, y in cells) or "-"


WALLED = "new 9 9 beginner " + mines([(4, y) for y in range(9)] + [(8, 8)])
FACE = (G.layout(9, 9).face_x + 12, G.FACE_Y + 12)


def random_board(rng):
    level = rng.choice(["beginner", "intermediate", "expert", "custom"])
    if level == "custom":
        w, h = rng.randint(9, 30), rng.randint(9, 24)
        m = rng.randint(10, min((w - 1) * (h - 1), 999))
    else:
        w, h, m = DIFFICULTIES[level]
    cells = [(x, y) for y in range(h) for x in range(w)]
    return f"new {w} {h} {level} " + mines(rng.sample(cells, m))


KEY_NAMES = ["Left", "Right", "Up", "Down", "h", "j", "k", "l", "space", "Return",
             "f", "c", "question", "x"]


def random_walk(seed, sessions, steps, render_every=0):
    """A script of random input, with a `new` answering every new_game effect.

    Generated against the Python session (so it can see those effects);
    render lines are emitted but not run here.
    """
    rng = random.Random(seed)
    script, held = [], set()
    with tempfile.TemporaryDirectory() as tmp:
        sim = Replay(tmp)

        def emit(line):
            script.append(line)
            return [] if line.startswith(("render", "wav")) else sim.run(line)

        for n in range(sessions):
            emit(random_board(rng))
            for step in range(steps):
                b = sim.session.game.board
                gw, gh = G.game_size(b.width, b.height)
                roll = rng.random()
                if roll < 0.1:
                    px, py = G.layout(b.width, b.height).face_x + 12, G.FACE_Y + 12
                elif roll < 0.8:
                    px, py = centre(rng.randrange(b.width), rng.randrange(b.height))
                    px, py = px + rng.randint(-8, 7), py + rng.randint(-8, 7)
                else:
                    px, py = rng.randint(-10, gw + 10), rng.randint(-10, gh + 10)
                held_text = ",".join(map(str, sorted(held))) or "-"
                roll, out = rng.random(), []
                if roll < 0.3:
                    free = [b for b in (1, 1, 1, 2, 3, 3) if b not in held]
                    if free:
                        button = rng.choice(free)
                        out = emit(f"press {button} {px} {py} {int(rng.random() < 0.1)} "
                                   f"{held_text}")
                        held.add(button)
                    else:
                        out = emit(f"motion {px} {py}")
                elif roll < 0.55:
                    if held:                        # held_text includes it, as GTK's mask does
                        button = rng.choice(sorted(held))
                        out = emit(f"release {button} {px} {py} {held_text}")
                        held.discard(button)
                    else:
                        out = emit(f"motion {px} {py}")
                elif roll < 0.7:
                    out = emit(f"motion {px} {py}")
                elif roll < 0.85:
                    out = emit(f"key {rng.choice(KEY_NAMES)}")
                elif roll < 0.95:
                    out = emit("tick")
                else:
                    if rng.random() < 0.3:
                        held.clear()                # a release delivered elsewhere
                    emit(f"settings marks={rng.randint(0, 1)} color={rng.randint(0, 1)} "
                         f"sound={rng.randint(0, 1)}")
                if out and "new_game" in out[0].split():
                    emit(random_board(rng))
                emit("dump")
                if render_every and step % render_every == render_every - 1:
                    emit(f"render walk-{seed}-{n}-{step}.ppm")
    return script


# --- the comparison ------------------------------------------------------------

class Parity(unittest.TestCase):
    maxDiff = None

    def check(self, script):
        with tempfile.TemporaryDirectory() as tmp:
            py_dir, c_dir = Path(tmp, "py"), Path(tmp, "c")
            py_dir.mkdir()
            c_dir.mkdir()
            replay = Replay(py_dir)
            expected = [out for line in script for out in replay.run(line)]
            got = subprocess.run([_exe, str(c_dir)], input="\n".join(script) + "\n",
                                 capture_output=True, text=True, check=True).stdout.splitlines()
            for i, (want, have) in enumerate(zip(expected, got)):
                if want != have:
                    self.fail(f"output line {i} differs\n  python: {want}\n  c:      {have}")
            self.assertEqual(len(got), len(expected), "C printed a different number of lines")
            for path in sorted(py_dir.iterdir()):
                other = c_dir / path.name
                self.assertTrue(other.exists(), f"C wrote no {path.name}")
                a, b = path.read_bytes(), other.read_bytes()
                if a != b:
                    at = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
                    self.fail(f"{path.name} differs at byte {at} (sizes {len(a)}, {len(b)})")
        return expected


class Rules(Parity):
    def test_walled_board(self):
        self.check([WALLED, *click(0, 0), "dump", "tick", "tick", "dump",
                    *click(5, 4, 3), *click(5, 4, 3), *click(3, 4, 3), "dump",
                    *click(4, 0), "dump", "tick", "dump"])

    def test_first_click_on_a_mine_relocates_it(self):
        self.check(["new 9 9 beginner " + mines([(0, 0), (8, 8)] + [(x, 8) for x in range(8)]),
                    *click(0, 0), "dump"])

    def test_chord_with_a_wrong_flag_loses(self):
        cells = [(1, 1), (8, 8), (6, 0), (7, 0), (8, 0), (6, 1), (7, 1), (8, 1), (6, 2), (7, 2)]
        px, py = centre(0, 0)
        self.check(["settings sound=1", "new 9 9 beginner " + mines(cells), *click(0, 0),
                    *click(0, 1, 3), f"press 2 {px} {py} 0 -", f"release 2 {px} {py} 2", "dump"])

    def test_one_click_win_sets_a_best_time(self):
        self.check(["settings sound=1", "new 9 9 beginner 8,8", *click(0, 0), "dump",
                    "new 9 9 beginner 8,8", "tick", *click(0, 0), "dump"])

    def test_both_buttons_chord_and_right_after_left_does_not_mark(self):
        px, py = centre(3, 4)
        self.check([WALLED, *click(3, 4), *click(4, 3, 3), *click(4, 4, 3), *click(4, 5, 3),
                    f"press 1 {px} {py} 0 -", f"press 3 {px} {py} 0 1", "dump",
                    f"release 3 {px} {py} 1,3", f"release 1 {px} {py} 1", "dump"])

    def test_drag_off_and_release(self):
        px, py = centre(0, 0)
        self.check([WALLED, f"press 1 {px} {py} 0 -", "motion -20 -20", "dump",
                    "release 1 -20 -20 1", "dump"])

    def test_face_asks_for_a_new_game(self):
        fx, fy = FACE
        self.check([WALLED, *click(0, 0), f"press 1 {fx} {fy} 0 -", "dump", "motion 0 0",
                    "dump", f"motion {fx} {fy}", f"release 1 {fx} {fy} 1", WALLED, "dump"])

    def test_keys(self):
        self.check([WALLED, "key space", "key Up", *["key h"] * 5, "key k", "dump",
                    "key l", "key l", "key l", "key j", "key space", "key f", "key c", "key x",
                    "key question", "key Return", "dump", *click(0, 0), "dump"])

    def test_marks_off_skips_the_question(self):
        self.check([WALLED, "settings marks=0", *click(2, 2, 3), *click(2, 2, 3), "dump",
                    "settings marks=1", *click(2, 2, 3), *click(2, 2, 3), "dump"])

    def test_counter_clamps_at_minus_99(self):
        top = [(x, y) for y in range(4) for x in range(30)][:99]
        flags = [line for y in range(5, 12) for x in range(30) for line in click(x, y, 3)]
        self.check(["new 30 16 expert " + mines(top), *flags, "dump"])

    def test_largest_custom_board(self):
        cells = [(x, y) for y in range(24) for x in range(30)]
        self.check(["new 30 24 custom " + mines(cells[53:]), *click(0, 0), "dump",
                    "key Down", "key Down", "dump"])

    def test_timer_stops_at_999(self):
        self.check([WALLED, *click(0, 0), *["tick"] * 1000, "dump"])


class RandomWalk(Parity):
    def test_random_walk(self):
        self.check(random_walk(seed=1, sessions=60, steps=50))


if __name__ == "__main__":
    unittest.main()
