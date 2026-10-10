"""Shared test data. NORD is the dotfiles mapping (spec §4) under nord."""

import time

NORD = {
    "face": "#3b4252", "light": "#a0a8b6", "shadow": "#272b33", "grid": "#434c5e",
    "revealed": "#272b33", "backdrop": "#272b33", "text": "#d8dee9",
    "led_bg": "#272b33", "led_on": "#bf616a", "led_off": "#2e3440",
    "mine": "#d8dee9", "glint": "#2e3440", "flag": "#c87d86", "ink": "#d8dee9",
    "exploded": "#bf616a", "smiley": "#ebcb8b", "smiley_ink": "#272b33",
    "cursor": "#eceff4",
    "num1": "#81a1c1", "num2": "#a3be8c", "num3": "#c87d86", "num4": "#b48ead",
    "num5": "#ebcb8b", "num6": "#8fbcbb", "num7": "#d8dee9", "num8": "#a0a8b6",
}


def toml(d):
    return "".join(f'{k} = "{v}"\n' for k, v in d.items())


def spin(until, timeout=5.0):
    """Iterate the default GLib main context until `until()` or timeout."""
    from gi.repository import GLib
    ctx = GLib.MainContext.default()
    end = time.monotonic() + timeout
    while not until() and time.monotonic() < end:
        while ctx.iteration(False):
            pass
        time.sleep(0.01)
    return until()


def pixel(surface, x, y):
    surface.flush()
    data, stride = surface.get_data(), surface.get_stride()
    b, g, r, _a = data[y * stride + 4 * x: y * stride + 4 * x + 4]
    return f"#{r:02x}{g:02x}{b:02x}"
