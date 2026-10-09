# swaysweeper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A faithful clone of Windows 95–2000 Minesweeper (winmine) for sway, drawn in the active dotfiles palette and recoloured live on `theme <name>`.

**Architecture:** Pure-Python rule, layout, colour and state modules (no GTK) carry all the logic and are unit-tested; a thin GTK4 layer (`view.py`, `app.py`, `dialogs.py`) paints through Cairo and turns input into calls on those modules. Colours come from `~/.config/swaysweeper/colors.gen.toml`, rendered by the dotfiles repo's `theme` from one new template, and watched with a Gio file monitor.

**Tech Stack:** Python 3.14 (`/usr/bin/python3`), GTK 4.22 via PyGObject 3.56, pycairo 1.29, stdlib `unittest`, `pw-play` (PipeWire) for sound, GNU make, GNU stow (dotfiles side).

**Spec:** `docs/specs/2026-10-09-swaysweeper-design.md` — read it before starting any task; this plan argues from it. Rules reference: [repnz/ReversingMinesweeper](https://github.com/repnz/ReversingMinesweeper) (`Minesweeper/game.c`, `windowing.c`, `drawing.c`).

## Global Constraints

- Interpreter is **`/usr/bin/python3`** everywhere — tests, launcher shebang, Makefile. The `python3` on `PATH` is a mise shim whose Python lacks `gi`.
- Run tests from the repo root: `/usr/bin/python3 -m unittest discover -s tests -t . -v`.
- `board.py`, `game.py`, `geometry.py`, `store.py`, `gestures.py`, `sound.py`, `cli.py` and `theme.py` (except inside `Watcher`) **must not import `gi`**.
- Application id: `io.github.xinye1.swaysweeper`. Desktop file: `io.github.xinye1.swaysweeper.desktop`.
- The game **never writes** under `~/.config/swaysweeper/`. State goes to `$XDG_STATE_HOME/swaysweeper/` (default `~/.local/state/swaysweeper/`), the sound cache to `$XDG_CACHE_HOME/swaysweeper/`.
- State writes are atomic: temp file in the same directory, `fsync`, `os.replace`.
- No bitmaps or audio files in the repo: sprites are text, sounds are generated.
- Child processes (sound) are fire-and-forget with stdin/stdout/stderr on `subprocess.DEVNULL` — never a pipe.
- Difficulty presets: beginner 9×9/10, intermediate 16×16/40, expert 30×16/99. Custom: width 9–30, height 9–24, mines 10–min((w−1)(h−1), 999), clamped.
- Counter display clamps to −99…999. Timer starts at 1, caps at 999, always stops on win or loss.
- Commit after every task with a conventional message ending in the two attribution lines:
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_014cXNm1YtXA8z8QgkySFjrB
  ```
- Dotfiles side: obey `~/repos/dotfiles/CLAUDE.md` — never inline a hex outside `palettes.toml`, `stow -n -v` before `stow`, never run `./setup.sh <palette>`.

## Review Focus

The inputs the spec implies but no rule test naturally reaches, most likely to bite first. Each has a test in its owning task.

1. **A theme switch while a game is open, twice in quick succession** — the game must end on the second palette's colours, never on Win95 and never on the first. *(Task 4: `test_two_quick_writes_end_on_the_second`.)*
2. **A chord gesture released outside the board or the window** — nothing must happen: no reveal, no timer start. *(Task 8: `test_chord_released_off_board_does_nothing`.)*
3. **A hand-edited `settings.json` with an impossible custom field** (`[30, 24, 5000]`) — clamp, don't quarantine the whole file. *(Task 5: `test_custom_field_is_clamped_not_rejected`.)*
4. **A `game.json` whose difficulty and board disagree** (an Expert label on a 9×9 board, e.g. from a future version) — treated as corrupt, moved to `.bad`, fresh game. *(Task 2: `test_rejects_a_preset_with_the_wrong_dimensions`.)*
5. **A crash between `mkstemp` and `os.replace`** leaving a stray `.game.*.tmp` — the next load and save must be unaffected. *(Task 5: `test_a_stray_temp_file_does_not_disturb_load_or_save`.)*

---

### Task 1: Scaffold and board rules

**Files:**
- Create: `swaysweeper/__init__.py`, `swaysweeper/board.py`, `tests/__init__.py`, `tests/test_board.py`, `.gitignore`

**Interfaces:**
- Consumes: nothing.
- Produces (`swaysweeper.board`):
  - constants `COVERED, FLAG, QUESTION, REVEALED` (mark strings) and `READY, PLAYING, WON, LOST` (state strings)
  - `class Board(width: int, height: int, mines: Iterable[tuple[int,int]])`, `Board.random(width, height, mines: int, rng: random.Random) -> Board`
  - attributes `width`, `height`, `marks: list[list[str]]` (`marks[y][x]`), `state: str`, `exploded: set[tuple]`, `revealed_count: int`
  - properties `mine_count -> int`, `over -> bool`
  - methods `in_bounds(x,y)`, `is_mine(x,y)`, `mine_cells() -> frozenset`, `neighbours(x,y)`, `count(x,y) -> int`, `flags_around(x,y) -> int`, `counter() -> int` (unclamped), `toggle_mark(x,y,marks_enabled) -> bool`, `reveal(x,y) -> bool`, `chord(x,y) -> bool`, `cell_face(x,y) -> str`, `to_dict() -> dict`, `Board.from_dict(d) -> Board` (raises `ValueError`)
  - `cell_face` returns one of `"covered" "flag" "question" "open0".."open8" "mine" "exploded" "wrong_flag"`

- [ ] **Step 1: Scaffold the package**

`swaysweeper/__init__.py`:
```python
"""swaysweeper — the classic Windows Minesweeper, in your palette's colours."""

__version__ = "0.1.0"
```

`tests/__init__.py`: empty file.

`.gitignore`:
```
__pycache__/
*.pyc
```

- [ ] **Step 2: Write the failing tests**

`tests/test_board.py`:
```python
import random
import unittest

from swaysweeper.board import (
    COVERED, FLAG, LOST, PLAYING, QUESTION, READY, REVEALED, WON, Board,
)

SCAN = [(x, y) for y in range(8) for x in range(8)]   # 9x9's relocation scan area
WALL = [(2, y) for y in range(5)]                       # a mine column on 5x5
WALL9 = [(4, y) for y in range(9)]                      # 9x9 split in two: a first
                                                        # click on the left never wins


class Placement(unittest.TestCase):
    def test_random_is_seeded(self):
        a = Board.random(9, 9, 10, random.Random(7))
        b = Board.random(9, 9, 10, random.Random(7))
        self.assertEqual(a.mine_cells(), b.mine_cells())
        self.assertEqual(a.mine_count, 10)

    def test_mine_outside_the_board_is_rejected(self):
        with self.assertRaises(ValueError):
            Board(3, 3, [(3, 0)])


class FirstClick(unittest.TestCase):
    def test_mine_moves_to_first_free_square_from_top_left(self):
        b = Board(9, 9, [(0, 0), (1, 0)])
        self.assertTrue(b.reveal(0, 0))
        self.assertEqual(b.mine_cells(), {(1, 0), (2, 0)})
        self.assertEqual(b.marks[0][0], REVEALED)
        self.assertEqual(b.state, PLAYING)

    def test_clicked_square_is_never_the_destination(self):
        b = Board(9, 9, [(0, 0)])
        b.reveal(0, 0)
        self.assertEqual(b.mine_cells(), {(1, 0)})

    def test_scan_skips_last_row_and_last_column(self):
        # Only (7, 7) is free inside the scan; (8, 1) is free too and would
        # come first in a full row-major scan — winmine never looks there.
        b = Board(9, 9, SCAN[:-1] + [(8, 0)])
        b.reveal(8, 0)
        self.assertIn((7, 7), b.mine_cells())
        self.assertNotIn((8, 0), b.mine_cells())
        self.assertNotIn((8, 1), b.mine_cells())

    def test_no_free_square_ignores_the_click(self):
        b = Board(9, 9, SCAN + [(8, 8)])
        self.assertFalse(b.reveal(8, 8))
        self.assertEqual(b.state, READY)
        self.assertEqual(b.marks[8][8], COVERED)
        self.assertEqual(b.mine_cells(), frozenset(SCAN + [(8, 8)]))

    def test_first_click_may_land_on_a_number(self):
        b = Board(9, 9, [(1, 1)])
        b.reveal(0, 0)
        self.assertEqual(b.cell_face(0, 0), "open1")
        self.assertEqual(b.revealed_count, 1)

    def test_relocation_only_on_the_very_first_reveal(self):
        b = Board(9, 9, WALL9)
        b.reveal(0, 0)
        self.assertTrue(b.reveal(4, 0))
        self.assertEqual(b.state, LOST)


class Flood(unittest.TestCase):
    def test_zero_floods_up_to_the_numbers(self):
        b = Board(5, 5, WALL)
        b.reveal(0, 0)
        self.assertEqual(b.revealed_count, 10)          # columns 0 and 1
        self.assertEqual(b.marks[0][3], COVERED)
        self.assertEqual(b.cell_face(1, 0), "open2")
        self.assertEqual(b.state, PLAYING)

    def test_flood_clears_question_but_not_flags(self):
        b = Board(5, 5, WALL)
        b.toggle_mark(0, 3, True)
        b.toggle_mark(0, 3, True)                        # flag -> ?
        b.toggle_mark(0, 4, True)                        # flag
        b.reveal(0, 0)
        self.assertEqual(b.marks[3][0], REVEALED)
        self.assertEqual(b.marks[4][0], FLAG)

    def test_flag_is_not_revealable_but_question_is(self):
        b = Board(9, 9, [(8, 8)])
        b.toggle_mark(0, 0, True)
        self.assertFalse(b.reveal(0, 0))
        b.toggle_mark(0, 0, True)                        # -> ?
        self.assertTrue(b.reveal(0, 0))


class Marks(unittest.TestCase):
    def test_cycle_with_marks_on(self):
        b = Board(9, 9, [(8, 8)])
        seen = []
        for _ in range(3):
            b.toggle_mark(0, 0, True)
            seen.append(b.marks[0][0])
        self.assertEqual(seen, [FLAG, QUESTION, COVERED])

    def test_cycle_with_marks_off(self):
        b = Board(9, 9, [(8, 8)])
        b.toggle_mark(0, 0, False)
        self.assertEqual(b.marks[0][0], FLAG)
        b.toggle_mark(0, 0, False)
        self.assertEqual(b.marks[0][0], COVERED)

    def test_marks_off_leaves_existing_question_marks(self):
        b = Board(9, 9, [(8, 8)])
        b.toggle_mark(0, 0, True)
        b.toggle_mark(0, 0, True)
        b.toggle_mark(1, 0, False)
        self.assertEqual(b.marks[0][0], QUESTION)

    def test_revealed_square_cannot_be_marked(self):
        b = Board(9, 9, WALL9)
        b.reveal(0, 0)
        self.assertEqual(b.state, PLAYING)
        self.assertFalse(b.toggle_mark(0, 0, True))

    def test_counter_goes_negative(self):
        b = Board(9, 9, [(8, 8)])
        for x in range(3):
            b.toggle_mark(x, 0, True)
        self.assertEqual(b.counter(), -2)


class Chord(unittest.TestCase):
    def setUp(self):
        # The column at x = 6 keeps the chord's flood from winning the game.
        self.b = Board(9, 9, [(0, 0), (2, 0)] + [(6, y) for y in range(9)])
        self.b.reveal(1, 1)                               # a 2

    def test_unsatisfied_number_does_nothing(self):
        self.b.toggle_mark(0, 0, True)
        self.assertFalse(self.b.chord(1, 1))
        self.assertEqual(self.b.marks[1][0], COVERED)

    def test_satisfied_number_opens_the_rest(self):
        self.b.toggle_mark(0, 0, True)
        self.b.toggle_mark(2, 0, True)
        self.assertTrue(self.b.chord(1, 1))
        for x, y in [(1, 0), (0, 1), (2, 1), (0, 2), (1, 2), (2, 2)]:
            self.assertEqual(self.b.marks[y][x], REVEALED, (x, y))
        self.assertEqual(self.b.state, PLAYING)

    def test_wrong_flags_lose_with_every_hit_mine_exploded(self):
        self.b.toggle_mark(0, 2, True)
        self.b.toggle_mark(1, 2, True)
        self.assertTrue(self.b.chord(1, 1))
        self.assertEqual(self.b.state, LOST)
        self.assertEqual(self.b.exploded, {(0, 0), (2, 0)})
        self.assertEqual(self.b.cell_face(0, 0), "exploded")
        self.assertEqual(self.b.cell_face(0, 2), "wrong_flag")

    def test_chord_on_a_covered_square_does_nothing(self):
        self.assertFalse(self.b.chord(5, 5))


class EndOfGame(unittest.TestCase):
    def test_loss_shows_mines_keeps_right_flags_marks_wrong_ones(self):
        b = Board(9, 9, WALL9 + [(8, 8)])
        b.reveal(0, 0)                                    # opens the left side
        b.toggle_mark(4, 0, True)                         # right flag
        b.toggle_mark(7, 7, True)                         # wrong flag
        b.reveal(8, 8)
        self.assertEqual(b.state, LOST)
        self.assertEqual(b.cell_face(8, 8), "exploded")
        self.assertEqual(b.cell_face(4, 1), "mine")
        self.assertEqual(b.cell_face(4, 0), "flag")
        self.assertEqual(b.cell_face(7, 7), "wrong_flag")
        self.assertFalse(b.reveal(1, 1))

    def test_win_flags_every_mine(self):
        b = Board(3, 3, [(2, 2)])
        b.reveal(0, 0)
        self.assertEqual(b.state, WON)
        self.assertEqual(b.marks[2][2], FLAG)
        self.assertEqual(b.counter(), 0)


class Serialise(unittest.TestCase):
    def test_round_trip(self):
        b = Board(9, 9, WALL9)
        b.reveal(0, 0)
        b.toggle_mark(4, 4, True)
        b.toggle_mark(8, 8, True)
        b.toggle_mark(8, 8, True)
        r = Board.from_dict(b.to_dict())
        self.assertEqual(r.to_dict(), b.to_dict())
        self.assertEqual(r.revealed_count, b.revealed_count)

    def test_rejects_bad_input(self):
        good = Board(9, 9, [(8, 8)]).to_dict()
        for bad in (
            {k: v for k, v in good.items() if k != "marks"},
            dict(good, marks=good["marks"][:-1]),
            dict(good, marks=["!" * 9] * 9),
            dict(good, state="paused"),
            dict(good, mines=[[99, 99]]),
            dict(good, exploded=[[0, 0]]),
        ):
            with self.assertRaises(ValueError):
                Board.from_dict(bad)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `/usr/bin/python3 -m unittest discover -s tests -t . -v`
Expected: ERROR — `ModuleNotFoundError: No module named 'swaysweeper.board'`.

- [ ] **Step 4: Implement `swaysweeper/board.py`**

```python
"""Pure Minesweeper rules, faithful to winmine. No GTK.

References are to the reverse-engineered winmine in
repnz/ReversingMinesweeper (XP build; 2000 shares its rules).
"""

COVERED, FLAG, QUESTION, REVEALED = "covered", "flag", "question", "revealed"
READY, PLAYING, WON, LOST = "ready", "playing", "won", "lost"
STATES = (READY, PLAYING, WON, LOST)

_MARK_CHAR = {COVERED: ".", FLAG: "F", QUESTION: "?", REVEALED: "#"}
_CHAR_MARK = {c: m for m, c in _MARK_CHAR.items()}


class Board:
    def __init__(self, width, height, mines):
        """`mines` is an iterable of (x, y). Use Board.random for a new game."""
        self.width = width
        self.height = height
        self._mines = set(mines)
        for x, y in self._mines:
            if not self.in_bounds(x, y):
                raise ValueError(f"mine {(x, y)} outside {width}x{height}")
        self.marks = [[COVERED] * width for _ in range(height)]
        self.state = READY
        self.exploded = set()
        self.revealed_count = 0

    @classmethod
    def random(cls, width, height, mines, rng):
        cells = [(x, y) for y in range(height) for x in range(width)]
        return cls(width, height, rng.sample(cells, mines))

    # --- queries -------------------------------------------------------------

    @property
    def mine_count(self):
        return len(self._mines)

    @property
    def over(self):
        return self.state in (WON, LOST)

    def in_bounds(self, x, y):
        return 0 <= x < self.width and 0 <= y < self.height

    def is_mine(self, x, y):
        return (x, y) in self._mines

    def mine_cells(self):
        return frozenset(self._mines)

    def neighbours(self, x, y):
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if (dx or dy) and self.in_bounds(x + dx, y + dy):
                    yield x + dx, y + dy

    def count(self, x, y):
        return sum(1 for n in self.neighbours(x, y) if n in self._mines)

    def flags_around(self, x, y):
        return sum(1 for nx, ny in self.neighbours(x, y) if self.marks[ny][nx] == FLAG)

    def counter(self):
        """Mines minus flags, unclamped — the display clamps (game.clamp_counter)."""
        return self.mine_count - sum(row.count(FLAG) for row in self.marks)

    def cell_face(self, x, y):
        """The sprite name for one square, including winmine's end-of-game reveal."""
        mark = self.marks[y][x]
        mine = (x, y) in self._mines
        if self.state == LOST:
            if (x, y) in self.exploded:
                return "exploded"
            if mark == FLAG and not mine:
                return "wrong_flag"
            if mine and mark != FLAG:
                return "mine"
        if mark == REVEALED:
            return f"open{self.count(x, y)}"
        if mark == FLAG:
            return "flag"
        if mark == QUESTION:
            return "question"
        return "covered"

    # --- moves ---------------------------------------------------------------

    def toggle_mark(self, x, y, marks_enabled):
        """Right press: covered -> flag -> ? -> covered (? only with Marks on)."""
        if self.over or not self.in_bounds(x, y):
            return False
        mark = self.marks[y][x]
        if mark == REVEALED:
            return False
        if mark == COVERED:
            new = FLAG
        elif mark == FLAG:
            new = QUESTION if marks_enabled else COVERED
        else:
            new = COVERED
        self.marks[y][x] = new
        return True

    def reveal(self, x, y):
        """Left release. Returns whether anything changed."""
        if self.over or not self.in_bounds(x, y):
            return False
        if self.marks[y][x] in (FLAG, REVEALED):
            return False
        if (x, y) in self._mines:
            if self.revealed_count == 0:          # game.c: NumberOfRevealedBlocks == 0
                if not self._relocate(x, y):
                    return False
            else:
                self._lose({(x, y)})
                return True
        self.state = PLAYING
        self._flood(x, y)
        self._check_win()
        return True

    def chord(self, x, y):
        """Open every covered, unflagged neighbour of a satisfied number."""
        if self.over or not self.in_bounds(x, y):
            return False
        if self.marks[y][x] != REVEALED:
            return False
        n = self.count(x, y)
        if n == 0 or self.flags_around(x, y) != n:
            return False
        hit = set()
        for nx, ny in self.neighbours(x, y):
            if self.marks[ny][nx] in (FLAG, REVEALED):
                continue
            if (nx, ny) in self._mines:
                hit.add((nx, ny))                  # game.c:505 — each one exploded
            else:
                self._flood(nx, ny)
        if hit:
            self._lose(hit)
        else:
            self._check_win()
        return True

    # --- internals -----------------------------------------------------------

    def _relocate(self, x, y):
        # game.c:551-553 loops `row < Height`, `col < Width` from 1 (1-based):
        # the last row and last column are never scanned. The clicked square is
        # still a mine here, so it can never be chosen.
        for ry in range(self.height - 1):
            for rx in range(self.width - 1):
                if (rx, ry) not in self._mines:
                    self._mines.discard((x, y))
                    self._mines.add((rx, ry))
                    return True
        return False

    def _flood(self, x, y):
        stack = [(x, y)]
        while stack:
            cx, cy = stack.pop()
            if self.marks[cy][cx] in (FLAG, REVEALED):
                continue
            self.marks[cy][cx] = REVEALED
            self.revealed_count += 1
            if self.count(cx, cy) == 0:
                stack.extend(self.neighbours(cx, cy))

    def _lose(self, hit):
        self.state = LOST
        self.exploded = set(hit)

    def _check_win(self):
        if self.revealed_count == self.width * self.height - self.mine_count:
            self.state = WON
            for x, y in self._mines:
                self.marks[y][x] = FLAG

    # --- persistence ---------------------------------------------------------

    def to_dict(self):
        return {
            "width": self.width,
            "height": self.height,
            "mines": sorted([x, y] for x, y in self._mines),
            "marks": ["".join(_MARK_CHAR[m] for m in row) for row in self.marks],
            "state": self.state,
            "exploded": sorted([x, y] for x, y in self.exploded),
        }

    @classmethod
    def from_dict(cls, d):
        try:
            board = cls(int(d["width"]), int(d["height"]),
                        [_point(p) for p in d["mines"]])
            rows = d["marks"]
            if len(rows) != board.height or any(len(r) != board.width for r in rows):
                raise ValueError("marks do not match the board size")
            board.marks = [[_CHAR_MARK[c] for c in row] for row in rows]
            if d["state"] not in STATES:
                raise ValueError(f"unknown state {d['state']!r}")
            board.state = d["state"]
            board.exploded = {_point(p) for p in d["exploded"]}
            if not board.exploded <= board._mines:
                raise ValueError("exploded square is not a mine")
            board.revealed_count = sum(row.count(REVEALED) for row in board.marks)
            return board
        except (KeyError, TypeError) as exc:
            raise ValueError(f"bad board: {exc!r}") from exc


def _point(p):
    x, y = p
    return int(x), int(y)
```

Note: `_CHAR_MARK[c]` raises `KeyError` for an unknown character, which the `except` turns into `ValueError`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `/usr/bin/python3 -m unittest discover -s tests -t . -v`
Expected: all `test_board` tests PASS.

- [ ] **Step 6: Mutation check — the scan bounds**

Temporarily change `range(self.height - 1)` / `range(self.width - 1)` in `_relocate` to `range(self.height)` / `range(self.width)`.
Run: `/usr/bin/python3 -m unittest tests.test_board -v`
Expected: `test_scan_skips_last_row_and_last_column` and `test_no_free_square_ignores_the_click` FAIL. Revert and re-run: all PASS.

Then temporarily change `if n == 0 or self.flags_around(x, y) != n` to `if n == 0`. Expected: `test_unsatisfied_number_does_nothing` FAILS. Revert.

- [ ] **Step 7: Commit**

```bash
git add .gitignore swaysweeper tests
git commit -m "feat(board): winmine rules — first-click relocation, flood, marks, chord, win/loss

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014cXNm1YtXA8z8QgkySFjrB"
```

---

### Task 2: Game session — timer, counter, difficulty, resume

**Files:**
- Create: `swaysweeper/game.py`, `tests/test_game.py`

**Interfaces:**
- Consumes: `swaysweeper.board` (Task 1).
- Produces (`swaysweeper.game`):
  - `DIFFICULTIES: dict[str, tuple[int,int,int]]` (`"beginner"|"intermediate"|"expert"` → (w, h, mines)), `TIMER_MAX = 999`, `VERSION = 1`
  - `clamp_custom(width, height, mines) -> tuple[int,int,int]`, `clamp_counter(n) -> int`
  - `class Game(difficulty: str, board: Board)`; `Game.new(difficulty, custom=(9, 9, 10), rng=None) -> Game`
  - attributes `difficulty`, `board`, `seconds: int`, `timer_running: bool`, `paused: bool`
  - `status -> str` (one of board's `READY/PLAYING/WON/LOST`), `ticking -> bool`
  - `release(x, y, chord=False) -> bool`, `mark(x, y, marks_enabled) -> bool`, `tick() -> bool`, `counter() -> int` (clamped)
  - `to_dict() -> dict`, `Game.from_dict(d) -> Game` (raises `ValueError`; result is `paused`)

- [ ] **Step 1: Write the failing tests**

`tests/test_game.py`:
```python
import random
import unittest

from swaysweeper.board import FLAG, LOST, PLAYING, READY, WON, Board
from swaysweeper.game import (
    DIFFICULTIES, TIMER_MAX, Game, clamp_counter, clamp_custom,
)


# Ten mines (a valid beginner board) with a wall at x = 4: a first click on
# the left opens that side only, so the game is still being played.
BEGINNER_WALL = [(4, y) for y in range(9)] + [(8, 8)]


def game_with(mines, w=9, h=9, difficulty="beginner"):
    return Game(difficulty, Board(w, h, mines))


class Difficulty(unittest.TestCase):
    def test_presets(self):
        self.assertEqual(DIFFICULTIES["beginner"], (9, 9, 10))
        self.assertEqual(DIFFICULTIES["intermediate"], (16, 16, 40))
        self.assertEqual(DIFFICULTIES["expert"], (30, 16, 99))
        g = Game.new("expert", rng=random.Random(1))
        self.assertEqual((g.board.width, g.board.height, g.board.mine_count), (30, 16, 99))

    def test_custom_is_clamped(self):
        self.assertEqual(clamp_custom(5, 50, 1), (9, 24, 10))
        self.assertEqual(clamp_custom(30, 24, 5000), (30, 24, 667))
        self.assertEqual(clamp_custom(9, 9, 64), (9, 9, 64))
        self.assertEqual(clamp_custom(9, 9, 65), (9, 9, 64))
        g = Game.new("custom", custom=(100, 3, 2), rng=random.Random(1))
        self.assertEqual((g.board.width, g.board.height, g.board.mine_count), (30, 9, 10))


class Timer(unittest.TestCase):
    def test_starts_at_one_on_the_first_reveal(self):
        g = game_with(BEGINNER_WALL)
        self.assertEqual(g.status, READY)
        g.release(0, 0)
        self.assertEqual(g.seconds, 1)
        self.assertTrue(g.ticking)

    def test_starts_on_a_release_over_a_flag(self):
        g = game_with([(8, 8)])
        g.mark(0, 0, True)
        g.release(0, 0)
        self.assertEqual(g.seconds, 1)
        self.assertEqual(g.board.state, READY)
        self.assertEqual(g.status, PLAYING)

    def test_right_click_alone_does_not_start_it(self):
        g = game_with([(8, 8)])
        g.mark(0, 0, True)
        self.assertEqual(g.seconds, 0)
        self.assertEqual(g.status, READY)

    def test_ticks_and_caps_at_999(self):
        g = game_with(BEGINNER_WALL)
        g.release(0, 0)
        self.assertTrue(g.tick())
        self.assertEqual(g.seconds, 2)
        g.seconds = TIMER_MAX - 1
        self.assertTrue(g.tick())
        self.assertFalse(g.tick())
        self.assertEqual(g.seconds, TIMER_MAX)
        self.assertFalse(g.ticking)

    def test_stops_on_a_loss(self):
        g = game_with(BEGINNER_WALL)
        g.release(0, 0)
        g.release(4, 0)
        self.assertEqual(g.status, LOST)
        self.assertFalse(g.tick())

    def test_stops_on_a_one_click_win(self):
        # Win95/98 left it running; 2000 fixed it, and so do we (spec §1).
        g = game_with([(2, 2)], w=3, h=3)
        g.release(0, 0)
        self.assertEqual(g.status, WON)
        self.assertEqual(g.seconds, 1)
        self.assertFalse(g.tick())

    def test_moves_after_the_end_change_nothing(self):
        g = game_with([(2, 2)], w=3, h=3)
        g.release(0, 0)
        self.assertFalse(g.release(1, 1))
        self.assertFalse(g.mark(2, 2, True))


class Counter(unittest.TestCase):
    def test_clamps(self):
        self.assertEqual(clamp_counter(-150), -99)
        self.assertEqual(clamp_counter(1500), 999)
        self.assertEqual(clamp_counter(-5), -5)

    def test_game_counter_is_clamped(self):
        g = game_with([(29, 15)], w=30, h=16, difficulty="expert")
        for i in range(110):
            g.mark(i % 29, i // 29, True)
        self.assertEqual(g.board.counter(), -109)
        self.assertEqual(g.counter(), -99)


class Resume(unittest.TestCase):
    def playing(self):
        g = game_with(BEGINNER_WALL)
        g.release(0, 0)
        g.tick()
        self.assertEqual(g.status, PLAYING)
        return g

    def test_round_trip_restores_paused(self):
        g = self.playing()
        r = Game.from_dict(g.to_dict())
        self.assertEqual(r.board.to_dict(), g.board.to_dict())
        self.assertEqual(r.seconds, 2)
        self.assertTrue(r.paused)
        self.assertFalse(r.ticking)
        self.assertFalse(r.tick())

    def test_first_board_input_resumes_the_clock(self):
        r = Game.from_dict(self.playing().to_dict())
        r.mark(5, 5, True)
        self.assertTrue(r.ticking)

    def test_rejects_wrong_version(self):
        d = self.playing().to_dict()
        d["version"] = 99
        with self.assertRaises(ValueError):
            Game.from_dict(d)

    def test_rejects_a_preset_with_the_wrong_dimensions(self):
        d = self.playing().to_dict()
        d["difficulty"] = "expert"
        with self.assertRaises(ValueError):
            Game.from_dict(d)

    def test_rejects_seconds_out_of_range(self):
        d = self.playing().to_dict()
        d["seconds"] = 5000
        with self.assertRaises(ValueError):
            Game.from_dict(d)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_game -v`
Expected: ERROR — `No module named 'swaysweeper.game'`.

- [ ] **Step 3: Implement `swaysweeper/game.py`**

```python
"""One game session around a Board: timer, counter, difficulty, resume. No GTK."""

import random

from .board import LOST, PLAYING, READY, WON, Board

DIFFICULTIES = {
    "beginner": (9, 9, 10),
    "intermediate": (16, 16, 40),
    "expert": (30, 16, 99),
}
TIMER_MAX = 999
VERSION = 1


def clamp_custom(width, height, mines):
    """winmine's Custom limits (windowing.c:220-223): clamp, never reject."""
    h = min(max(int(height), 9), 24)
    w = min(max(int(width), 9), 30)
    m = min(max(int(mines), 10), min((w - 1) * (h - 1), 999))
    return w, h, m


def clamp_counter(n):
    return max(-99, min(999, n))


class Game:
    def __init__(self, difficulty, board):
        self.difficulty = difficulty
        self.board = board
        self.seconds = 0
        self.timer_running = False
        self.paused = False

    @classmethod
    def new(cls, difficulty, custom=(9, 9, 10), rng=None):
        w, h, m = DIFFICULTIES.get(difficulty) or clamp_custom(*custom)
        return cls(difficulty, Board.random(w, h, m, rng or random.Random()))

    @property
    def status(self):
        if self.board.state in (WON, LOST):
            return self.board.state
        if self.timer_running or self.board.state == PLAYING:
            return PLAYING
        return READY

    @property
    def ticking(self):
        return self.timer_running and not self.paused and self.seconds < TIMER_MAX

    def release(self, x, y, chord=False):
        """A left/middle release (or a keyboard open) on board square (x, y).

        The timer starts here, on the first release on the board, even one that
        reveals nothing (a flag) — game.c HandleBlockClick.
        """
        b = self.board
        if b.over or not b.in_bounds(x, y):
            return False
        self.paused = False
        if b.revealed_count == 0 and self.seconds == 0:
            self.seconds = 1
            self.timer_running = True
        if chord:
            b.chord(x, y)
        else:
            b.reveal(x, y)
        if b.over:
            self.timer_running = False
        return True

    def mark(self, x, y, marks_enabled):
        if self.board.over:
            return False
        self.paused = False
        return self.board.toggle_mark(x, y, marks_enabled)

    def tick(self):
        if not self.ticking:
            return False
        self.seconds += 1
        return True

    def counter(self):
        return clamp_counter(self.board.counter())

    def to_dict(self):
        return {
            "version": VERSION,
            "difficulty": self.difficulty,
            "seconds": self.seconds,
            "timer_running": self.timer_running,
            "board": self.board.to_dict(),
        }

    @classmethod
    def from_dict(cls, d):
        try:
            if d["version"] != VERSION:
                raise ValueError(f"saved game version {d['version']!r}")
            board = Board.from_dict(d["board"])
            difficulty = d["difficulty"]
            dims = (board.width, board.height, board.mine_count)
            if difficulty in DIFFICULTIES:
                if DIFFICULTIES[difficulty] != dims:
                    raise ValueError(f"{difficulty} board is {dims}")
            elif difficulty == "custom":
                if clamp_custom(*dims) != dims:
                    raise ValueError(f"custom board {dims} is out of range")
            else:
                raise ValueError(f"unknown difficulty {difficulty!r}")
            seconds = d["seconds"]
            if not isinstance(seconds, int) or not 0 <= seconds <= TIMER_MAX:
                raise ValueError(f"seconds {seconds!r}")
            game = cls(difficulty, board)
            game.seconds = seconds
            game.timer_running = bool(d["timer_running"])
            game.paused = True                     # spec §5: resumes on first input
            return game
        except (KeyError, TypeError) as exc:
            raise ValueError(f"bad game: {exc!r}") from exc
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/bin/python3 -m unittest discover -s tests -t . -v`
Expected: all PASS.

- [ ] **Step 5: Mutation check — the timer cap and the one-click win**

Temporarily change `self.seconds < TIMER_MAX` in `ticking` to `True`. Expected: `test_ticks_and_caps_at_999` FAILS. Revert.
Temporarily delete `if b.over: self.timer_running = False` in `release`. Expected: `test_stops_on_a_one_click_win` and `test_stops_on_a_loss` FAIL. Revert; all PASS.

- [ ] **Step 6: Commit**

```bash
git add swaysweeper/game.py tests/test_game.py
git commit -m "feat(game): session — timer from first board release, 999 cap, clamped counter, resume paused

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014cXNm1YtXA8z8QgkySFjrB"
```

---

### Task 3: Window geometry

**Files:**
- Create: `swaysweeper/geometry.py`, `tests/test_geometry.py`

**Interfaces:**
- Consumes: nothing.
- Produces (`swaysweeper.geometry`):
  - constants `CELL = 16`, `DIGIT_W = 13`, `DIGIT_H = 23`, `FACE = 24`, `BOARD_X = 12`, `BOARD_Y = 55`, `DIGIT_Y = 16`, `FACE_Y = 16`, `CHROME_ALLOWANCE = 96`
  - `Rect(left, top, right, bottom, bevel, style)` NamedTuple — inclusive pixel box; `style` ∈ `"raised" | "sunken" | "flat"`
  - `Layout` NamedTuple: `width, height, frame, panel, counter, timer, smiley, board` (Rects), `counter_x, timer_x` (3-tuples), `face_x`
  - `game_size(w, h) -> (int, int)`, `layout(w, h) -> Layout`, `cell_at(lay, x, y) -> tuple|None`, `on_face(lay, x, y) -> bool`, `zoom_fits(w, h, zoom, mon_w, mon_h) -> bool`

- [ ] **Step 1: Write the failing tests**

`tests/test_geometry.py`:
```python
import unittest

from swaysweeper.geometry import (
    BOARD_X, BOARD_Y, CELL, Rect, cell_at, game_size, layout, on_face, zoom_fits,
)

PRESETS = [(9, 9), (16, 16), (30, 16)]


class Geometry(unittest.TestCase):
    def test_game_size(self):
        self.assertEqual(game_size(9, 9), (168, 211))
        self.assertEqual(game_size(16, 16), (280, 323))
        self.assertEqual(game_size(30, 16), (504, 323))

    def test_beginner_layout_matches_drawing_c(self):
        lay = layout(9, 9)
        self.assertEqual(lay.frame, Rect(0, 0, 167, 210, 3, "raised"))
        self.assertEqual(lay.panel, Rect(9, 9, 158, 45, 2, "sunken"))
        self.assertEqual(lay.counter, Rect(16, 15, 56, 39, 1, "sunken"))
        self.assertEqual(lay.timer, Rect(111, 15, 151, 39, 1, "sunken"))
        self.assertEqual(lay.smiley, Rect(71, 15, 96, 40, 1, "flat"))
        self.assertEqual(lay.board, Rect(9, 52, 158, 201, 3, "sunken"))
        self.assertEqual(lay.counter_x, (17, 30, 43))
        self.assertEqual(lay.timer_x, (112, 125, 138))
        self.assertEqual(lay.face_x, 72)

    def test_board_bevel_exactly_wraps_the_cells(self):
        for w, h in PRESETS:
            b = layout(w, h).board
            self.assertEqual(b.left + b.bevel, BOARD_X)
            self.assertEqual(b.top + b.bevel, BOARD_Y)
            self.assertEqual(b.right - b.bevel, BOARD_X + CELL * w - 1)
            self.assertEqual(b.bottom - b.bevel, BOARD_Y + CELL * h - 1)

    def test_timer_mirrors_counter(self):
        for w, h in PRESETS:
            lay = layout(w, h)
            self.assertEqual(lay.counter.left + lay.timer.right, lay.width - 1)
            self.assertEqual(lay.counter.right + lay.timer.left, lay.width - 1)

    def test_cell_at(self):
        lay = layout(9, 9)
        self.assertEqual(cell_at(lay, 12, 55), (0, 0))
        self.assertEqual(cell_at(lay, 27.9, 70.5), (0, 0))
        self.assertEqual(cell_at(lay, 28, 55), (1, 0))
        self.assertEqual(cell_at(lay, 155, 198), (8, 8))
        self.assertIsNone(cell_at(lay, 11, 55))
        self.assertIsNone(cell_at(lay, 156, 55))
        self.assertIsNone(cell_at(lay, 12, 199))

    def test_on_face(self):
        lay = layout(9, 9)
        self.assertTrue(on_face(lay, 72, 16))
        self.assertTrue(on_face(lay, 95, 39))
        self.assertFalse(on_face(lay, 96, 16))
        self.assertFalse(on_face(lay, 71, 16))

    def test_zoom_fits(self):
        self.assertTrue(zoom_fits(30, 16, 1, 1920, 1080))
        self.assertTrue(zoom_fits(30, 16, 2, 1920, 1080))
        self.assertTrue(zoom_fits(30, 24, 2, 1920, 998))     # 451*2 + 96 = 998
        self.assertFalse(zoom_fits(30, 24, 2, 1920, 997))
        self.assertFalse(zoom_fits(30, 16, 2, 1000, 1080))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_geometry -v`
Expected: ERROR — `No module named 'swaysweeper.geometry'`.

- [ ] **Step 3: Implement `swaysweeper/geometry.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/bin/python3 -m unittest discover -s tests -t . -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add swaysweeper/geometry.py tests/test_geometry.py
git commit -m "feat(geometry): winmine client-area rectangles, hit-testing, zoom fit

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014cXNm1YtXA8z8QgkySFjrB"
```

---

### Task 4: Colours — slots, parser, contrast check, file watcher

**Files:**
- Create: `swaysweeper/theme.py`, `tests/test_theme.py`, `tests/fixtures.py`

**Interfaces:**
- Consumes: nothing.
- Produces (`swaysweeper.theme`):
  - `SLOTS: tuple[str, ...]`, `WIN95: dict[str,str]`, `MONO: dict[str,str]` (slot → `"#rrggbb"`)
  - `normalise(value) -> str|None`, `rgb(hexstr) -> (float,float,float)`, `contrast(a, b) -> float`, `FLOORS: list[(slot_a, slot_b, ratio)]`
  - `parse(text) -> (good: dict, problems: list[str])` — raises `tomllib.TOMLDecodeError`
  - `load_first(path) -> (colours: dict, problems: list[str])` — Win95 per missing/invalid slot
  - `reload(path, current) -> dict|None` — `None` means keep everything; a missing/invalid slot keeps its current colour
  - `check(text) -> list[str]`, `check_file(path) -> list[str]`
  - `class Watcher(path, on_change: Callable[[], None])` — calls `on_change()` after a completed write to `path`
- Produces (`tests.fixtures`): `NORD: dict` (a full passing slot set), `toml(d) -> str`, `spin(until, timeout=5.0)`, `pixel(surface, x, y) -> "#rrggbb"`

- [ ] **Step 1: Write the shared test fixtures**

`tests/fixtures.py`:
```python
"""Shared test data. NORD is the dotfiles mapping (spec §4) under nord."""

import time

NORD = {
    "face": "#3b4252", "light": "#a0a8b6", "shadow": "#272b33", "grid": "#434c5e",
    "revealed": "#272b33", "backdrop": "#272b33", "text": "#d8dee9",
    "led_bg": "#272b33", "led_on": "#bf616a", "led_off": "#2e3440",
    "mine": "#d8dee9", "glint": "#2e3440", "flag": "#c87d86", "ink": "#d8dee9",
    "exploded": "#bf616a", "smiley": "#ebcb8b", "smiley_ink": "#272b33",
    "cursor": "#eceff4",
    "num1": "#81a1c1", "num2": "#a3be8c", "num3": "#c87d86", "num4": "#b48ead",
    "num5": "#ebcb8b", "num6": "#8fbcbb", "num7": "#d8dee9", "num8": "#a0a8b6",
}


def toml(d):
    return "".join(f'{k} = "{v}"\n' for k, v in d.items())


def spin(until, timeout=5.0):
    """Iterate the default GLib main context until `until()` or timeout."""
    from gi.repository import GLib
    ctx = GLib.MainContext.default()
    end = time.monotonic() + timeout
    while not until() and time.monotonic() < end:
        while ctx.iteration(False):
            pass
        time.sleep(0.01)
    return until()


def pixel(surface, x, y):
    surface.flush()
    data, stride = surface.get_data(), surface.get_stride()
    b, g, r, _a = data[y * stride + 4 * x: y * stride + 4 * x + 4]
    return f"#{r:02x}{g:02x}{b:02x}"
```

- [ ] **Step 2: Write the failing tests**

`tests/test_theme.py`:
```python
import tempfile
import tomllib
import unittest
from pathlib import Path

from swaysweeper import theme
from tests.fixtures import NORD, spin, toml


class Values(unittest.TestCase):
    def test_sets_cover_exactly_the_slots(self):
        self.assertEqual(set(theme.WIN95), set(theme.SLOTS))
        self.assertEqual(set(theme.MONO), set(theme.SLOTS))
        self.assertEqual(set(NORD), set(theme.SLOTS))

    def test_normalise(self):
        self.assertEqual(theme.normalise("#ABC"), "#aabbcc")
        self.assertEqual(theme.normalise("#a1B2c3"), "#a1b2c3")
        for bad in ("red", "#abcd", "a1b2c3", 12, None):
            self.assertIsNone(theme.normalise(bad))

    def test_contrast(self):
        self.assertAlmostEqual(theme.contrast("#000000", "#ffffff"), 21.0, places=1)
        self.assertEqual(theme.contrast("#123456", "#abcdef"),
                         theme.contrast("#abcdef", "#123456"))


class Parse(unittest.TestCase):
    def test_full_file(self):
        good, problems = theme.parse(toml(NORD))
        self.assertEqual(good, NORD)
        self.assertEqual(problems, [])

    def test_unknown_invalid_and_missing_are_reported(self):
        d = dict(NORD, nmu1="#ffffff", num2="green")
        del d["num3"]
        good, problems = theme.parse(toml(d))
        self.assertNotIn("nmu1", good)
        self.assertNotIn("num2", good)
        text = "\n".join(problems)
        for word in ("nmu1", "num2", "num3"):
            self.assertIn(word, text)

    def test_malformed_raises(self):
        with self.assertRaises(tomllib.TOMLDecodeError):
            theme.parse("face = \n")


class Loading(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "colors.gen.toml"

    def tearDown(self):
        self.dir.cleanup()

    def test_first_load_missing_file_is_win95_silently(self):
        colours, problems = theme.load_first(self.path)
        self.assertEqual(colours, theme.WIN95)
        self.assertEqual(problems, [])

    def test_first_load_partial_falls_back_per_slot(self):
        self.path.write_text(toml({"face": "#111111"}))
        colours, problems = theme.load_first(self.path)
        self.assertEqual(colours["face"], "#111111")
        self.assertEqual(colours["num1"], theme.WIN95["num1"])
        self.assertEqual(len(problems), len(theme.SLOTS) - 1)

    def test_first_load_malformed_is_win95_with_a_problem(self):
        self.path.write_text("face = \n")
        colours, problems = theme.load_first(self.path)
        self.assertEqual(colours, theme.WIN95)
        self.assertEqual(len(problems), 1)

    def test_reload_keeps_everything_on_missing_or_malformed(self):
        self.assertIsNone(theme.reload(self.path, NORD))
        self.path.write_text("face = \n")
        self.assertIsNone(theme.reload(self.path, NORD))

    def test_reload_of_an_empty_file_keeps_current(self):
        # `theme` truncates then writes; a read between the two sees this.
        self.path.write_text("")
        self.assertEqual(theme.reload(self.path, NORD), NORD)

    def test_reload_keeps_current_for_missing_and_invalid_slots(self):
        self.path.write_text(toml({"face": "#111111", "num1": "blue"}))
        new = theme.reload(self.path, NORD)
        self.assertEqual(new["face"], "#111111")
        self.assertEqual(new["num1"], NORD["num1"])
        self.assertEqual(new["num2"], NORD["num2"])


class Check(unittest.TestCase):
    def test_the_dotfiles_mapping_passes(self):
        self.assertEqual(theme.check(toml(NORD)), [])

    def test_each_floor_can_fail(self):
        cases = {
            "num3": dict(NORD, num3="#bf616a"),          # nord's own red: 3.47:1
            "light": dict(NORD, light=NORD["shadow"]),
            "flag": dict(NORD, flag=NORD["face"]),
            "smiley_ink": dict(NORD, smiley_ink=NORD["smiley"]),
            "led_on": dict(NORD, led_on=NORD["led_bg"]),
            "mine": dict(NORD, mine=NORD["revealed"]),
        }
        for slot, d in cases.items():
            problems = theme.check(toml(d))
            self.assertTrue(any(slot in p for p in problems), (slot, problems))

    def test_cursor_must_differ_from_every_number(self):
        problems = theme.check(toml(dict(NORD, cursor=NORD["num6"])))
        self.assertTrue(any("cursor" in p and "num6" in p for p in problems), problems)

    def test_missing_and_unknown_fail(self):
        d = dict(NORD, extra="#ffffff")
        del d["glint"]
        text = "\n".join(theme.check(toml(d)))
        self.assertIn("extra", text)
        self.assertIn("glint", text)

    def test_check_file_reports_unreadable(self):
        self.assertEqual(len(theme.check_file("/nonexistent/colors.gen.toml")), 1)


class Watching(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "colors.gen.toml"
        self.calls = 0
        self.watcher = theme.Watcher(self.path, self.changed)

    def tearDown(self):
        self.watcher.cancel()
        self.dir.cleanup()

    def changed(self):
        self.calls += 1

    def test_a_completed_write_is_reported(self):
        spin(lambda: False, timeout=0.2)           # let the monitor settle
        self.path.write_text(toml(NORD))
        self.assertTrue(spin(lambda: self.calls > 0))

    def test_other_files_are_ignored(self):
        spin(lambda: False, timeout=0.2)
        (Path(self.dir.name) / "other.toml").write_text("x = 1\n")
        spin(lambda: False, timeout=1.0)
        self.assertEqual(self.calls, 0)

    def test_two_quick_writes_end_on_the_second(self):
        seen = []
        self.watcher.cancel()
        self.watcher = theme.Watcher(
            self.path, lambda: seen.append(theme.reload(self.path, theme.WIN95)))
        spin(lambda: False, timeout=0.2)
        self.path.write_text(toml(dict(NORD, face="#111111")))
        self.path.write_text(toml(dict(NORD, face="#222222")))
        spin(lambda: seen and seen[-1] and seen[-1]["face"] == "#222222")
        self.assertEqual(seen[-1]["face"], "#222222")
        self.assertNotIn(None, seen[-1:])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_theme -v`
Expected: ERROR — `cannot import name 'theme' from 'swaysweeper'`.

- [ ] **Step 4: Implement `swaysweeper/theme.py`**

```python
"""Colour slots, the built-in sets, the theme file, its check and its watcher.

Only `Watcher` touches gi, and it imports it lazily, so `--check-colors` and
the tests of everything else run without GTK.
"""

import re
import sys
import tomllib
from pathlib import Path

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

# Checked against the theme file only — Win95's own grey 8 would fail them.
FLOORS = [
    *((f"num{i}", "revealed", 4.5) for i in range(1, 9)),
    ("light", "shadow", 3.0),
    ("mine", "revealed", 3.0),
    ("flag", "face", 3.0),
    ("ink", "face", 3.0),
    ("smiley_ink", "smiley", 3.0),
    ("led_on", "led_bg", 3.0),
    ("cursor", "revealed", 3.0),
    ("cursor", "face", 3.0),
]

_HEX = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})")


def normalise(value):
    if not isinstance(value, str) or not _HEX.fullmatch(value):
        return None
    v = value.lower()
    if len(v) == 4:
        v = "#" + "".join(c * 2 for c in v[1:])
    return v


def rgb(hexstr):
    return tuple(int(hexstr[i:i + 2], 16) / 255 for i in (1, 3, 5))


def _luminance(hexstr):
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in rgb(hexstr)]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a, b):
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def parse(text):
    """(valid slots, problems). Raises tomllib.TOMLDecodeError on bad TOML."""
    data = tomllib.loads(text)
    good, problems = {}, []
    for key, value in data.items():
        if key not in SLOTS:
            problems.append(f"unknown slot {key!r}")
            continue
        v = normalise(value)
        if v is None:
            problems.append(f"{key}: {value!r} is not #rgb or #rrggbb")
        else:
            good[key] = v
    for slot in SLOTS:
        if slot not in data:
            problems.append(f"{slot}: missing")
    return good, problems


def load_first(path):
    """Colours for start-up: a missing or invalid slot falls back to Win95."""
    try:
        good, problems = parse(Path(path).read_text())
    except FileNotFoundError:
        return dict(WIN95), []
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        return dict(WIN95), [f"{path}: {exc}"]
    return {**WIN95, **good}, [f"{path}: {p}" for p in problems]


def reload(path, current):
    """Colours after a live change, or None to keep everything as it is.

    Never falls back to Win95: an empty or partial file (a write caught half
    way) keeps the current colour for every slot it does not carry.
    """
    try:
        good, _problems = parse(Path(path).read_text())
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return None
    return {**current, **good}


def check(text):
    try:
        good, problems = parse(text)
    except tomllib.TOMLDecodeError as exc:
        return [f"not TOML: {exc}"]
    for a, b, floor in FLOORS:
        if a in good and b in good:
            ratio = contrast(good[a], good[b])
            if ratio < floor:
                problems.append(f"{a} vs {b}: {ratio:.2f}:1, under the {floor}:1 floor")
    if "cursor" in good:
        for i in range(1, 9):
            if good.get(f"num{i}") == good["cursor"]:
                problems.append(f"cursor equals num{i} ({good['cursor']})")
    return problems


def check_file(path):
    try:
        return check(Path(path).read_text())
    except (OSError, UnicodeDecodeError) as exc:
        return [f"{path}: {exc}"]


class Watcher:
    """Call `on_change()` after a completed write to `path`.

    Watches the directory, so a file that does not exist yet (or a directory
    that appears later — GLib polls for it) is picked up. Reacts only to a
    finished write (CHANGES_DONE_HINT) or an atomic move into place, never to
    CHANGED: `theme` truncates and then writes, and a read between the two
    would see an empty file.
    """

    def __init__(self, path, on_change):
        from gi.repository import Gio
        self._path = Path(path)
        self._on_change = on_change
        self._events = {
            Gio.FileMonitorEvent.CHANGES_DONE_HINT,
            Gio.FileMonitorEvent.MOVED_IN,
            Gio.FileMonitorEvent.RENAMED,
        }
        directory = Gio.File.new_for_path(str(self._path.parent))
        self._monitor = directory.monitor_directory(Gio.FileMonitorFlags.WATCH_MOVES, None)
        self._monitor.connect("changed", self._changed)

    def _changed(self, _monitor, file, other, event):
        if event not in self._events:
            return
        # RENAMED carries the old name in `file` and the new one in `other`.
        names = {f.get_basename() for f in (file, other) if f is not None}
        if self._path.name not in names:
            return
        try:
            self._on_change()
        except Exception as exc:              # a bad callback must not kill the monitor
            print(f"swaysweeper: theme reload failed: {exc!r}", file=sys.stderr)

    def cancel(self):
        self._monitor.cancel()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `/usr/bin/python3 -m unittest discover -s tests -t . -v`
Expected: all PASS. If `test_the_dotfiles_mapping_passes` fails, the problem text names the pair and ratio: fix the **fixture** only if a hex in it was mistyped against `~/repos/dotfiles/palettes.toml`; otherwise the floor logic is wrong.

- [ ] **Step 6: Mutation check — reload never falls back**

Temporarily change `return {**current, **good}` in `reload` to `return {**WIN95, **good}`. Expected: `test_reload_of_an_empty_file_keeps_current` and `test_reload_keeps_current_for_missing_and_invalid_slots` FAIL. Revert.
Temporarily add `Gio.FileMonitorEvent.CHANGED` to `self._events`, then run `test_two_quick_writes_end_on_the_second` five times (`for i in 1 2 3 4 5; do /usr/bin/python3 -m unittest tests.test_theme.Watching -v; done`) — note whether a `None`/Win95 result ever appears in `seen`; it is a race, so record what you saw rather than requiring a failure. Revert.

- [ ] **Step 7: Commit**

```bash
git add swaysweeper/theme.py tests/test_theme.py tests/fixtures.py
git commit -m "feat(theme): slots, Win95/mono sets, keep-current reload, contrast check, watcher

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014cXNm1YtXA8z8QgkySFjrB"
```

---

### Task 5: State store — atomic JSON, quarantine, settings and best times

**Files:**
- Create: `swaysweeper/store.py`, `tests/test_store.py`

**Interfaces:**
- Consumes: `swaysweeper.game.DIFFICULTIES`, `clamp_custom` (Task 2).
- Produces (`swaysweeper.store`):
  - `state_dir(env=os.environ) -> Path`
  - `class Store(root: Path)`: `load(name, validate) -> object|None`, `save(name, data)` (raises `OSError`), `delete(name)`
  - `default_settings() -> dict` (`difficulty`, `custom: [w,h,m]`, `marks`, `color`, `sound`, `zoom`), `settings_from(data) -> dict` (raises `ValueError`)
  - `default_best() -> dict` (`level -> [seconds, name]`), `best_from(data) -> dict` (raises `ValueError`)

- [ ] **Step 1: Write the failing tests**

`tests/test_store.py`:
```python
import json
import tempfile
import unittest
from pathlib import Path

from swaysweeper import store


class StateDir(unittest.TestCase):
    def test_xdg(self):
        self.assertEqual(store.state_dir({"XDG_STATE_HOME": "/x"}), Path("/x/swaysweeper"))

    def test_fallback(self):
        self.assertEqual(store.state_dir({}), Path.home() / ".local/state/swaysweeper")


class StoreFiles(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name) / "swaysweeper"
        self.s = store.Store(self.root)

    def tearDown(self):
        self.dir.cleanup()

    def test_round_trip(self):
        self.s.save("game", {"a": [1, 2]})
        self.assertEqual(self.s.load("game", lambda d: d), {"a": [1, 2]})

    def test_missing_is_none(self):
        self.assertIsNone(self.s.load("game", lambda d: d))

    def test_corrupt_json_is_quarantined(self):
        self.root.mkdir(parents=True)
        (self.root / "game.json").write_text("{nope")
        self.assertIsNone(self.s.load("game", lambda d: d))
        self.assertFalse((self.root / "game.json").exists())
        self.assertEqual((self.root / "game.json.bad").read_text(), "{nope")

    def test_invalid_content_is_quarantined(self):
        self.s.save("game", {"a": 1})

        def reject(_d):
            raise ValueError("no")

        self.assertIsNone(self.s.load("game", reject))
        self.assertTrue((self.root / "game.json.bad").exists())

    def test_save_leaves_no_temp_files(self):
        self.s.save("game", {"a": 1})
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["game.json"])

    def test_a_stray_temp_file_does_not_disturb_load_or_save(self):
        self.root.mkdir(parents=True)
        (self.root / ".game.abc123.tmp").write_text("{half")
        self.s.save("game", {"a": 1})
        self.assertEqual(self.s.load("game", lambda d: d), {"a": 1})

    def test_delete(self):
        self.s.save("game", {"a": 1})
        self.s.delete("game")
        self.s.delete("game")                      # twice is fine
        self.assertIsNone(self.s.load("game", lambda d: d))

    def test_unwritable_root_raises(self):
        Path(self.dir.name, "file").write_text("")
        with self.assertRaises(OSError):
            store.Store(Path(self.dir.name, "file")).save("game", {})


class Settings(unittest.TestCase):
    def test_defaults_fill_gaps(self):
        s = store.settings_from({"marks": False})
        self.assertFalse(s["marks"])
        self.assertEqual(s["difficulty"], "beginner")
        self.assertEqual(s["zoom"], 1)

    def test_custom_field_is_clamped_not_rejected(self):
        s = store.settings_from({"difficulty": "custom", "custom": [30, 24, 5000]})
        self.assertEqual(s["custom"], [30, 24, 667])

    def test_bad_values_raise(self):
        for bad in ({"difficulty": "nightmare"}, {"zoom": 3}, {"marks": "yes"},
                    {"custom": [1, 2]}, ["not", "a", "dict"]):
            with self.assertRaises(ValueError, msg=bad):
                store.settings_from(bad)

    def test_round_trips_through_json(self):
        s = store.default_settings()
        self.assertEqual(store.settings_from(json.loads(json.dumps(s))), s)


class Best(unittest.TestCase):
    def test_default(self):
        self.assertEqual(store.default_best()["expert"], [999, "Anonymous"])

    def test_missing_level_is_filled(self):
        b = store.best_from({"beginner": [12, "xl"]})
        self.assertEqual(b["beginner"], [12, "xl"])
        self.assertEqual(b["expert"], [999, "Anonymous"])

    def test_bad_values_raise(self):
        for bad in ({"beginner": [0, "x"]}, {"beginner": [1000, "x"]},
                    {"beginner": [5, 7]}, {"beginner": "fast"}):
            with self.assertRaises(ValueError, msg=bad):
                store.best_from(bad)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_store -v`
Expected: ERROR — `cannot import name 'store'`.

- [ ] **Step 3: Implement `swaysweeper/store.py`**

```python
"""Atomic JSON state under $XDG_STATE_HOME/swaysweeper. No GTK.

An unreadable or invalid file is moved aside to `<name>.json.bad` and the
caller gets None, so the game always starts.
"""

import json
import os
import tempfile
from pathlib import Path

from .game import DIFFICULTIES, clamp_custom

APP = "swaysweeper"


def state_dir(env=os.environ):
    base = env.get("XDG_STATE_HOME") or Path.home() / ".local" / "state"
    return Path(base) / APP


class Store:
    def __init__(self, root):
        self.root = Path(root)

    def _path(self, name):
        return self.root / f"{name}.json"

    def load(self, name, validate):
        path = self._path(name)
        try:
            text = path.read_text()
        except FileNotFoundError:
            return None
        except OSError:
            self._quarantine(path)
            return None
        try:
            return validate(json.loads(text))
        except (ValueError, TypeError, KeyError):
            self._quarantine(path)
            return None

    def save(self, name, data):
        self.root.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.root, prefix=f".{name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as fh:
                json.dump(data, fh)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self._path(name))
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def delete(self, name):
        self._path(name).unlink(missing_ok=True)

    @staticmethod
    def _quarantine(path):
        try:
            os.replace(path, path.with_name(path.name + ".bad"))
        except OSError:
            pass


