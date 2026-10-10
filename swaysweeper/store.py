"""Atomic JSON state under $XDG_STATE_HOME/swaysweeper. No GTK.

An unreadable or invalid file is moved aside to `<name>.json.bad` and the
caller gets None, so the game always starts.
"""

import json
import os
import tempfile
from pathlib import Path

from .game import DIFFICULTIES, clamp_custom

APP = "swaysweeper"


def state_dir(env=os.environ):
    base = env.get("XDG_STATE_HOME") or Path.home() / ".local" / "state"
    return Path(base) / APP


class Store:
    def __init__(self, root):
        self.root = Path(root)

    def _path(self, name):
        return self.root / f"{name}.json"

    def load(self, name, validate):
        path = self._path(name)
        try:
            text = path.read_text()
        except FileNotFoundError:
            return None
        except (OSError, UnicodeDecodeError):     # UnicodeDecodeError is a ValueError
            self._quarantine(path)
            return None
        try:
            return validate(json.loads(text))
        except (ValueError, TypeError, KeyError):
            self._quarantine(path)
            return None

    def save(self, name, data):
        self.root.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.root, prefix=f".{name}.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as fh:
                json.dump(data, fh)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, self._path(name))
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def delete(self, name):
        self._path(name).unlink(missing_ok=True)

    @staticmethod
    def _quarantine(path):
        try:
            os.replace(path, path.with_name(path.name + ".bad"))
        except OSError:
            pass


def default_settings():
    return {"difficulty": "beginner", "custom": [9, 9, 10], "marks": True,
            "color": True, "sound": False, "zoom": 1}


def settings_from(data):
    if not isinstance(data, dict):
        raise ValueError("settings is not an object")
    out = default_settings()
    for key, value in data.items():
        if key not in out:
            continue
        if key == "difficulty":
            if value not in DIFFICULTIES and value != "custom":
                raise ValueError(f"difficulty {value!r}")
        elif key == "custom":
            if (not isinstance(value, list) or len(value) != 3
                    or not all(isinstance(v, int) and not isinstance(v, bool) for v in value)):
                raise ValueError(f"custom {value!r}")
            value = list(clamp_custom(*value))
        elif key == "zoom":
            if value not in (1, 2) or isinstance(value, bool):
                raise ValueError(f"zoom {value!r}")
        elif not isinstance(value, bool):
            raise ValueError(f"{key} {value!r}")
        out[key] = value
    return out


def default_best():
    return {level: [999, "Anonymous"] for level in DIFFICULTIES}


def best_from(data):
    if not isinstance(data, dict):
        raise ValueError("best times is not an object")
    out = default_best()
    for level in DIFFICULTIES:
        if level not in data:
            continue
        entry = data[level]
        if (not isinstance(entry, list) or len(entry) != 2
                or not isinstance(entry[0], int) or isinstance(entry[0], bool)
                or not 1 <= entry[0] <= 999 or not isinstance(entry[1], str)):
            raise ValueError(f"{level} {entry!r}")
        out[level] = [entry[0], entry[1][:32]]
    return out
