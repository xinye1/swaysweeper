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