def default_settings():
    return {"difficulty": "beginner", "custom": [9, 9, 10], "marks": True,
            "color": True, "sound": False, "zoom": 1}


def settings_from(data):
    if not isinstance(data, dict):
        raise ValueError("settings is not an object")
    out = default_settings()
    for key, value in data.items():
        if key not in out:
            continue
        if key == "difficulty":
            if value not in DIFFICULTIES and value != "custom":
                raise ValueError(f"difficulty {value!r}")
        elif key == "custom":
            if (not isinstance(value, list) or len(value) != 3
                    or not all(isinstance(v, int) and not isinstance(v, bool) for v in value)):
                raise ValueError(f"custom {value!r}")
            value = list(clamp_custom(*value))
        elif key == "zoom":
            if value not in (1, 2) or isinstance(value, bool):
                raise ValueError(f"zoom {value!r}")
        elif not isinstance(value, bool):
            raise ValueError(f"{key} {value!r}")
        out[key] = value
    return out


def default_best():
    return {level: [999, "Anonymous"] for level in DIFFICULTIES}


def best_from(data):
    if not isinstance(data, dict):
        raise ValueError("best times is not an object")
    out = default_best()
    for level in DIFFICULTIES:
        if level not in data:
            continue
        entry = data[level]
        if (not isinstance(entry, list) or len(entry) != 2
                or not isinstance(entry[0], int) or isinstance(entry[0], bool)
                or not 1 <= entry[0] <= 999 or not isinstance(entry[1], str)):
            raise ValueError(f"{level} {entry!r}")
        out[level] = [entry[0], entry[1][:32]]
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/bin/python3 -m unittest discover -s tests -t . -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add swaysweeper/store.py tests/test_store.py
git commit -m "feat(store): atomic state files, .bad quarantine, settings and best-time schemas

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014cXNm1YtXA8z8QgkySFjrB"
```

---

### Task 6: Sprites — pixel art as text

**Files:**
- Create: `swaysweeper/sprites.py`, `tests/test_sprites.py`

**Interfaces:**
- Consumes: `swaysweeper.theme.rgb` (Task 4).
- Produces (`swaysweeper.sprites`):
  - `LEGEND: dict[char, slot]`
  - `CELLS: dict[str, list[str]]` — 16×16 overlays: `open1`…`open8`, `mine`, `flag`, `question`, `cross`
  - `FACES: dict[str, list[str]]` — 24×24: `normal`, `wow`, `dead`, `cool`, `pressed`
  - `LED: dict[str, list[str]]` — 13×23: `"0"`…`"9"`, `"-"`
  - `paint(cr, sprite, x, y, colours)` — one Cairo rectangle per run of equal non-`.` characters

- [ ] **Step 1: Write the failing tests**

`tests/test_sprites.py`:
```python
import unittest

