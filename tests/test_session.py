import unittest

from swaysweeper import geometry as G
from swaysweeper.board import FLAG, QUESTION, REVEALED, Board
from swaysweeper.game import Game
from swaysweeper.session import KEYS, Session


def centre(x, y):
    """Game-area pixel in the middle of board square (x, y)."""
    return G.BOARD_X + G.CELL * x + 8, G.BOARD_Y + G.CELL * y + 8


def walled():
    # A wall of mines down x = 4 (and one at 8,8): opening (0, 0) floods
    # x = 0..3 and stops; (3, 4) is a 3.
    return Game("beginner", Board(9, 9, [(4, y) for y in range(9)] + [(8, 8)]))


def one_click_win():
    return Game("beginner", Board(9, 9, [(8, 8)]))


def session(game=None, sound=False, marks=True):
    settings = {"marks": marks, "sound": sound, "color": True}
    best = {level: [999, "Anonymous"] for level in ("beginner", "intermediate", "expert")}
    return Session(game or walled(), settings, best)


def click(s, x, y, button=1):
    px, py = centre(x, y)
    return s.press(button, px, py, held=frozenset()) + s.release(button, px, py, held={button})


class Pointer(unittest.TestCase):
    def test_left_click_opens_and_saves(self):
        s = session()
        self.assertEqual(click(s, 0, 0), [("redraw",), ("save",), ("redraw",)])
        self.assertEqual(s.game.board.marks[0][0], REVEALED)

    def test_first_open_ticks_when_sound_is_on(self):
        s = session(sound=True)
        px, py = centre(0, 0)
        s.press(1, px, py, held=frozenset())
        self.assertEqual(s.release(1, px, py, held={1}),
                         [("save",), ("sound", "tick"), ("redraw",)])

    def test_right_press_marks_without_starting_the_game(self):
        s = session()
        self.assertEqual(s.press(3, *centre(2, 2), held=frozenset()), [("delete",), ("redraw",)])
        self.assertEqual(s.game.board.marks[2][2], FLAG)

    def test_marks_setting_is_read_live(self):
        s = session()
        s.press(3, *centre(2, 2), held=frozenset())
        s.release(3, *centre(2, 2), held={3})
        s.settings["marks"] = False
        s.press(3, *centre(2, 2), held=frozenset())
        self.assertNotEqual(s.game.board.marks[2][2], QUESTION)

    def test_release_off_the_board_does_nothing(self):
        s = session()
        s.press(1, *centre(0, 0), held=frozenset())
        s.motion(-20, -20)
        self.assertEqual(s.release(1, -20, -20, held={1}), [("redraw",)])
        self.assertEqual(s.game.status, "ready")
        self.assertIsNone(s.gestures.mode)

    def test_face_click_asks_for_a_new_game(self):
        s = session()
        fx, fy = G.layout(9, 9).face_x + 12, G.FACE_Y + 12
        s.press(1, fx, fy, held=frozenset())
        self.assertEqual(s.paint_state()[0], "pressed")
        self.assertEqual(s.release(1, fx, fy, held={1}), [("new_game",), ("redraw",)])

    def test_holding_left_shows_wow_and_the_pressed_square(self):
        s = session()
        s.press(1, *centre(3, 3), held=frozenset())
        self.assertEqual(s.paint_state(), ("wow", frozenset({(3, 3)}), None))


class Motion(unittest.TestCase):
    def test_motion_over_a_square_hides_the_cursor(self):
        s = session()
        s.key("Left")
        self.assertEqual(s.motion(*centre(1, 1)), [("redraw",)])
        self.assertIsNone(s.cursor)

    def test_idle_motion_needs_no_redraw(self):
        self.assertEqual(session().motion(*centre(1, 1)), [])

    def test_motion_off_the_board_keeps_the_cursor(self):
        s = session()
        s.key("Left")
        self.assertEqual(s.motion(1, 1), [])
        self.assertEqual(s.cursor, (4, 4))


