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
