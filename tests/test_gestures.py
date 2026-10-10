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



class StaleHeld(unittest.TestCase):
    def test_a_release_lost_to_a_dialog_does_not_poison_the_next_game(self):
        # A record win by chord opens the modal name prompt inside the left
        # release; the right release then goes to the dialog, never to us.
        g = Gestures()
        g.press(LEFT, (4, 4), False)
        g.press(RIGHT, (4, 4), False)
        g.release(LEFT, (4, 4), False)
        # Next game: GTK's button mask says nothing is held before this press.
        self.assertEqual(g.press(LEFT, None, True, held=frozenset()), [])
        self.assertEqual(g.face(PLAYING), "pressed")
        self.assertEqual(g.release(LEFT, None, True, held=frozenset({LEFT})), [("new",)])
        g.press(LEFT, (2, 2), False, held=frozenset())
        self.assertEqual(g.release(LEFT, (2, 2), False, held=frozenset({LEFT})),
                         [("reveal", 2, 2)])

if __name__ == "__main__":
    unittest.main()
