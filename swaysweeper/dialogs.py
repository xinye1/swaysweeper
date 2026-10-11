"""Small modal windows. GTK 4.10+ deprecates Gtk.Dialog, so these are windows."""

from gi.repository import Gtk

from . import __version__
from .game import DIFFICULTIES, clamp_custom
from .session import KEYS


def _window(parent, title):
    win = Gtk.Window(title=title, transient_for=parent, modal=True, resizable=False)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                  margin_top=16, margin_bottom=16, margin_start=16, margin_end=16)
    win.set_child(box)
    return win, box


def _buttons(box, *specs):
    row = Gtk.Box(spacing=8, halign=Gtk.Align.END)
    for label, callback in specs:
        button = Gtk.Button(label=label)
        button.connect("clicked", lambda _b, cb=callback: cb())
        row.append(button)
    box.append(row)


def custom_field(parent, current, on_ok):
    """winmine's Custom Field: Height, Width, Mines; clamped, never rejected."""
    win, box = _window(parent, "Custom Field")
    grid = Gtk.Grid(row_spacing=8, column_spacing=12)
    box.append(grid)
    width, height, mines = current
    spins = []
    for row, (label, value) in enumerate((("Height:", height), ("Width:", width),
                                          ("Mines:", mines))):
        grid.attach(Gtk.Label(label=label, xalign=0), 0, row, 1, 1)
        spin = Gtk.SpinButton.new_with_range(0, 9999, 1)
        spin.set_numeric(True)
        spin.set_value(value)
        grid.attach(spin, 1, row, 1, 1)
        spins.append(spin)

    def ok():
        for spin in spins:
            spin.update()
        h, w, m = (int(spin.get_value()) for spin in spins)
        win.close()
        on_ok(*clamp_custom(w, h, m))

    _buttons(box, ("Cancel", win.close), ("OK", ok))
    win.present()


def fastest_time(parent, level, on_ok):
    """Closing the window any way at all still records the name typed."""
    win, box = _window(parent, "Congratulations")
    box.append(Gtk.Label(label=f"You have the fastest time\nfor {level} level.\n"
                               "Please type your name:",
                         justify=Gtk.Justification.CENTER))
    entry = Gtk.Entry(text="Anonymous")
    box.append(entry)
    done = False

    def record():
        nonlocal done
        if not done:
            done = True
            on_ok(entry.get_text().strip()[:32] or "Anonymous")

    entry.connect("activate", lambda *_: win.close())
    win.connect("close-request", lambda *_: (record(), False)[1])
    _buttons(box, ("OK", win.close))
    win.present()
    entry.grab_focus()
    entry.select_region(0, -1)


def best_times(parent, best, on_reset):
    win, box = _window(parent, "Fastest Mine Sweepers")
    grid = Gtk.Grid(row_spacing=6, column_spacing=16)
    box.append(grid)
    labels = {}
    for row, level in enumerate(DIFFICULTIES):
        grid.attach(Gtk.Label(label=f"{level.title()}:", xalign=0), 0, row, 1, 1)
        secs, name = Gtk.Label(xalign=1), Gtk.Label(xalign=0)
        grid.attach(secs, 1, row, 1, 1)
        grid.attach(name, 2, row, 1, 1)
        labels[level] = (secs, name)

    def show(times):
        for level, (secs, name) in labels.items():
            secs.set_label(f"{times[level][0]} seconds")
            name.set_label(times[level][1])

    show(best)
    _buttons(box, ("Reset Scores", lambda: show(on_reset())), ("OK", win.close))
    win.present()


def keys_help(parent):
    win, box = _window(parent, "swaysweeper keys")
    label = Gtk.Label(label=KEYS, xalign=0)
    label.add_css_class("monospace")
    box.append(label)
    _buttons(box, ("OK", win.close))
    win.present()


def about(parent):
    Gtk.AboutDialog(
        transient_for=parent, modal=True, program_name="swaysweeper", version=__version__,
        comments="The classic Windows Minesweeper.\n"
                 "Inspired by omasweeper (github.com/jankeesvw/omasweeper).",
        license_type=Gtk.License.MIT_X11,
    ).present()