import cairo

from swaysweeper import sprites, theme
from tests.fixtures import pixel


class Shapes(unittest.TestCase):
    def assertShape(self, sprite, w, h, name):
        self.assertEqual(len(sprite), h, name)
        for row in sprite:
            self.assertEqual(len(row), w, (name, row))
            for ch in row:
                self.assertTrue(ch == "." or ch in sprites.LEGEND, (name, ch))

    def test_cells(self):
        expected = {f"open{n}" for n in range(1, 9)} | {"mine", "flag", "question", "cross"}
        self.assertEqual(set(sprites.CELLS), expected)
        for name, s in sprites.CELLS.items():
            self.assertShape(s, 16, 16, name)

    def test_faces(self):
        self.assertEqual(set(sprites.FACES), {"normal", "wow", "dead", "cool", "pressed"})
        for name, s in sprites.FACES.items():
            self.assertShape(s, 24, 24, name)

    def test_led(self):
        self.assertEqual(set(sprites.LED), set("0123456789-"))
        for name, s in sprites.LED.items():
            self.assertShape(s, 13, 23, name)

    def test_numbers_use_their_own_slot(self):
        for n in range(1, 9):
            chars = {c for row in sprites.CELLS[f"open{n}"] for c in row} - {"."}
            self.assertEqual(chars, {str(n)})

    def test_led_segments(self):
        lit = lambda d: sum(row.count("O") for row in sprites.LED[d])
        self.assertEqual(lit("8"), sum(len(s) for s in sprites._SEGMENTS.values()))
        self.assertEqual(lit("-"), len(sprites._SEGMENTS["g"]))
        self.assertEqual(lit("1"), len(sprites._SEGMENTS["b"]) + len(sprites._SEGMENTS["c"]))

    def test_faces_differ(self):
        faces = [tuple(s) for s in sprites.FACES.values()]
        self.assertEqual(len(set(faces)), len(faces))


