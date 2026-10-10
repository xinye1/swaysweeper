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
