import unittest

from swaysweeper.geometry import (
    BOARD_X, BOARD_Y, CELL, ZOOMS, Rect, cell_at, fitting_zooms, game_size, layout, on_face,
    shown_zoom, zoom_fits, zoom_step,
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

    def test_zoom_levels(self):
        self.assertEqual(ZOOMS, (1, 1.25, 1.5, 1.75, 2, 2.5, 3))

    def test_fitting_zooms(self):
        self.assertEqual(fitting_zooms(30, 16, 1920, 1080), ZOOMS)        # 323*3 + 96 = 1065
        self.assertEqual(fitting_zooms(30, 24, 1920, 1080), (1, 1.25, 1.5, 1.75, 2))
        self.assertEqual(fitting_zooms(30, 24, 100, 100), (1,))          # 100 % always

    def test_shown_zoom_is_the_largest_that_fits_up_to_the_choice(self):
        self.assertEqual(shown_zoom(30, 24, 3, 1920, 1080), 2)
        self.assertEqual(shown_zoom(30, 24, 1.5, 1920, 1080), 1.5)
        self.assertEqual(shown_zoom(30, 24, 2, 1000, 800), 1.5)           # 451*1.75 + 96 > 800
        self.assertEqual(shown_zoom(30, 24, 2, 100, 100), 1)

    def test_zoom_step_moves_one_fitting_level_and_stops_at_the_ends(self):
        levels = (1, 1.25, 1.5)
        self.assertEqual(zoom_step(levels, 1.25, 1), 1.5)
        self.assertEqual(zoom_step(levels, 1.5, 1), 1.5)
        self.assertEqual(zoom_step(levels, 1.25, -1), 1)
        self.assertEqual(zoom_step(levels, 1, -1), 1)


if __name__ == "__main__":
    unittest.main()
