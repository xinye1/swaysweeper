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

    def test_non_utf8_file_is_quarantined_not_fatal(self):
        # An editor saving best.json as Latin-1 must not stop the game starting.
        self.root.mkdir(parents=True)
        (self.root / "best.json").write_bytes(b'{"beginner": [5, "Jos\xe9"]}')
        self.assertIsNone(self.s.load("best", lambda d: d))
        self.assertTrue((self.root / "best.json.bad").exists())

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
