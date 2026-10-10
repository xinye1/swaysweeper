"""Square-wave tick / win / lose, generated on first use, played by pw-play.

GTK has no media backend on this machine, so playback is a child process —
fire-and-forget, every stream on DEVNULL, never a pipe.
"""

import os
import shutil
import struct
import subprocess
import tempfile
import wave
from pathlib import Path

RATE = 22050
TONES = {
    "tick": [(1200, 0.02)],
    "win": [(523, 0.08), (659, 0.08), (784, 0.16)],
    "lose": [(196, 0.12), (147, 0.25)],
}
_AMPLITUDE = int(0.2 * 32767)
_UNSET = object()


def write_wav(path, notes):
    frames = bytearray()
    for hz, seconds in notes:
        period = RATE / hz
        for i in range(int(RATE * seconds)):
            value = _AMPLITUDE if (i % period) < period / 2 else -_AMPLITUDE
            frames += struct.pack("<h", value)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(frames))


class Sound:
    def __init__(self, cache_dir, player=_UNSET):
        self.cache_dir = Path(cache_dir)
        self.player = shutil.which("pw-play") if player is _UNSET else player

    @property
    def available(self):
        return self.player is not None

    def play(self, name):
        notes = TONES[name]
        if self.player is None:
            return
        path = self.cache_dir / f"{name}.wav"
        try:
            if not path.exists():
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                fd, tmp = tempfile.mkstemp(dir=self.cache_dir, prefix=f".{name}.", suffix=".tmp")
                os.close(fd)
                try:
                    write_wav(tmp, notes)
                    os.replace(tmp, path)
                except BaseException:
                    Path(tmp).unlink(missing_ok=True)
                    raise
            subprocess.Popen([self.player, str(path)], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
        except OSError:
            pass