class Paint(unittest.TestCase):
    def test_paints_runs_and_skips_transparency(self):
        surf = cairo.ImageSurface(cairo.FORMAT_RGB24, 3, 1)
        cr = cairo.Context(surf)
        cr.set_source_rgb(1, 1, 1)
        cr.paint()
        cr.set_antialias(cairo.ANTIALIAS_NONE)
        sprites.paint(cr, ["11."], 0, 0, theme.WIN95)
        self.assertEqual(pixel(surf, 0, 0), theme.WIN95["num1"])
        self.assertEqual(pixel(surf, 1, 0), theme.WIN95["num1"])
        self.assertEqual(pixel(surf, 2, 0), "#ffffff")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_sprites -v`
Expected: ERROR — `cannot import name 'sprites'`.

- [ ] **Step 3: Implement `swaysweeper/sprites.py`**

```python
"""Every glyph as text pixel art. Each character names a colour slot; '.' is
transparent. Nothing here is a bitmap, so recolouring is a dictionary lookup.
"""

from .theme import rgb

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/bin/python3 -m unittest discover -s tests -t . -v`
Expected: all PASS.

- [ ] **Step 5: Eyeball the art**

Run:
```bash
/usr/bin/python3 -c "
from swaysweeper import sprites
for name in ('open1','open3','open8','mine','flag','question'):
    print(name); print('\n'.join(sprites.CELLS[name])); print()