class Keys(unittest.TestCase):
    def test_first_arrow_places_the_cursor_in_the_middle(self):
        s = session()
        self.assertEqual(s.key("Right"), [("redraw",)])
        self.assertEqual(s.cursor, (4, 4))

    def test_arrows_and_hjkl_move_and_stop_at_the_edge(self):
        s = session()
        s.key("Up")
        for name in ("h", "h", "h", "h", "h", "k"):
            s.key(name)
        self.assertEqual(s.cursor, (0, 3))
        for name in ("l", "j", "Down"):
            s.key(name)
        self.assertEqual(s.cursor, (1, 5))

    def test_question_shows_the_keys(self):
        self.assertEqual(session().key("question"), [("show_keys",)])

    def test_open_keys_need_a_cursor(self):
        self.assertEqual(session().key("space"), [("unhandled",)])

    def test_space_opens_a_square(self):
        s = session()
        s.key("Left")
        s.key("h")                                    # (3, 4)
        self.assertEqual(s.key("space"), [("save",), ("redraw",)])
        self.assertEqual(s.game.board.marks[4][3], REVEALED)

    def test_return_on_an_open_number_chords(self):
        s = session()
        s.key("Left")
        s.key("h")
        s.key("space")
        for y in (3, 4, 5):
            s.game.mark(4, y, True)
        s.key("Return")
        self.assertEqual(s.game.board.marks[4][0], REVEALED)

    def test_f_marks_and_c_on_a_flag_still_starts_the_timer(self):
        s = session()
        s.key("Left")
        s.key("h")
        s.key("f")
        self.assertEqual(s.game.board.marks[4][3], FLAG)
        self.assertEqual(s.key("c"), [("save",), ("redraw",)])
        self.assertEqual(s.game.status, "playing")

    def test_unknown_key_with_a_cursor_is_unhandled(self):
        s = session()
        s.key("Left")
        self.assertEqual(s.key("x"), [("unhandled",)])

    def test_keys_text_names_the_bindings(self):
        for binding in ("F2", "Ctrl+Q", "h j k l"):
            self.assertIn(binding, KEYS)


class Outcomes(unittest.TestCase):
    def test_a_win_records_a_best_time_as_anonymous(self):
        s = session(one_click_win(), sound=True)
        px, py = centre(0, 0)
        s.press(1, px, py, held=frozenset())
        self.assertEqual(s.release(1, px, py, held={1}),
                         [("delete",), ("sound", "win"), ("best", "beginner", 1), ("redraw",)])
        self.assertEqual(s.best["beginner"], [1, "Anonymous"])

    def test_a_slower_win_is_not_a_best_time(self):
        s = session(one_click_win())
        s.best["beginner"] = [1, "Ada"]
        self.assertNotIn(("best", "beginner", 1), click(s, 0, 0))
        self.assertEqual(s.best["beginner"], [1, "Ada"])

    def test_custom_wins_never_count(self):
        s = session(Game("custom", Board(9, 9, [(8, 8)])))
        self.assertEqual([e for e in click(s, 0, 0) if e[0] == "best"], [])

    def test_a_loss_plays_lose(self):
        s = session(sound=True)
        click(s, 0, 0)
        px, py = centre(4, 0)
        s.press(1, px, py, held=frozenset())
        self.assertEqual(s.release(1, px, py, held={1}),
                         [("delete",), ("sound", "lose"), ("redraw",)])


class Timer(unittest.TestCase):
    def test_tick_saves_and_redraws_while_running(self):
        s = session()
        click(s, 0, 0)
        self.assertEqual(s.tick(), [("save",), ("redraw",)])
        self.assertEqual(s.game.seconds, 2)

    def test_tick_plays_when_sound_is_on(self):
        s = session(sound=True)
        click(s, 0, 0)
        self.assertEqual(s.tick(), [("save",), ("sound", "tick"), ("redraw",)])

    def test_no_tick_before_the_first_click(self):
        self.assertEqual(session().tick(), [])

    def test_the_timer_stops_at_999(self):
        s = session()
        click(s, 0, 0)
        s.game.seconds = 999
        self.assertEqual(s.tick(), [])


class NewGame(unittest.TestCase):
    def test_new_resets_cursor_and_gesture(self):
        s = session()
        s.key("Left")
        s.press(1, *centre(0, 0), held=frozenset())
        fresh = walled()
        self.assertEqual(s.new(fresh), [("delete",), ("redraw",)])
        self.assertIs(s.game, fresh)
        self.assertIsNone(s.cursor)
        self.assertIsNone(s.gestures.mode)

    def test_a_session_can_start_without_a_game(self):
        s = Session(None, {"marks": True, "sound": False}, {})
        s.new(walled())
        self.assertEqual(s.game.difficulty, "beginner")


if __name__ == "__main__":
    unittest.main()
