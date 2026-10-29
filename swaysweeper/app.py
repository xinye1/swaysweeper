"""The GTK application: window, menu, timer, persistence."""

import sys
from pathlib import Path

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

from . import colours, dialogs, geometry, store  # noqa: E402
from .board import PLAYING  # noqa: E402
from .game import Game  # noqa: E402
from .session import Session  # noqa: E402
from .sound import Sound  # noqa: E402
from .view import BoardView  # noqa: E402

APP_ID = "io.github.xinye1.swaysweeper"


def _zoom_name(z):
    """The app.zoom target for a level: "1", "1.25", ... "3"."""
    return f"{z:g}"


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)
        self.store = store.Store(store.state_dir())
        self.settings = self.store.load("settings", store.settings_from) or store.default_settings()
        best = self.store.load("best", store.best_from) or store.default_best()
        self.sound = Sound(Path(GLib.get_user_cache_dir()) / "swaysweeper")
        saved = self.store.load("game", Game.from_dict)
        if saved is not None and saved.status == PLAYING:
            game = saved
            self.settings["difficulty"] = saved.difficulty
            if saved.difficulty == "custom":
                b = saved.board
                self.settings["custom"] = [b.width, b.height, b.mine_count]
        else:
            self.store.delete("game")
            game = self._fresh()
        self.session = Session(game, self.settings, best)
        self.window = None
        self.view = None
        self._zoom, self._levels = 1, (1,)
        self._zoom_levels = Gio.Menu()
        self._timer = 0
        self._css = None

    # --- derived -------------------------------------------------------------

    @property
    def colours(self):
        return colours.WIN95 if self.settings["color"] else colours.MONO

    @property
    def zoom(self):
        """The zoom shown: the chosen one, or the largest below it that fits."""
        return self._zoom

    @property
    def game(self):
        return self.session.game

    @property
    def best(self):
        return self.session.best

    @best.setter
    def best(self, value):
        self.session.best = value

    def _fresh(self):
        return Game.new(self.settings["difficulty"], tuple(self.settings["custom"]))

    # --- lifecycle -----------------------------------------------------------

    def do_startup(self):
        Gtk.Application.do_startup(self)
        self._css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), self._css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self._update_css()
        self._install_actions()

    def do_activate(self):
        if self.window is None:
            self._build_window()
        self.window.present()

    def _build_window(self):
        win = Gtk.ApplicationWindow(application=self, title="swaysweeper", resizable=False)
        bar = Gtk.PopoverMenuBar.new_from_model(self._menu_model())
        bar.add_css_class("swaysweeper-menubar")
        self.view = BoardView(self)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.append(bar)
        box.append(self.view)
        win.set_child(box)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", lambda _c, keyval, _code, state: self.view.key(keyval, state))
        win.add_controller(keys)
        win.connect("map", lambda *_: self._apply_size())
        self.window = win
        self._apply_size()
        self._sync_timer()

    # --- menu and settings ---------------------------------------------------

    def _menu_model(self):
        def section(*items):
            s = Gio.Menu()
            for label, action in items:
                s.append(label, action)
            return s

        game = Gio.Menu()
        game.append_section(None, section(("_New", "app.new")))
        game.append_section(None, section(
            ("_Beginner", "app.difficulty::beginner"),
            ("_Intermediate", "app.difficulty::intermediate"),
            ("_Expert", "app.difficulty::expert"),
            ("_Custom…", "app.difficulty::custom")))
        options = section(("_Marks (?)", "app.marks"), ("Co_lor", "app.color"),
                          ("_Sound", "app.sound"))
        zoom = Gio.Menu()
        zoom.append_section(None, section(("Zoom _In", "app.zoom-in"),
                                          ("Zoom _Out", "app.zoom-out")))
        zoom.append_section(None, self._zoom_levels)
        options.append_submenu("_Zoom", zoom)
        game.append_section(None, options)
        game.append_section(None, section(("Best _Times…", "app.best")))
        game.append_section(None, section(("E_xit", "app.quit")))
        help_ = section(("_Keys…", "app.keys"), ("_About swaysweeper", "app.about"))
        bar = Gio.Menu()
        bar.append_submenu("_Game", game)
        bar.append_submenu("_Help", help_)
        return bar

    def _install_actions(self):
        plain = {
            "new": lambda *_: self.new_game(),
            "quit": lambda *_: self.quit(),
            "best": lambda *_: self._show_best(),
            "keys": lambda *_: dialogs.keys_help(self.window),
            "about": lambda *_: dialogs.about(self.window),
            "zoom-in": lambda *_: self._set_zoom(geometry.zoom_step(self._levels, self._zoom, 1)),
            "zoom-out": lambda *_: self._set_zoom(geometry.zoom_step(self._levels, self._zoom, -1)),
        }
        for name, handler in plain.items():
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", handler)
            self.add_action(action)

        level = Gio.SimpleAction.new_stateful(
            "difficulty", GLib.VariantType.new("s"),
            GLib.Variant("s", self.settings["difficulty"]))
        level.connect("change-state", self._on_difficulty)
        self.add_action(level)

        for name in ("marks", "color", "sound"):
            action = Gio.SimpleAction.new_stateful(name, None, GLib.Variant("b", self.settings[name]))
            action.connect("change-state", self._on_toggle)
            self.add_action(action)
        self.lookup_action("sound").set_enabled(self.sound.available)

        zoom = Gio.SimpleAction.new_stateful("zoom", GLib.VariantType.new("s"),
                                             GLib.Variant("s", _zoom_name(self._zoom)))
        zoom.connect("change-state", lambda _a, value: self._set_zoom(
            next(z for z in geometry.ZOOMS if _zoom_name(z) == value.get_string())))
        self.add_action(zoom)

        self.set_accels_for_action("app.new", ["F2"])
        self.set_accels_for_action("app.quit", ["<Control>q"])
        self.set_accels_for_action("app.zoom-in", ["<Control>equal", "<Control>plus",
                                                   "<Control>KP_Add"])
        self.set_accels_for_action("app.zoom-out", ["<Control>minus", "<Control>KP_Subtract"])
        self.set_accels_for_action("app.zoom::1", ["<Control>0", "<Control>KP_0"])

    def _on_difficulty(self, action, value):
        level = value.get_string()
        if level == "custom":
            dialogs.custom_field(self.window, self.settings["custom"],
                                 lambda w, h, m: self._set_level("custom", [w, h, m]))
            return
        self._set_level(level)

    def _set_level(self, level, custom=None):
        self.settings["difficulty"] = level
        if custom is not None:
            self.settings["custom"] = custom
        self.lookup_action("difficulty").set_state(GLib.Variant("s", level))
        self._save("settings", self.settings)
        self.new_game()

    def _on_toggle(self, action, value):
        name, on = action.get_name(), value.get_boolean()
        action.set_state(value)
        self.settings[name] = on
        if name == "color":
            self._update_css()
            if self.view is not None:
                self.view.queue_draw()
        self._save("settings", self.settings)

    def _show_best(self):
        def reset():
            self.best = store.default_best()
            self._save("best", self.best)
            return self.best
        dialogs.best_times(self.window, self.best, reset)

    def _set_zoom(self, zoom):
        self.settings["zoom"] = zoom
        self._save("settings", self.settings)
        self._apply_size()

    def _apply_size(self):
        """Show the chosen zoom, or the largest below it that fits; settings
        keep the choice for a monitor it fits. Game ▸ Zoom lists what fits."""
        if self.view is None:
            return
        levels = self._fitting_zooms()
        if levels != self._levels:
            self._levels = levels
            self._zoom_levels.remove_all()
            for z in levels:
                self._zoom_levels.append(f"{z * 100:g}%", f"app.zoom::{_zoom_name(z)}")
        self._zoom = max(z for z in levels if z <= self.settings["zoom"])
        self.lookup_action("zoom").set_state(GLib.Variant("s", _zoom_name(self._zoom)))
        self.lookup_action("zoom-in").set_enabled(self._zoom < levels[-1])
        self.lookup_action("zoom-out").set_enabled(self._zoom > 1)
        self.view.resize()

    def _fitting_zooms(self):
        display = Gdk.Display.get_default()
        surface = self.window.get_surface() if self.window else None
        monitor = display.get_monitor_at_surface(surface) if surface else None
        if monitor is None:
            monitors = display.get_monitors()
            monitor = monitors.get_item(0) if monitors.get_n_items() else None
        if monitor is None:
            return (1,)
        g = monitor.get_geometry()
        b = self.game.board
        return geometry.fitting_zooms(b.width, b.height, g.width, g.height)

    # --- play ----------------------------------------------------------------

    def apply(self, effects, sync=True):
        for effect in effects:
            kind = effect[0]
            if kind == "save":
                self._save("game", self.game.to_dict())
            elif kind == "delete":
                self.store.delete("game")
            elif kind == "sound":
                self.sound.play(effect[1])
            elif kind == "best":
                self._best_time(effect[1])
            elif kind == "new_game":
                self.new_game()
            elif kind == "show_keys":
                self.activate_action("keys", None)
            elif kind == "redraw" and self.view is not None:
                self.view.queue_draw()
        if sync:
            self._sync_timer()

    def _best_time(self, level):
        # Already recorded as Anonymous by the session, so closing the window
        # mid-dialog can never lose the time; the dialog only names it.
        self._save("best", self.best)

        def named(name):
            self.best[level][1] = name
            self._save("best", self.best)
            self._show_best()

        dialogs.fastest_time(self.window, level, named)

    def new_game(self):
        self.apply(self.session.new(self._fresh()))
        self._apply_size()

    # --- timer ---------------------------------------------------------------

    def _sync_timer(self):
        want = self.game.ticking
        if want and not self._timer:
            self._timer = GLib.timeout_add(1000, self._tick)
        elif not want and self._timer:
            GLib.source_remove(self._timer)
            self._timer = 0

    def _tick(self):
        self.apply(self.session.tick(), sync=False)
        if not self.game.ticking:
            self._timer = 0
            return GLib.SOURCE_REMOVE
        return GLib.SOURCE_CONTINUE

    # --- persistence ---------------------------------------------------------

    def _save(self, name, data):
        try:
            self.store.save(name, data)
        except OSError as exc:
            print(f"swaysweeper: cannot save {name}: {exc}", file=sys.stderr)

    # --- colours -------------------------------------------------------------

    def _update_css(self):
        c = self.colours
        self._css.load_from_string(
            f".swaysweeper-menubar {{ background: {c['face']}; color: {c['text']}; }}\n"
            f".swaysweeper-menubar > item {{ color: {c['text']}; }}\n")


def run():
    return App().run([sys.argv[0]])
