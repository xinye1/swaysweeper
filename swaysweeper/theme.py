"""Colour slots, the built-in sets, the theme file, its check and its watcher.

Only `Watcher` touches gi, and it imports it lazily, so `--check-colors` and
the tests of everything else run without GTK.
"""

import re
import sys
import tomllib
from pathlib import Path

SLOTS = (
    "face", "light", "shadow", "grid", "revealed", "backdrop", "text",
    "led_bg", "led_on", "led_off",
    "mine", "glint", "flag", "ink", "exploded", "smiley", "smiley_ink", "cursor",
    "num1", "num2", "num3", "num4", "num5", "num6", "num7", "num8",
)

WIN95 = {
    "face": "#c0c0c0", "light": "#ffffff", "shadow": "#808080", "grid": "#808080",
    "revealed": "#c0c0c0", "backdrop": "#008080", "text": "#000000",
    "led_bg": "#000000", "led_on": "#ff0000", "led_off": "#800000",
    "mine": "#000000", "glint": "#ffffff", "flag": "#ff0000", "ink": "#000000",
    "exploded": "#ff0000", "smiley": "#ffff00", "smiley_ink": "#000000",
    "cursor": "#ff00ff",
    "num1": "#0000ff", "num2": "#008000", "num3": "#ff0000", "num4": "#000080",
    "num5": "#800000", "num6": "#008080", "num7": "#000000", "num8": "#808080",
}

MONO = {
    "face": "#c0c0c0", "light": "#ffffff", "shadow": "#808080", "grid": "#808080",
    "revealed": "#c0c0c0", "backdrop": "#808080", "text": "#000000",
    "led_bg": "#000000", "led_on": "#ffffff", "led_off": "#404040",
    "mine": "#000000", "glint": "#ffffff", "flag": "#000000", "ink": "#000000",
    "exploded": "#808080", "smiley": "#ffffff", "smiley_ink": "#000000",
    "cursor": "#000000",
    **{f"num{i}": "#000000" for i in range(1, 9)},
}

# Checked against the theme file only — Win95's own grey 8 would fail them.
FLOORS = [
    *((f"num{i}", "revealed", 4.5) for i in range(1, 9)),
    ("light", "shadow", 3.0),
    ("mine", "revealed", 3.0),
    ("flag", "face", 3.0),
    ("ink", "face", 3.0),
    ("smiley_ink", "smiley", 3.0),
    ("led_on", "led_bg", 3.0),
    ("cursor", "revealed", 3.0),
    ("cursor", "face", 3.0),
]

_HEX = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})")


def normalise(value):
    if not isinstance(value, str) or not _HEX.fullmatch(value):
        return None
    v = value.lower()
    if len(v) == 4:
        v = "#" + "".join(c * 2 for c in v[1:])
    return v


def rgb(hexstr):
    return tuple(int(hexstr[i:i + 2], 16) / 255 for i in (1, 3, 5))


def _luminance(hexstr):
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in rgb(hexstr)]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(a, b):
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def parse(text):
    """(valid slots, problems). Raises tomllib.TOMLDecodeError on bad TOML."""
    data = tomllib.loads(text)
    good, problems = {}, []
    for key, value in data.items():
        if key not in SLOTS:
            problems.append(f"unknown slot {key!r}")
            continue
        v = normalise(value)
        if v is None:
            problems.append(f"{key}: {value!r} is not #rgb or #rrggbb")
        else:
            good[key] = v
    for slot in SLOTS:
        if slot not in data:
            problems.append(f"{slot}: missing")
    return good, problems


def load_first(path):
    """Colours for start-up: a missing or invalid slot falls back to Win95."""
    try:
        good, problems = parse(Path(path).read_text())
    except FileNotFoundError:
        return dict(WIN95), []
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        return dict(WIN95), [f"{path}: {exc}"]
    return {**WIN95, **good}, [f"{path}: {p}" for p in problems]


def reload(path, current):
    """Colours after a live change, or None to keep everything as it is.

    Never falls back to Win95: an empty or partial file (a write caught half
    way) keeps the current colour for every slot it does not carry.
    """
    try:
        good, _problems = parse(Path(path).read_text())
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return None
    return {**current, **good}


def check(text):
    try:
        good, problems = parse(text)
    except tomllib.TOMLDecodeError as exc:
        return [f"not TOML: {exc}"]
    for a, b, floor in FLOORS:
        if a in good and b in good:
            ratio = contrast(good[a], good[b])
            if ratio < floor:
                problems.append(f"{a} vs {b}: {ratio:.2f}:1, under the {floor}:1 floor")
    if "cursor" in good:
        for i in range(1, 9):
            if good.get(f"num{i}") == good["cursor"]:
                problems.append(f"cursor equals num{i} ({good['cursor']})")
    return problems


def check_file(path):
    try:
        return check(Path(path).read_text())
    except (OSError, UnicodeDecodeError) as exc:
        return [f"{path}: {exc}"]


class Watcher:
    """Call `on_change()` after a completed write to `path`.

    Watches the directory, so a file that does not exist yet (or a directory
    that appears later — GLib polls for it) is picked up. Reacts only to a
    finished write (CHANGES_DONE_HINT) or an atomic move into place, never to
    CHANGED: `theme` truncates and then writes, and a read between the two
    would see an empty file.
    """

    def __init__(self, path, on_change):
        from gi.repository import Gio
        self._path = Path(path)
        self._on_change = on_change
        self._events = {
            Gio.FileMonitorEvent.CHANGES_DONE_HINT,
            Gio.FileMonitorEvent.MOVED_IN,
            Gio.FileMonitorEvent.RENAMED,
        }
        directory = Gio.File.new_for_path(str(self._path.parent))
        self._monitor = directory.monitor_directory(Gio.FileMonitorFlags.WATCH_MOVES, None)
        self._monitor.connect("changed", self._changed)

    def _changed(self, _monitor, file, other, event):
        if event not in self._events:
            return
        # RENAMED carries the old name in `file` and the new one in `other`.
        names = {f.get_basename() for f in (file, other) if f is not None}
        if self._path.name not in names:
            return
        try:
            self._on_change()
        except Exception as exc:              # a bad callback must not kill the monitor
            print(f"swaysweeper: theme reload failed: {exc!r}", file=sys.stderr)

    def cancel(self):
        self._monitor.cancel()
