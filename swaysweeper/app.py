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
        self._timer = 0
        self._css = None

    # --- derived -------------------------------------------------------------

    @property
    def colours(self):
        return colours.WIN95 if self.settings["color"] else colours.MONO

    @property
    def zoom(self):
        return self.settings["zoom"]

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
        game.append_section(None, section(
            ("_Marks (?)", "app.marks"), ("Co_lor", "app.color"),
            ("_Sound", "app.sound"), ("_Zoom ×2", "app.zoom")))
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

        for name in ("marks", "color", "sound", "zoom"):
            value = self.settings["zoom"] == 2 if name == "zoom" else self.settings[name]
            action = Gio.SimpleAction.new_stateful(name, None, GLib.Variant("b", value))
            action.connect("change-state", self._on_toggle)
            self.add_action(action)
        self.lookup_action("sound").set_enabled(self.sound.available)

        self.set_accels_for_action("app.new", ["F2"])
        self.set_accels_for_action("app.quit", ["<Control>q"])

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
        if name == "zoom":
            self.settings["zoom"] = 2 if on else 1
            self._apply_size()
        else:
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

    def _apply_size(self):
        if self.view is None:
            return
        fits = self._fits(2)
        zoom = self.lookup_action("zoom")
        zoom.set_enabled(fits)
        if self.settings["zoom"] == 2 and not fits:
            self.settings["zoom"] = 1
            self._save("settings", self.settings)
        zoom.set_state(GLib.Variant("b", self.settings["zoom"] == 2))
        self.view.resize()

    def _fits(self, zoom):
        display = Gdk.Display.get_default()
        surface = self.window.get_surface() if self.window else None
        monitor = display.get_monitor_at_surface(surface) if surface else None
        if monitor is None:
            monitors = display.get_monitors()
            monitor = monitors.get_item(0) if monitors.get_n_items() else None
        if monitor is None:
            return False
        g = monitor.get_geometry()
        b = self.game.board
        return geometry.zoom_fits(b.width, b.height, zoom, g.width, g.height)

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
