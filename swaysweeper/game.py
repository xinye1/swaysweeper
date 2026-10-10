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