for name in ('normal','dead','cool'):
    print(name); print('\n'.join(sprites.FACES[name])); print()
print('\n'.join(sprites.LED['8']))
"
```
Expected: recognisable digits, a spiked mine with a glint, a pennant on a pole, a `?`, three faces, a full 8. Fix any glyph that reads wrong before committing (keep the sizes).

- [ ] **Step 6: Commit**

```bash
git add swaysweeper/sprites.py tests/test_sprites.py
git commit -m "feat(sprites): numbers, mine, flag, ?, faces and LED digits as text pixel art

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014cXNm1YtXA8z8QgkySFjrB"
```

---

### Task 7: Render — the whole game area in Cairo

**Files:**
- Create: `swaysweeper/render.py`, `tests/test_render.py`

**Interfaces:**
- Consumes: `geometry` (Task 3), `sprites` (Task 6), `theme.rgb` (Task 4), `game.Game` (Task 2).
- Produces (`swaysweeper.render`):
  - `counter_text(n) -> str` (`-05`, `010`)
  - `bevel(cr, rect, colours)`, `draw_cell(cr, name, colours)` (at 0,0, 16×16)
  - `class CellCache`: `prepare(colours)`, `get(name) -> cairo.ImageSurface`
  - `draw(cr, game, colours, *, pressed=frozenset(), face="normal", cursor=None, cache=None)` — paints at 1:1 logical; caller translates/scales

- [ ] **Step 1: Write the failing tests**

`tests/test_render.py`:
```python
import unittest

import cairo

from swaysweeper import geometry as G
from swaysweeper import render, sprites, theme
from swaysweeper.board import Board
from swaysweeper.game import Game
from tests.fixtures import NORD, pixel


def paint(game, colours, **kw):
    lay = G.layout(game.board.width, game.board.height)
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, lay.width, lay.height)
    render.draw(cairo.Context(surf), game, colours, **kw)
    return surf


def cell_origin(x, y):
    return G.BOARD_X + G.CELL * x, G.BOARD_Y + G.CELL * y


def first_ink(sprite):
    for y, row in enumerate(sprite):
        for x, ch in enumerate(row):
            if ch != ".":
                return x, y


def lost_expert():
    # The column at x = 15 stops the first click's flood from winning outright.
    g = Game("expert", Board(30, 16, [(15, y) for y in range(16)] + [(0, 15)]))
    g.release(0, 0)
    g.release(0, 15)
    assert g.board.state == "lost"
    return g


class Text(unittest.TestCase):
    def test_counter_text(self):
        self.assertEqual(render.counter_text(10), "010")
        self.assertEqual(render.counter_text(0), "000")
        self.assertEqual(render.counter_text(-5), "-05")
        self.assertEqual(render.counter_text(-99), "-99")


class Chrome(unittest.TestCase):
    def test_frame_is_raised_and_board_sunken(self):
        surf = paint(Game.new("beginner"), theme.WIN95)
        self.assertEqual(pixel(surf, 0, 0), theme.WIN95["light"])
        self.assertEqual(pixel(surf, 167, 210), theme.WIN95["shadow"])
        self.assertEqual(pixel(surf, 9, 52), theme.WIN95["shadow"])
        self.assertEqual(pixel(surf, 158, 201), theme.WIN95["light"])

    def test_covered_cell_is_raised(self):
        surf = paint(Game.new("beginner"), theme.WIN95)
        x, y = cell_origin(0, 0)
        self.assertEqual(pixel(surf, x, y), theme.WIN95["light"])
        self.assertEqual(pixel(surf, x + 8, y + 8), theme.WIN95["face"])
        self.assertEqual(pixel(surf, x + 15, y + 15), theme.WIN95["shadow"])

    def test_led_digits_drawn(self):
        surf = paint(Game.new("beginner"), theme.WIN95)
        lay = G.layout(9, 9)
        # counter "010": the middle digit's top segment (a) is lit, at (x+2, DIGIT_Y+1)
        self.assertEqual(pixel(surf, lay.counter_x[1] + 5, G.DIGIT_Y + 1), theme.WIN95["led_off"])
        self.assertEqual(pixel(surf, lay.counter_x[1] + 11, G.DIGIT_Y + 5), theme.WIN95["led_on"])


class LostBoardSmoke(unittest.TestCase):
    def test_under_every_colour_set(self):
        g = lost_expert()
        for name, colours in (("win95", theme.WIN95), ("mono", theme.MONO), ("nord", NORD)):
            with self.subTest(name):
                surf = paint(g, colours)
                ex, ey = cell_origin(0, 15)
                self.assertEqual(pixel(surf, ex + 1, ey + 1), colours["exploded"])
                nx, ny = cell_origin(0, 14)              # a 1 next to the mine
                gx, gy = first_ink(sprites.CELLS["open1"])
                self.assertEqual(pixel(surf, nx + gx, ny + gy), colours["num1"])


