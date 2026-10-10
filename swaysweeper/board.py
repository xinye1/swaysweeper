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
