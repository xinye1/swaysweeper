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