class Interaction(unittest.TestCase):
    def test_pressed_covered_cell_draws_sunken_open(self):
        g = Game.new("beginner")
        surf = paint(g, theme.WIN95, pressed={(0, 0)})
        x, y = cell_origin(0, 0)
        self.assertEqual(pixel(surf, x, y), theme.WIN95["grid"])
        self.assertEqual(pixel(surf, x + 8, y + 8), theme.WIN95["revealed"])

    def test_cursor_outline(self):
        surf = paint(Game.new("beginner"), NORD, cursor=(4, 4))
        x, y = cell_origin(4, 4)
        self.assertEqual(pixel(surf, x, y), NORD["cursor"])
        self.assertEqual(pixel(surf, x + 15, y + 15), NORD["cursor"])

    def test_cache_follows_a_colour_change(self):
        cache = render.CellCache()
        cache.prepare(theme.WIN95)
        a = cache.get("covered")
        cache.prepare(NORD)
        b = cache.get("covered")
        self.assertIsNot(a, b)
        self.assertEqual(pixel(b, 8, 8), NORD["face"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_render -v`
Expected: ERROR — `cannot import name 'render'`.

- [ ] **Step 3: Implement `swaysweeper/render.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/bin/python3 -m unittest discover -s tests -t . -v`
Expected: all PASS. If `test_led_digits_drawn` fails on a pixel choice, check it against `sprites._SEGMENTS` (segment `a` spans x 2–10 at y 1; `b` is x 9–11 at y 2–10) and correct the **test coordinates** — the art is the authority.

- [ ] **Step 5: Render a preview PNG and look at it**

Run:
```bash
/usr/bin/python3 -c "
import cairo
from swaysweeper import render, geometry as G, theme
from tests.test_render import lost_expert
from tests.fixtures import NORD
g = lost_expert()
for name, c in (('win95', theme.WIN95), ('nord', NORD)):
    lay = G.layout(30, 16); s = cairo.ImageSurface(cairo.FORMAT_RGB24, lay.width*3, lay.height*3)
    cr = cairo.Context(s); cr.scale(3, 3); render.draw(cr, g, c, face='dead'); s.write_to_png(f'/tmp/claude-1000/sweep-{name}.png')
"
```
Open both PNGs with the Read tool. Expected: a recognisable winmine Expert board after a loss — raised outer frame, sunken panel and board, red LED digits, dead face, mines shown, the exploded square red. Fix anything that reads wrong.

- [ ] **Step 6: Commit**

```bash
git add swaysweeper/render.py tests/test_render.py
git commit -m "feat(render): bevels, LED digits, faces and cached cells in Cairo

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014cXNm1YtXA8z8QgkySFjrB"
```

---

### Task 8: Mouse gestures — winmine's input model without GTK

**Files:**
- Create: `swaysweeper/gestures.py`, `tests/test_gestures.py`

**Interfaces:**
- Consumes: `board.LOST`, `board.WON` (Task 1).
- Produces (`swaysweeper.gestures`):
  - `LEFT = 1, MIDDLE = 2, RIGHT = 3` (GTK button numbers)
  - `class Gestures`: `press(button, cell, on_face, shift=False, active=True) -> list[tuple]`, `motion(cell, on_face)`, `release(button, cell, on_face) -> list[tuple]`, `preview(width, height) -> frozenset`, `face(status) -> str`, attribute `mode`
  - actions: `("reveal", x, y)`, `("chord", x, y)`, `("mark", x, y)`, `("new",)`

- [ ] **Step 1: Write the failing tests**

`tests/test_gestures.py`:
```python
import unittest

from swaysweeper.board import LOST, PLAYING, WON
from swaysweeper.gestures import LEFT, MIDDLE, RIGHT, Gestures


class Clicks(unittest.TestCase):
    def setUp(self):
        self.g = Gestures()

    def test_left_reveals_on_release(self):
        self.assertEqual(self.g.press(LEFT, (2, 3), False), [])
        self.assertEqual(self.g.release(LEFT, (2, 3), False), [("reveal", 2, 3)])

    def test_drag_reveals_where_released(self):
        self.g.press(LEFT, (2, 3), False)
        self.g.motion((4, 4), False)
        self.assertEqual(self.g.preview(9, 9), {(4, 4)})
        self.assertEqual(self.g.release(LEFT, (4, 4), False), [("reveal", 4, 4)])

    def test_release_off_board_cancels(self):
        self.g.press(LEFT, (2, 3), False)
        self.assertEqual(self.g.release(LEFT, None, False), [])

    def test_right_marks_on_press(self):
        self.assertEqual(self.g.press(RIGHT, (1, 1), False), [("mark", 1, 1)])
        self.assertEqual(self.g.release(RIGHT, (1, 1), False), [])


class Chords(unittest.TestCase):
    def setUp(self):
        self.g = Gestures()

    def test_left_then_right_chords_on_the_first_release(self):
        self.g.press(LEFT, (4, 4), False)
        self.assertEqual(self.g.press(RIGHT, (4, 4), False), [])      # no flag
        self.assertEqual(self.g.release(RIGHT, (4, 4), False), [("chord", 4, 4)])
        self.assertEqual(self.g.release(LEFT, (4, 4), False), [])

    def test_right_then_left_flags_then_chords(self):
        self.assertEqual(self.g.press(RIGHT, (4, 4), False), [("mark", 4, 4)])
        self.assertEqual(self.g.press(LEFT, (4, 4), False), [])
        self.assertEqual(self.g.release(LEFT, (4, 4), False), [("chord", 4, 4)])
        self.assertEqual(self.g.release(RIGHT, (4, 4), False), [])

    def test_middle_chords(self):
        self.g.press(MIDDLE, (4, 4), False)
        self.assertEqual(self.g.release(MIDDLE, (4, 4), False), [("chord", 4, 4)])

    def test_shift_left_chords(self):
        self.g.press(LEFT, (4, 4), False, shift=True)
        self.assertEqual(self.g.release(LEFT, (4, 4), False), [("chord", 4, 4)])

    def test_chord_released_off_board_does_nothing(self):
        self.g.press(LEFT, (4, 4), False)
        self.g.press(RIGHT, (4, 4), False)
        self.g.motion(None, False)
        self.assertEqual(self.g.release(RIGHT, None, False), [])
        self.assertEqual(self.g.release(LEFT, None, False), [])

    def test_chord_preview_is_the_3x3_block_clipped(self):
        self.g.press(MIDDLE, (0, 0), False)
        self.assertEqual(self.g.preview(9, 9), {(0, 0), (1, 0), (0, 1), (1, 1)})
        self.g.motion((4, 4), False)
        self.assertEqual(len(self.g.preview(9, 9)), 9)


class Smiley(unittest.TestCase):
    def setUp(self):
        self.g = Gestures()

    def test_click_starts_a_new_game(self):
        self.g.press(LEFT, None, True)
        self.assertEqual(self.g.face(PLAYING), "pressed")
        self.assertEqual(self.g.release(LEFT, None, True), [("new",)])

    def test_drag_off_cancels(self):
        self.g.press(LEFT, None, True)
        self.g.motion(None, False)
        self.assertEqual(self.g.face(PLAYING), "normal")
        self.assertEqual(self.g.release(LEFT, None, False), [])

    def test_faces(self):
        self.assertEqual(self.g.face(PLAYING), "normal")
        self.assertEqual(self.g.face(LOST), "dead")
        self.assertEqual(self.g.face(WON), "cool")
        self.g.press(LEFT, None, False)                 # anywhere in the game area
        self.assertEqual(self.g.face(PLAYING), "wow")
        self.g.release(LEFT, None, False)
        self.g.press(RIGHT, (1, 1), False)               # right does not "o"
        self.assertEqual(self.g.face(PLAYING), "normal")


class GameOver(unittest.TestCase):
    def test_board_ignores_input_but_the_smiley_works(self):
        g = Gestures()
        self.assertEqual(g.press(LEFT, (1, 1), False, active=False), [])
        self.assertEqual(g.release(LEFT, (1, 1), False), [])
        self.assertEqual(g.press(RIGHT, (1, 1), False, active=False), [])
        g.release(RIGHT, (1, 1), False)
        g.press(LEFT, None, True, active=False)
        self.assertEqual(g.release(LEFT, None, True), [("new",)])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_gestures -v`
Expected: ERROR — `No module named 'swaysweeper.gestures'`.

- [ ] **Step 3: Implement `swaysweeper/gestures.py`**

```python
"""winmine's mouse model (windowing.c:495-548), with no GTK in it.

- Right PRESS marks, unless left is already held (then it turns the press
  into a chord). Left pressed while right is held also chords; so do middle
  and Shift+left.
- A reveal or chord fires on the FIRST button released, on the square under
  the pointer; released off the board, nothing happens.
- The smiley is its own button: pressed while held under the pointer.
"""

from .board import LOST, WON

LEFT, MIDDLE, RIGHT = 1, 2, 3


class Gestures:
    def __init__(self):
        self.held = set()
        self.mode = None            # None | "single" | "chord" | "face"
        self.cell = None
        self.on_face = False

    def press(self, button, cell, on_face, shift=False, active=True):
        self.held.add(button)
        self.cell, self.on_face = cell, on_face
        if self.mode == "face":
            return []
        if button == LEFT and on_face and self.mode is None and self.held == {LEFT}:
            self.mode = "face"
            return []
        if not active:
            return []
        if button == RIGHT:
            if self.mode == "single":
                self.mode = "chord"
                return []
            if self.mode is None and LEFT not in self.held and cell is not None:
                return [("mark", *cell)]
            return []
        if button == MIDDLE or (button == LEFT and (shift or RIGHT in self.held)):
            self.mode = "chord"
        elif button == LEFT:
            self.mode = "single"
        return []

    def motion(self, cell, on_face):
        self.cell, self.on_face = cell, on_face

    def release(self, button, cell, on_face):
        self.held.discard(button)
        self.cell, self.on_face = cell, on_face
        mode = self.mode
        if mode == "face":
            if button != LEFT:
                return []
            self.mode = None
            return [("new",)] if on_face else []
        self.mode = None
        if mode in ("single", "chord") and cell is not None:
            return [("chord" if mode == "chord" else "reveal", *cell)]
        return []

    def preview(self, width, height):
        if self.cell is None or self.mode not in ("single", "chord"):
            return frozenset()
        x, y = self.cell
        if self.mode == "single":
            return frozenset({(x, y)})
        return frozenset((x + dx, y + dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                         if 0 <= x + dx < width and 0 <= y + dy < height)

    def face(self, status):
        if self.mode == "face" and self.on_face:
            return "pressed"
        if status == LOST:
            return "dead"
        if status == WON:
            return "cool"
        if self.mode in ("single", "chord"):
            return "wow"
        return "normal"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/bin/python3 -m unittest discover -s tests -t . -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add swaysweeper/gestures.py tests/test_gestures.py
git commit -m "feat(gestures): winmine mouse model — mark on right press, chord on first release

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014cXNm1YtXA8z8QgkySFjrB"
```

---

### Task 9: Sound

**Files:**
- Create: `swaysweeper/sound.py`, `tests/test_sound.py`

**Interfaces:**
- Consumes: nothing.
- Produces (`swaysweeper.sound`): `RATE = 22050`, `TONES: dict[str, list[(hz, seconds)]]` with keys `tick`, `win`, `lose`; `write_wav(path, notes)`; `class Sound(cache_dir, player=<pw-play or None>)` with `available -> bool`, `play(name)`.

- [ ] **Step 1: Write the failing tests**

`tests/test_sound.py`:
```python
import os
import stat
import tempfile
import time
import unittest
import wave
from pathlib import Path

from swaysweeper import sound


class Wav(unittest.TestCase):
    def test_length_and_format(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.wav"
            sound.write_wav(p, [(440, 0.1), (880, 0.05)])
            with wave.open(str(p)) as w:
                self.assertEqual(w.getnchannels(), 1)
                self.assertEqual(w.getsampwidth(), 2)
                self.assertEqual(w.getnframes(), int(sound.RATE * 0.1) + int(sound.RATE * 0.05))


class Play(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name)

    def tearDown(self):
        self.dir.cleanup()

    def test_plays_through_the_player_without_waiting(self):
        log = self.root / "log"
        player = self.root / "fake-play"
        player.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$@\" >> {log}\n")
        player.chmod(player.stat().st_mode | stat.S_IEXEC)
        s = sound.Sound(self.root / "cache", player=str(player))
        self.assertTrue(s.available)
        s.play("tick")
        end = time.monotonic() + 3
        while not log.exists() and time.monotonic() < end:
            time.sleep(0.02)
        self.assertTrue(log.read_text().strip().endswith("tick.wav"))
        self.assertTrue((self.root / "cache" / "tick.wav").exists())

    def test_no_player_is_silent(self):
        s = sound.Sound(self.root / "cache", player=None)
        self.assertFalse(s.available)
        s.play("win")
        self.assertFalse((self.root / "cache").exists())

    def test_a_failing_player_never_raises(self):
        s = sound.Sound(self.root / "cache", player=str(self.root / "missing"))
        s.play("lose")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_sound -v`
Expected: ERROR — `cannot import name 'sound'`.

- [ ] **Step 3: Implement `swaysweeper/sound.py`**

```python
"""Square-wave tick / win / lose, generated on first use, played by pw-play.

GTK has no media backend on this machine, so playback is a child process —
fire-and-forget, every stream on DEVNULL, never a pipe.
"""

import shutil
import struct
import subprocess
import wave
from pathlib import Path

RATE = 22050
TONES = {
    "tick": [(1200, 0.02)],
    "win": [(523, 0.08), (659, 0.08), (784, 0.16)],
    "lose": [(196, 0.12), (147, 0.25)],
}
_AMPLITUDE = int(0.2 * 32767)
_UNSET = object()


def write_wav(path, notes):
    frames = bytearray()
    for hz, seconds in notes:
        period = RATE / hz
        for i in range(int(RATE * seconds)):
            value = _AMPLITUDE if (i % period) < period / 2 else -_AMPLITUDE
            frames += struct.pack("<h", value)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(frames))


class Sound:
    def __init__(self, cache_dir, player=_UNSET):
        self.cache_dir = Path(cache_dir)
        self.player = shutil.which("pw-play") if player is _UNSET else player

    @property
    def available(self):
        return self.player is not None

    def play(self, name):
        notes = TONES[name]
        if self.player is None:
            return
        path = self.cache_dir / f"{name}.wav"
        try:
            if not path.exists():
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                write_wav(path, notes)
            subprocess.Popen([self.player, str(path)], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
        except OSError:
            pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/bin/python3 -m unittest discover -s tests -t . -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add swaysweeper/sound.py tests/test_sound.py
git commit -m "feat(sound): generated square-wave tick/win/lose via pw-play, fire-and-forget

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014cXNm1YtXA8z8QgkySFjrB"
```

---

### Task 10: CLI entry and launcher — `--check-colors` without GTK

**Files:**
- Create: `swaysweeper/cli.py`, `bin/swaysweeper`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `theme.check_file` (Task 4). Lazily imports `swaysweeper.app.run` (Task 11).
- Produces: `swaysweeper.cli.main(argv=None) -> int`; executable `bin/swaysweeper`.

- [ ] **Step 1: Write the failing tests**

`tests/test_cli.py`:
```python
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.fixtures import NORD, toml

ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = ROOT / "bin" / "swaysweeper"


def run(*args):
    return subprocess.run([str(LAUNCHER), *args], capture_output=True, text=True, timeout=30)


class CheckColors(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "colors.gen.toml"

    def tearDown(self):
        self.dir.cleanup()

    def test_good_file_exits_zero(self):
        self.path.write_text(toml(NORD))
        r = run("--check-colors", str(self.path))
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_bad_file_exits_one_naming_the_slot(self):
        self.path.write_text(toml(dict(NORD, num3="#bf616a")))
        r = run("--check-colors", str(self.path))
        self.assertEqual(r.returncode, 1)
        self.assertIn("num3", r.stderr)

    def test_missing_argument_is_a_usage_error(self):
        self.assertEqual(run("--check-colors").returncode, 2)

    def test_check_never_imports_gi(self):
        self.path.write_text(toml(NORD))
        code = ("import sys; sys.modules['gi'] = None; "
                "from swaysweeper.cli import main; "
                f"sys.exit(main(['--check-colors', {str(self.path)!r}]))")
        r = subprocess.run(["/usr/bin/python3", "-c", code], cwd=ROOT,
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/bin/python3 -m unittest tests.test_cli -v`
Expected: FAIL/ERROR — launcher missing.

- [ ] **Step 3: Implement `swaysweeper/cli.py` and `bin/swaysweeper`**

`swaysweeper/cli.py`:
```python
"""Entry point. `--check-colors FILE` never imports GTK."""

import sys

from . import theme

USAGE = "usage: swaysweeper [--check-colors FILE]"


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--check-colors"]:
        if len(argv) != 2:
            print(USAGE, file=sys.stderr)
            return 2
        problems = theme.check_file(argv[1])
        for p in problems:
            print(f"{argv[1]}: {p}", file=sys.stderr)
        return 1 if problems else 0
    if argv:
        print(USAGE, file=sys.stderr)
        return 2
    from .app import run
    return run()
```

`bin/swaysweeper` (mode 755):
```python
#!/usr/bin/python3
# /usr/bin/python3 on purpose: it is the interpreter with PyGObject; the mise
# shim's python on PATH is not.
import sys
from pathlib import Path

_repo = Path(__file__).resolve().parent.parent
_lib = _repo if (_repo / "swaysweeper" / "__init__.py").is_file() \
    else Path.home() / ".local" / "share" / "swaysweeper"
sys.path.insert(0, str(_lib))

from swaysweeper.cli import main  # noqa: E402

sys.exit(main())
```

Run: `chmod 755 bin/swaysweeper`

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/bin/python3 -m unittest discover -s tests -t . -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add swaysweeper/cli.py bin/swaysweeper tests/test_cli.py
git commit -m "feat(cli): launcher and --check-colors, GTK-free

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014cXNm1YtXA8z8QgkySFjrB"
```

---

### Task 11: The playable window — view, timer, persistence, live theme

**Files:**
- Create: `swaysweeper/view.py`, `swaysweeper/app.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `swaysweeper.view.BoardView(app)` — `Gtk.DrawingArea`; `resize()`, `reset_cursor()`, `key(keyval, state) -> bool`
  - `swaysweeper.app.App` — `Gtk.Application`; attributes `game`, `settings`, `best`, `store`, `sound`, `window`, `view`; properties `colours`, `zoom`; methods `act(action)`, `new_game()`, `_apply_size()`, `_save(name, data)`, `_update_css()`, `_menu_model()`, `_install_actions()`
  - `swaysweeper.app.run() -> int`

This task has no unit tests (GTK); its logic lives in Tasks 1–10. It ends with a scripted launch on the live desktop and a manual play check. Until Task 12 adds the `keys` action, pressing `?` logs a GLib "action not found" warning — expected, not a bug.

- [ ] **Step 1: Implement `swaysweeper/view.py`**

```python
"""The board widget: paints through render.draw, turns raw input into actions."""

import cairo
import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Graphene", "1.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Graphene, Gtk  # noqa: E402

from . import geometry as G  # noqa: E402
from . import render  # noqa: E402
from .board import REVEALED  # noqa: E402
from .gestures import Gestures  # noqa: E402
from .theme import rgb  # noqa: E402

_DIRS = {"Left": (-1, 0), "h": (-1, 0), "Right": (1, 0), "l": (1, 0),
         "Up": (0, -1), "k": (0, -1), "Down": (0, 1), "j": (0, 1)}
_INPUT = (Gdk.EventType.BUTTON_PRESS, Gdk.EventType.BUTTON_RELEASE,
          Gdk.EventType.MOTION_NOTIFY)


class BoardView(Gtk.DrawingArea):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.gestures = Gestures()
        self.cursor = None
        self.cache = render.CellCache()
        self.set_focusable(True)
        self.set_draw_func(self._draw)
        # Legacy, not GestureClick: a click gesture ignores a second button
        # pressed while the first is held, and that IS the chord.
        legacy = Gtk.EventControllerLegacy()
        legacy.connect("event", self._event)
        self.add_controller(legacy)

    # --- geometry ------------------------------------------------------------

    def _layout(self):
        b = self.app.game.board
        return G.layout(b.width, b.height)

    def _origin(self):
        lay, z = self._layout(), self.app.zoom
        ox = max(0, (self.get_width() - lay.width * z) // 2)
        oy = max(0, (self.get_height() - lay.height * z) // 2)
        return ox, oy, z, lay

    def resize(self):
        lay, z = self._layout(), self.app.zoom
        self.set_content_width(lay.width * z)
        self.set_content_height(lay.height * z)
        self.queue_draw()

    def reset_cursor(self):
        self.cursor = None

    def _surface_to_widget(self, sx, sy):
        native = self.get_native()
        nx, ny = native.get_surface_transform()
        ok, p = native.compute_point(self, Graphene.Point().init(sx - nx, sy - ny))
        return (p.x, p.y) if ok else (-1.0, -1.0)

    def _hit(self, sx, sy):
        wx, wy = self._surface_to_widget(sx, sy)
        ox, oy, z, lay = self._origin()
        gx, gy = (wx - ox) / z, (wy - oy) / z
        return G.cell_at(lay, gx, gy), G.on_face(lay, gx, gy)

    # --- input ---------------------------------------------------------------

    def _event(self, _controller, event):
        kind = event.get_event_type()
        if kind not in _INPUT:
            return False
        ok, sx, sy = event.get_position()
        if not ok:
            return False
        cell, face = self._hit(sx, sy)
        if kind == Gdk.EventType.MOTION_NOTIFY:
            self.gestures.motion(cell, face)
            had_cursor = self.cursor is not None
            if cell is not None:
                self.cursor = None
            if self.gestures.mode or (had_cursor and self.cursor is None):
                self.queue_draw()
            return False
        button = event.get_button()
        if kind == Gdk.EventType.BUTTON_PRESS:
            self.grab_focus()
            shift = bool(event.get_modifier_state() & Gdk.ModifierType.SHIFT_MASK)
            actions = self.gestures.press(button, cell, face, shift=shift,
                                          active=not self.app.game.board.over)
        else:
            actions = self.gestures.release(button, cell, face)
        for action in actions:
            self.app.act(action)
        self.queue_draw()
        return True

    def key(self, keyval, state):
        if state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK):
            return False
        name = Gdk.keyval_name(keyval)
        b = self.app.game.board
        if name in _DIRS:
            if self.cursor is None:
                self.cursor = (b.width // 2, b.height // 2)
            else:
                dx, dy = _DIRS[name]
                x, y = self.cursor
                self.cursor = (min(max(x + dx, 0), b.width - 1),
                               min(max(y + dy, 0), b.height - 1))
            self.queue_draw()
            return True
        if name == "question":
            self.app.activate_action("keys", None)
            return True
        if self.cursor is None:
            return False
        x, y = self.cursor
        if name in ("space", "Return", "KP_Enter"):
            chord = b.marks[y][x] == REVEALED
            self.app.act(("chord" if chord else "reveal", x, y))
        elif name == "f":
            self.app.act(("mark", x, y))
        elif name == "c":
            self.app.act(("chord", x, y))
        else:
            return False
        self.queue_draw()
        return True

    # --- paint ---------------------------------------------------------------

    def _draw(self, _area, cr, _width, _height):
        ox, oy, z, _lay = self._origin()
        colours = self.app.colours
        cr.set_antialias(cairo.ANTIALIAS_NONE)
        cr.set_source_rgb(*rgb(colours["backdrop"]))
        cr.paint()
        cr.translate(ox, oy)
        cr.scale(z, z)
        game = self.app.game
        render.draw(cr, game, colours,
                    pressed=self.gestures.preview(game.board.width, game.board.height),
                    face=self.gestures.face(game.status),
                    cursor=self.cursor, cache=self.cache)
```

- [ ] **Step 2: Implement `swaysweeper/app.py`**

```python
"""The GTK application: window, menu, timer, persistence, live theme."""

import sys
from pathlib import Path

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

from . import geometry, store, theme  # noqa: E402
from .board import LOST, PLAYING, READY, WON  # noqa: E402
from .game import Game  # noqa: E402
from .sound import Sound  # noqa: E402
from .view import BoardView  # noqa: E402

APP_ID = "io.github.xinye1.swaysweeper"


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)
        self.store = store.Store(store.state_dir())
        self.settings = self.store.load("settings", store.settings_from) or store.default_settings()
        self.best = self.store.load("best", store.best_from) or store.default_best()
        self.theme_path = Path(GLib.get_user_config_dir()) / "swaysweeper" / "colors.gen.toml"
        self.theme_colours, problems = theme.load_first(self.theme_path)
        for p in problems:
            print(f"swaysweeper: {p}", file=sys.stderr)
        self.sound = Sound(Path(GLib.get_user_cache_dir()) / "swaysweeper")
        saved = self.store.load("game", Game.from_dict)
        if saved is not None and saved.status == PLAYING:
            self.game = saved
            self.settings["difficulty"] = saved.difficulty
            if saved.difficulty == "custom":
                b = saved.board
                self.settings["custom"] = [b.width, b.height, b.mine_count]
        else:
            self.store.delete("game")
            self.game = self._fresh()
        self.window = None
        self.view = None
        self._timer = 0
        self._watcher = None
        self._css = None

    # --- derived -------------------------------------------------------------

    @property
    def colours(self):
        return self.theme_colours if self.settings["color"] else theme.MONO

    @property
    def zoom(self):
        return self.settings["zoom"]

    def _fresh(self):
        return Game.new(self.settings["difficulty"], tuple(self.settings["custom"]))

    # --- lifecycle -----------------------------------------------------------

    def do_startup(self):
        Gtk.Application.do_startup(self)
        self._css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), self._css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self._update_css()
        self._install_actions()
        self._watcher = theme.Watcher(self.theme_path, self._theme_changed)

    def do_activate(self):
        if self.window is None:
            self._build_window()
        self.window.present()

    def _build_window(self):
        win = Gtk.ApplicationWindow(application=self, title="swaysweeper", resizable=False)
        bar = Gtk.PopoverMenuBar.new_from_model(self._menu_model())
        bar.add_css_class("swaysweeper-menubar")
        self.view = BoardView(self)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(bar)
        box.append(self.view)
        win.set_child(box)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", lambda _c, keyval, _code, state: self.view.key(keyval, state))
        win.add_controller(keys)
        win.connect("map", lambda *_: self._apply_size())
        self.window = win
        self._apply_size()
        self._sync_timer()

    # --- menu (Task 12 replaces both) ------------------------------------------

    def _menu_model(self):
        game = Gio.Menu()
        game.append("_New", "app.new")
        game.append("E_xit", "app.quit")
        bar = Gio.Menu()
        bar.append_submenu("_Game", game)
        return bar

    def _install_actions(self):
        for name, handler in (("new", lambda *_: self.new_game()),
                              ("quit", lambda *_: self.quit())):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", handler)
            self.add_action(action)
        self.set_accels_for_action("app.new", ["F2"])
        self.set_accels_for_action("app.quit", ["<Control>q"])

    def _apply_size(self):
        if self.view is not None:
            self.view.resize()

    # --- play ----------------------------------------------------------------

    def act(self, action):
        kind = action[0]
        if kind == "new":
            self.new_game()
            return
        before = self.game.status
        _, x, y = action
        if kind == "reveal":
            self.game.release(x, y)
        elif kind == "chord":
            self.game.release(x, y, chord=True)
        elif kind == "mark":
            self.game.mark(x, y, self.settings["marks"])
        after = self.game.status
        self._sync_timer()
        self._save_game()
        if self.view is not None:
            self.view.queue_draw()
        if before != after:
            self._status_changed(before, after)

    def _status_changed(self, before, after):
        if self.settings["sound"]:
            if before == READY and after == PLAYING:
                self.sound.play("tick")
            elif after == WON:
                self.sound.play("win")
            elif after == LOST:
                self.sound.play("lose")
        if after == WON:
            self._won()

    def _won(self):
        """Task 12 records best times here."""

    def new_game(self):
        self.game = self._fresh()
        self._sync_timer()
        self._save_game()
        if self.view is not None:
            self.view.reset_cursor()
            self.view.gestures.mode = None
        self._apply_size()

    # --- timer ---------------------------------------------------------------

    def _sync_timer(self):
        want = self.game.ticking
        if want and not self._timer:
            self._timer = GLib.timeout_add(1000, self._tick)
        elif not want and self._timer:
            GLib.source_remove(self._timer)
            self._timer = 0

    def _tick(self):
        if self.game.tick():
            if self.view is not None:
                self.view.queue_draw()
            self._save_game()
            if self.settings["sound"]:
                self.sound.play("tick")
        if not self.game.ticking:
            self._timer = 0
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    # --- persistence ---------------------------------------------------------

    def _save(self, name, data):
        try:
            self.store.save(name, data)
        except OSError as exc:
            print(f"swaysweeper: cannot save {name}: {exc}", file=sys.stderr)

    def _save_game(self):
        if self.game.status == PLAYING:
            self._save("game", self.game.to_dict())
        else:
            self.store.delete("game")

    # --- theme ---------------------------------------------------------------

    def _theme_changed(self):
        new = theme.reload(self.theme_path, self.theme_colours)
        if new is None or new == self.theme_colours:
            return
        self.theme_colours = new
        self._update_css()
        if self.view is not None:
            self.view.queue_draw()

    def _update_css(self):
        c = self.colours
        self._css.load_from_string(
            f".swaysweeper-menubar {{ background: {c['face']}; color: {c['text']}; }}\n"
            f".swaysweeper-menubar > item {{ color: {c['text']}; }}\n")


def run():
    return App().run([sys.argv[0]])
```

- [ ] **Step 3: Confirm the suite is still green and the modules import**

Run: `/usr/bin/python3 -m unittest discover -s tests -t . -v && /usr/bin/python3 -c "import swaysweeper.app"`
Expected: all PASS; the import prints nothing.

- [ ] **Step 4: Scripted launch on the live desktop (closes itself)**

Use a throwaway state dir so the real one is untouched:
```bash
export XDG_STATE_HOME=$(mktemp -d)
timeout 4 ./bin/swaysweeper; echo "exit=$?"
swaymsg -t get_tree | /usr/bin/python3 -c "import json,sys; print('still open' if 'io.github.xinye1.swaysweeper' in sys.stdin.read() else 'closed')"
```
Expected: `exit=124` (killed by timeout, i.e. it ran), no traceback on stderr, `closed`. Then launch it again in the background, and confirm sway floats it:
```bash
./bin/swaysweeper & pid=$!; sleep 1.5
swaymsg -t get_tree | /usr/bin/python3 -c "
import json,sys
def walk(n):
    if n.get('app_id') == 'io.github.xinye1.swaysweeper': print(n['type'], n['rect']['width'], n['rect']['height'])
    for c in n.get('nodes', []) + n.get('floating_nodes', []): walk(c)
walk(json.load(sys.stdin))"
kill $pid
```
Expected: `floating_con` with a size near 168×(211 + menu bar). If it prints `con` (tiled), stop and note it — Task 13's dotfiles PR then adds `for_window [app_id="io.github.xinye1.swaysweeper"] floating enable`.

- [ ] **Step 5: Manual play check (ask Xinye or do it yourself)**

Run `XDG_STATE_HOME=$(mktemp -d) ./bin/swaysweeper` and verify, against spec §1:
1. First click opens; the timer shows 001 and ticks.
2. Right press flags immediately; the counter drops; it can go negative.
3. Left+right on a satisfied number chords; Shift+left and middle do too; release off the board cancels.
4. Hold left: the face shows `o`; drag the sunken preview around.
5. Lose: the exploded square is red, wrong flags crossed. Win: every mine flagged, sunglasses.
6. Click the smiley: new game. F2: new game. Ctrl+Q: exits.
7. Keyboard: an arrow shows the cursor in the centre; `hjkl` move; Space opens; `f` flags; `c` chords; mouse motion hides it.
8. Close mid-game, relaunch with the same `XDG_STATE_HOME`: the board is back, the timer frozen until you click.
9. `kill -TERM` mid-game, relaunch: the board is back.

- [ ] **Step 6: Commit**

```bash
git add swaysweeper/view.py swaysweeper/app.py
git commit -m "feat(app): playable window — legacy input for chords, timer, resume, live theme

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014cXNm1YtXA8z8QgkySFjrB"
```

---

### Task 12: Full menu, dialogs, best times, settings, zoom, sound

**Files:**
- Create: `swaysweeper/dialogs.py`
- Modify: `swaysweeper/app.py` — replace `_menu_model`, `_install_actions`, `_apply_size`, `_won`

**Interfaces:**
- Consumes: Task 11's `App`; `game.DIFFICULTIES`, `clamp_custom`; `store.default_best`; `geometry.zoom_fits`.
- Produces (`swaysweeper.dialogs`): `custom_field(parent, current, on_ok)`, `fastest_time(parent, level, on_ok)`, `best_times(parent, best, on_reset)`, `keys_help(parent)`, `about(parent)`.

- [ ] **Step 1: Implement `swaysweeper/dialogs.py`**

```python
"""Small modal windows. GTK 4.10+ deprecates Gtk.Dialog, so these are windows."""

from gi.repository import Gtk

from . import __version__
from .game import DIFFICULTIES, clamp_custom

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


def _window(parent, title):
    win = Gtk.Window(title=title, transient_for=parent, modal=True, resizable=False)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                  margin_top=16, margin_bottom=16, margin_start=16, margin_end=16)
    win.set_child(box)
    return win, box


def _buttons(box, *specs):
    row = Gtk.Box(spacing=8, halign=Gtk.Align.END)
    for label, callback in specs:
        button = Gtk.Button(label=label)
        button.connect("clicked", lambda _b, cb=callback: cb())
        row.append(button)
    box.append(row)


def custom_field(parent, current, on_ok):
    """winmine's Custom Field: Height, Width, Mines; clamped, never rejected."""
    win, box = _window(parent, "Custom Field")
    grid = Gtk.Grid(row_spacing=8, column_spacing=12)
    box.append(grid)
    width, height, mines = current
    spins = []
    for row, (label, value) in enumerate((("Height:", height), ("Width:", width),
                                          ("Mines:", mines))):
        grid.attach(Gtk.Label(label=label, xalign=0), 0, row, 1, 1)
        spin = Gtk.SpinButton.new_with_range(0, 9999, 1)
        spin.set_numeric(True)
        spin.set_value(value)
        grid.attach(spin, 1, row, 1, 1)
        spins.append(spin)

    def ok():
        for spin in spins:
            spin.update()
        h, w, m = (int(spin.get_value()) for spin in spins)
        win.close()
        on_ok(*clamp_custom(w, h, m))

    _buttons(box, ("Cancel", win.close), ("OK", ok))
    win.present()


def fastest_time(parent, level, on_ok):
    """Closing the window any way at all still records the name typed."""
    win, box = _window(parent, "Congratulations")
    box.append(Gtk.Label(label=f"You have the fastest time\nfor {level} level.\n"
                               "Please type your name:",
                         justify=Gtk.Justification.CENTER))
    entry = Gtk.Entry(text="Anonymous")
    box.append(entry)
    done = False

    def record():
        nonlocal done
        if not done:
            done = True
            on_ok(entry.get_text().strip()[:32] or "Anonymous")

    entry.connect("activate", lambda *_: win.close())
    win.connect("close-request", lambda *_: (record(), False)[1])
    _buttons(box, ("OK", win.close))
    win.present()
    entry.grab_focus()
    entry.select_region(0, -1)


def best_times(parent, best, on_reset):
    win, box = _window(parent, "Fastest Mine Sweepers")
    grid = Gtk.Grid(row_spacing=6, column_spacing=16)
    box.append(grid)
    labels = {}
    for row, level in enumerate(DIFFICULTIES):
        grid.attach(Gtk.Label(label=f"{level.title()}:", xalign=0), 0, row, 1, 1)
        secs, name = Gtk.Label(xalign=1), Gtk.Label(xalign=0)
        grid.attach(secs, 1, row, 1, 1)
        grid.attach(name, 2, row, 1, 1)
        labels[level] = (secs, name)

    def show(times):
        for level, (secs, name) in labels.items():
            secs.set_label(f"{times[level][0]} seconds")
            name.set_label(times[level][1])

    show(best)
    _buttons(box, ("Reset Scores", lambda: show(on_reset())), ("OK", win.close))
    win.present()


def keys_help(parent):
    win, box = _window(parent, "swaysweeper keys")
    label = Gtk.Label(label=KEYS, xalign=0)
    label.add_css_class("monospace")
    box.append(label)
    _buttons(box, ("OK", win.close))
    win.present()


def about(parent):
    Gtk.AboutDialog(
        transient_for=parent, modal=True, program_name="swaysweeper", version=__version__,
        comments="The classic Windows Minesweeper, in your palette's colours.\n"
                 "Inspired by omasweeper (github.com/jankeesvw/omasweeper).",
        license_type=Gtk.License.MIT_X11,
    ).present()
```

- [ ] **Step 2: Replace the four methods in `swaysweeper/app.py`**

Add to the imports: `from . import dialogs` and `from .game import DIFFICULTIES, Game` (replacing `from .game import Game`).

Replace `_menu_model`:
```python
    def _menu_model(self):
        def section(*items):
            s = Gio.Menu()
            for label, action in items:
                s.append(label, action)
            return s

        game = Gio.Menu()
        game.append_section(None, section(("_New", "app.new")))
        game.append_section(None, section(
            ("_Beginner", "app.difficulty::beginner"),
            ("_Intermediate", "app.difficulty::intermediate"),
            ("_Expert", "app.difficulty::expert"),
            ("_Custom…", "app.difficulty::custom")))
        game.append_section(None, section(
            ("_Marks (?)", "app.marks"), ("Co_lor", "app.color"),
            ("_Sound", "app.sound"), ("_Zoom ×2", "app.zoom")))
        game.append_section(None, section(("Best _Times…", "app.best")))
        game.append_section(None, section(("E_xit", "app.quit")))
        help_ = section(("_Keys…", "app.keys"), ("_About swaysweeper", "app.about"))
        bar = Gio.Menu()
        bar.append_submenu("_Game", game)
        bar.append_submenu("_Help", help_)
        return bar
```

Replace `_install_actions`:
```python
    def _install_actions(self):
        plain = {
            "new": lambda *_: self.new_game(),
            "quit": lambda *_: self.quit(),
            "best": lambda *_: self._show_best(),
            "keys": lambda *_: dialogs.keys_help(self.window),
            "about": lambda *_: dialogs.about(self.window),
        }
        for name, handler in plain.items():
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", handler)
            self.add_action(action)

        level = Gio.SimpleAction.new_stateful(
            "difficulty", GLib.VariantType.new("s"),
            GLib.Variant("s", self.settings["difficulty"]))
        level.connect("change-state", self._on_difficulty)
        self.add_action(level)

        for name in ("marks", "color", "sound", "zoom"):
            value = self.settings["zoom"] == 2 if name == "zoom" else self.settings[name]
            action = Gio.SimpleAction.new_stateful(name, None, GLib.Variant("b", value))
            action.connect("change-state", self._on_toggle)
            self.add_action(action)
        self.lookup_action("sound").set_enabled(self.sound.available)

        self.set_accels_for_action("app.new", ["F2"])
        self.set_accels_for_action("app.quit", ["<Control>q"])

    def _on_difficulty(self, action, value):
        level = value.get_string()
        if level == "custom":
            dialogs.custom_field(self.window, self.settings["custom"],
                                 lambda w, h, m: self._set_level("custom", [w, h, m]))
            return
        self._set_level(level)

    def _set_level(self, level, custom=None):
        self.settings["difficulty"] = level
        if custom is not None:
            self.settings["custom"] = custom
        self.lookup_action("difficulty").set_state(GLib.Variant("s", level))
        self._save("settings", self.settings)
        self.new_game()

    def _on_toggle(self, action, value):
        name, on = action.get_name(), value.get_boolean()
        action.set_state(value)
        if name == "zoom":
            self.settings["zoom"] = 2 if on else 1
            self._apply_size()
        else:
            self.settings[name] = on
        if name == "color":
            self._update_css()
            if self.view is not None:
                self.view.queue_draw()
        self._save("settings", self.settings)

    def _show_best(self):
        def reset():
            self.best = store.default_best()
            self._save("best", self.best)
            return self.best
        dialogs.best_times(self.window, self.best, reset)
```

Replace `_apply_size`:
```python
    def _apply_size(self):
        if self.view is None:
            return
        fits = self._fits(2)
        zoom = self.lookup_action("zoom")
        zoom.set_enabled(fits)
        if self.settings["zoom"] == 2 and not fits:
            self.settings["zoom"] = 1
            self._save("settings", self.settings)
        zoom.set_state(GLib.Variant("b", self.settings["zoom"] == 2))
        self.view.resize()

    def _fits(self, zoom):
        display = Gdk.Display.get_default()
        surface = self.window.get_surface() if self.window else None
        monitor = display.get_monitor_at_surface(surface) if surface else None
        if monitor is None:
            monitors = display.get_monitors()
            monitor = monitors.get_item(0) if monitors.get_n_items() else None
        if monitor is None:
            return False
        g = monitor.get_geometry()
        b = self.game.board
        return geometry.zoom_fits(b.width, b.height, zoom, g.width, g.height)
```

Replace `_won`:
```python
    def _won(self):
        level = self.game.difficulty
        if level not in DIFFICULTIES or self.game.seconds >= self.best[level][0]:
            return
        # Record at once as Anonymous, so closing the window mid-dialog can
        # never lose the time; the dialog only names it.
        self.best[level] = [self.game.seconds, "Anonymous"]
        self._save("best", self.best)

        def named(name):
            self.best[level][1] = name
            self._save("best", self.best)
            self._show_best()

        dialogs.fastest_time(self.window, level, named)
```

- [ ] **Step 3: Confirm the suite is still green and the modules import**

Run: `/usr/bin/python3 -m unittest discover -s tests -t . -v && /usr/bin/python3 -c "import swaysweeper.app, swaysweeper.dialogs"`
Expected: all PASS.

- [ ] **Step 4: Manual menu check**

Run `XDG_STATE_HOME=$(mktemp -d) ./bin/swaysweeper` and verify:
1. Game menu shows New (F2), the four difficulties as radio items, Marks/Color/Sound/Zoom ×2 as checkboxes, Best Times…, Exit; Help shows Keys… and About.
2. Each difficulty resizes the window (the window shrinks back from Expert).
3. Custom… with Height 50, Width 5, Mines 1 gives a 9×24 board with 10 mines.
4. Marks off: right-click cycles flag ↔ blank only. Color off: monochrome; on: palette back.
5. Zoom ×2 doubles; with Custom 30×24 it is greyed out if it does not fit.
6. Sound on: tick each second, win/lose sounds. Sound greyed out if `pw-play` is absent (check with `PATH=/usr/local/bin ./bin/swaysweeper` only if `pw-play` lives elsewhere; otherwise skip and note it).
7. Win Beginner: the name prompt appears; after OK, Best Times shows the time; Reset Scores restores 999 Anonymous. Close the name prompt with the window's close button: the time is still recorded.
8. `?` shows Keys; typing `?` in the name prompt types a `?`.

- [ ] **Step 5: Commit**

```bash
git add swaysweeper/dialogs.py swaysweeper/app.py
git commit -m "feat(app): winmine menu, custom field, best times, marks/color/sound/zoom

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014cXNm1YtXA8z8QgkySFjrB"
```

---

### Task 13: Install, README, licence

**Files:**
- Create: `Makefile`, `data/io.github.xinye1.swaysweeper.desktop.in`, `tests/test_install.py`, `README.md`, `LICENSE`

**Interfaces:**
- Consumes: `bin/swaysweeper` (Task 10), the package.
- Produces: `make test`, `make install`, `make uninstall`; installed `~/.local/bin/swaysweeper`, `~/.local/share/swaysweeper/swaysweeper/`, `~/.local/share/applications/io.github.xinye1.swaysweeper.desktop` with an absolute `Exec=`.

- [ ] **Step 1: Write the failing test**

`tests/test_install.py`:
```python
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.fixtures import NORD, toml

ROOT = Path(__file__).resolve().parent.parent
ID = "io.github.xinye1.swaysweeper"


class Install(unittest.TestCase):
    def test_install_into_a_fake_home(self):
        with tempfile.TemporaryDirectory() as home:
            env = dict(os.environ, HOME=home)
            subprocess.run(["make", "-C", str(ROOT), "install"], env=env, check=True,
                           capture_output=True, text=True)
            desktop = Path(home, ".local/share/applications", f"{ID}.desktop").read_text()
            exec_line = next(l for l in desktop.splitlines() if l.startswith("Exec="))
            self.assertEqual(exec_line, f"Exec={home}/.local/bin/swaysweeper")
            self.assertIn("Categories=Game;LogicGame;", desktop)
            self.assertIn("Keywords=minesweeper;mines;game;", desktop)

            # The installed launcher runs from outside the repo, from its own copy.
            colours = Path(home, "c.toml")
            colours.write_text(toml(NORD))
            r = subprocess.run([f"{home}/.local/bin/swaysweeper", "--check-colors", str(colours)],
                               env=env, cwd=home, capture_output=True, text=True, timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr)

            subprocess.run(["make", "-C", str(ROOT), "uninstall"], env=env, check=True,
                           capture_output=True)
            self.assertFalse(Path(home, ".local/bin/swaysweeper").exists())
            self.assertFalse(Path(home, ".local/share/swaysweeper").exists())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `/usr/bin/python3 -m unittest tests.test_install -v`
Expected: FAIL — `make: *** No rule to make target 'install'`.

- [ ] **Step 3: Write the Makefile and desktop entry**

`Makefile` (recipe lines are TABs):
```make
PY      ?= /usr/bin/python3
ID      := io.github.xinye1.swaysweeper
BINDIR  := $(HOME)/.local/bin
LIBDIR  := $(HOME)/.local/share/swaysweeper
APPDIR  := $(HOME)/.local/share/applications

.PHONY: test install uninstall

test:
	$(PY) -m unittest discover -s tests -t . -v

# Exec= is absolute on purpose: the sway session's PATH has no ~/.local/bin,
# so a bare `swaysweeper` never resolves from fuzzel or Super+Space.
install:
	rm -rf $(LIBDIR)
	install -d $(LIBDIR)/swaysweeper $(BINDIR) $(APPDIR)
	install -m 644 swaysweeper/*.py $(LIBDIR)/swaysweeper/
	install -m 755 bin/swaysweeper $(BINDIR)/swaysweeper
	sed 's|@BINDIR@|$(BINDIR)|' data/$(ID).desktop.in > $(APPDIR)/$(ID).desktop
	-update-desktop-database $(APPDIR) 2>/dev/null

uninstall:
	rm -rf $(LIBDIR)
	rm -f $(BINDIR)/swaysweeper $(APPDIR)/$(ID).desktop
```

`data/io.github.xinye1.swaysweeper.desktop.in`:
```ini
[Desktop Entry]
Type=Application
Name=swaysweeper
GenericName=Minesweeper
Comment=The classic Windows Minesweeper, in your palette's colours
Exec=@BINDIR@/swaysweeper
Terminal=false
Categories=Game;LogicGame;
Keywords=minesweeper;mines;game;
StartupNotify=false
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `make test`
Expected: all PASS, including `test_install`.

- [ ] **Step 5: Write `README.md` and `LICENSE`**

`LICENSE`: the standard MIT licence text, `Copyright (c) 2026 Xinye Li`. (MIT matches termtris; if Xinye prefers otherwise, change before publishing.)

`README.md`:
```markdown
# swaysweeper

The classic Windows Minesweeper — Windows 95–2000 `winmine`, rules and all —
drawn in the colours of the active dotfiles palette, and recoloured live when
the palette switches. Inspired by [omasweeper](https://github.com/jankeesvw/omasweeper).

- Beginner, Intermediate, Expert and Custom; Marks (?), Color, Best Times.
- winmine's rules: the first-click mine moves to the top-left-most free square
  (never the last row or column); right *press* flags; chord with both buttons,
  the middle button or Shift+left, on the first button released.
- One deliberate deviation: the 95/98 one-click-win timer bug is fixed, as 2000 did.
- Extras that stay out of the way: vim/arrow keyboard play (`?` lists the keys),
  Zoom ×2 when it fits, and a game in progress survives closing — or a crash.

## Install

    make install      # ~/.local/{bin,share}; a desktop entry with an absolute Exec=
    make test

Needs `gtk4`, `python-gobject`, `python-cairo`; `pipewire` (`pw-play`) for sound.

## Colours

The game reads `~/.config/swaysweeper/colors.gen.toml` — a flat table of
`slot = "#rrggbb"` — and watches it. In this setup the dotfiles repo's `theme`
renders it from `palettes.toml`. With no file it is Windows 95 grey.

    swaysweeper --check-colors FILE   # unknown/missing/invalid slots, contrast floors

The slots and floors are in `docs/specs/2026-10-09-swaysweeper-design.md` §3.

## State

`$XDG_STATE_HOME/swaysweeper/` — settings, best times and the game in progress.
A file that will not parse is moved aside to `*.bad`; the game always starts.
```

- [ ] **Step 6: Install for real and launch from the launcher**

Run: `make install` then press Super+Space, type `mines`, choose swaysweeper.
Expected: the game opens (proves `Exec=` resolves in the session's `PATH`).

- [ ] **Step 7: Commit**

```bash
git add Makefile data tests/test_install.py README.md LICENSE
git commit -m "feat(install): make install with absolute Exec=, README, MIT licence

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014cXNm1YtXA8z8QgkySFjrB"
```

---

### Task 14: Dotfiles — `critical_text`, the template, the check (separate PR)

**Repo:** `~/repos/dotfiles`. Read its `CLAUDE.md` first. Branch from `main`: `git switch -c feat/swaysweeper-colours`.

**Files:**
- Modify: `palettes.toml` (add `critical_text` to `[nord]` and `[gruvbox]`)
- Create: `swaysweeper/.config/swaysweeper/colors.gen.toml.tmpl`
- Modify: `tests/check_consumers.sh` (a swaysweeper section)
- Modify: `README.md` (package table row), `PLAYBOOK.md` (§3.1 role row, §5.2 fold row)

**Interfaces:**
- Consumes: `~/.local/bin/swaysweeper --check-colors` (Task 13 installed it); `theme`'s `load_palettes`, `bindings`, `render`.
- Produces: the rendered `~/.config/swaysweeper/colors.gen.toml` (via the folded stow link).

- [ ] **Step 1: Add the role to both palettes**

In `palettes.toml`, directly after `critical = "#bf616a"` in `[nord]`:
```toml
# `critical` when it has to be READ, not just seen: swaysweeper's 3 and its
# flag. Nord has no lighter red; this is `critical` mixed toward `fg_bright` in
# 5% steps, stopping at the first that clears 4.5:1 on `desktop` (20%: 4.55:1;
# 3.23:1 on `surface`, under the flag). `dim`'s rule: the shortest step the
# floor asks for, nothing more. §3.1.
critical_text = "#c87d86"
```
and after `critical = "#fb4934"` in `[gruvbox]`:
```toml
# gruvbox's red already clears 4.5:1 on `desktop` (4.77:1) unchanged. §3.1.
critical_text = "#fb4934"
```

- [ ] **Step 2: Write the template**

`swaysweeper/.config/swaysweeper/colors.gen.toml.tmpl`:
```toml
# Generated from palettes.toml by `theme` — do not edit; edit the .tmpl.
#
# swaysweeper's colour slots (~/repos/swaysweeper, spec §3). The game watches
# this file and repaints on every switch — which needs ~/.config/swaysweeper
# to stay FOLDED (PLAYBOOK §5.2): through an unfolded package the game gets no
# change events. It never writes here.
#
# `swaysweeper --check-colors` holds these to floors: numbers 4.5:1 on
# `revealed`, the bevel pair 3:1, and more. tests/check_consumers.sh runs it
# under both palettes.
#
# Departures from winmine's colours, all forced by a dark background:
# - opened squares are `desktop`, darker than `bg` — it is what lets
#   magenta (4) and gruvbox's red clear 4.5:1;
# - winmine's navy 4, maroon 5 and black 7 vanish on dark: 4 is magenta,
#   5 the yellow `warning`, 7 `fg`;
# - 3 and the flag are `critical_text`, the readable red (palettes.toml).

face = "{{surface}}"
light = "{{dim}}"
shadow = "{{desktop}}"
grid = "{{sel}}"
revealed = "{{desktop}}"
backdrop = "{{desktop}}"
text = "{{fg}}"

led_bg = "{{desktop}}"
led_on = "{{critical}}"
led_off = "{{bg}}"

mine = "{{fg}}"
glint = "{{bg}}"
flag = "{{critical_text}}"
ink = "{{fg}}"
exploded = "{{critical}}"
smiley = "{{warning}}"
smiley_ink = "{{desktop}}"
cursor = "{{fg_bright}}"

num1 = "{{ansi_bright_blue}}"
num2 = "{{ansi_bright_green}}"
num3 = "{{critical_text}}"
num4 = "{{ansi_bright_magenta}}"
num5 = "{{warning}}"
num6 = "{{ansi_bright_cyan}}"
num7 = "{{fg}}"
num8 = "{{dim}}"
```

- [ ] **Step 3: Add the consumer check**

In `tests/check_consumers.sh`, before the final tally `printf`, add:
```sh
# --- swaysweeper ---
# The game falls back per slot with only a stderr line, so a misspelt slot, or
# a palette edit that drops a number under 4.5:1, would ship looking almost
# right. Ask the game itself, under BOTH palettes (the live file is only the
# current one), rendered to a scratch dir through theme's own functions.
ss="$HOME/.local/bin/swaysweeper"
if [ -x "$ss" ]; then
    ss_tmp=$(mktemp -d)
    for p in nord gruvbox; do
        if python3 - "$repo" "$p" "$ss_tmp/$p.toml" <<'PY'
import importlib.machinery, importlib.util, sys
from pathlib import Path
root, name, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
loader = importlib.machinery.SourceFileLoader("theme", str(root / "bin/.local/bin/theme"))
spec = importlib.util.spec_from_loader("theme", loader)
theme = importlib.util.module_from_spec(spec)
loader.exec_module(theme)
tmpl = root / "swaysweeper/.config/swaysweeper/colors.gen.toml.tmpl"
data = theme.load_palettes(root)
out.write_text(theme.render(tmpl.read_text(), theme.bindings(data[name], name), tmpl.name))
PY
        then
            if out=$("$ss" --check-colors "$ss_tmp/$p.toml" 2>&1); then
                ok "swaysweeper accepts its colours under $p"
            else
                no "swaysweeper accepts its colours under $p" "$(printf '%s' "$out" | head -3)"
            fi
        else
            no "swaysweeper colours render under $p"
        fi
    done
    rm -rf "$ss_tmp"
    if [ -L "$HOME/.config/swaysweeper" ]; then
        ok "~/.config/swaysweeper is folded (live repaint needs it)"
    else
        no "~/.config/swaysweeper is folded (live repaint needs it)" "stow -D swaysweeper; rm -r ~/.config/swaysweeper; stow swaysweeper"
    fi
else
    sk "swaysweeper colours" "not installed — make install in ~/repos/swaysweeper"
fi
```

- [ ] **Step 4: Render, stow, verify**

```bash
cd ~/repos/dotfiles
theme "$(cat "${XDG_STATE_HOME:-$HOME/.local/state}/theme/palette")"   # re-apply the current palette; renders the new template
ls swaysweeper/.config/swaysweeper/colors.gen.toml
git status --short        # the rendered file must NOT appear (gitignored *.gen.*)
stow -n -v swaysweeper    # dry run: expect a single LINK of .config/swaysweeper
stow swaysweeper
[ -L ~/.config/swaysweeper ] && echo folded
sh tests/theme_test.sh
sh tests/check_consumers.sh
```
Expected: the rendered file exists; `git status` lists only the tracked edits; `folded`; `theme_test.sh` PASS; `check_consumers.sh` shows `ok swaysweeper accepts its colours under nord`, `… under gruvbox`, `ok ~/.config/swaysweeper is folded`.

- [ ] **Step 5: Prove the new check can fail**

Temporarily set `num3 = "{{critical}}"` in the template, run `sh tests/check_consumers.sh`. Expected: `FAIL swaysweeper accepts its colours under nord` naming `num3`. Revert, re-render (Step 4's `theme` line), re-run: ok.

- [ ] **Step 6: Live repaint check**

With swaysweeper open mid-game: `theme nord`, then `theme gruvbox` (then back to the starting palette). Expected: the window recolours each time without restarting, never flashing Win95 grey, the game and timer intact.

- [ ] **Step 7: Docs**

- `README.md` package table: add `| \`swaysweeper\` | \`~/.config/swaysweeper/colors.gen.toml\` — swaysweeper's colours (the game is \`~/repos/swaysweeper\`) |`.
- `PLAYBOOK.md` §3.1 role table, after the `critical` row: `| \`critical_text\` | \`critical\` when it must be *read* — swaysweeper's 3 and flag. Nord's red is lightened toward \`fg_bright\` only until it clears 4.5:1 on \`desktop\`, as \`dim\` was |`.
- `PLAYBOOK.md` §5.2 table: `| \`swaysweeper\` | **Yes — and it must be** | The game watches \`colors.gen.toml\` for live repaint, and through an unfolded package (the file a symlink into the repo) it receives no change events. The game never writes here — its state is in \`~/.local/state/swaysweeper\`. \`setup.sh\` must not pre-create the directory. |`

- [ ] **Step 8: Commit, push, PR**

```bash
git add palettes.toml swaysweeper tests/check_consumers.sh README.md PLAYBOOK.md
git commit -m "feat(swaysweeper): colour template, critical_text role, consumer check under both palettes

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_014cXNm1YtXA8z8QgkySFjrB"
git push -u origin feat/swaysweeper-colours
gh pr create --title "swaysweeper colours: template, critical_text, consumer check" --body "<summary of the above; end with the Claude Code attribution line>"
```
(The remote must be SSH — `git@github.com:xinye1/dotfiles.git`.) Wait for the CodeRabbit review and address it before merging.

---

### Task 15: Final verification

- [ ] **Step 1: Whole suite and mutation spot-checks**

Run: `make test` in `~/repos/swaysweeper`. Expected: all PASS. Confirm the mutation checks from Tasks 1, 2 and 4 were run and recorded (re-run any that were skipped).

- [ ] **Step 2: The spec's manual list (§10)**

With the installed build: play each difficulty with mouse and keyboard, including every chord gesture; `theme nord` then `theme gruvbox` with a game open (no Win95 flash); close mid-game and relaunch; `kill` mid-game and relaunch; launch from fuzzel / Super+Space.

- [ ] **Step 3: Whole-branch review**

Dispatch a reviewer over the full swaysweeper history against the spec, and fix what it finds that is real.

- [ ] **Step 4: Ask Xinye whether to publish**

The swaysweeper repo is local only. Ask whether to create `github.com/xinye1/swaysweeper` (public or private) and push — do not create it unasked.
