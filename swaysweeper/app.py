"""The GTK application: window, menu, timer, persistence, live theme."""

import sys
from pathlib import Path

import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402

from . import geometry, store, theme  # noqa: E402
from .board import LOST, PLAYING, READY, WON  # noqa: E402
from .game import Game  # noqa: E402
from .sound import Sound  # noqa: E402
from .view import BoardView  # noqa: E402

APP_ID = "io.github.xinye1.swaysweeper"


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)
        self.store = store.Store(store.state_dir())
        self.settings = self.store.load("settings", store.settings_from) or store.default_settings()
        self.best = self.store.load("best", store.best_from) or store.default_best()
        self.theme_path = Path(GLib.get_user_config_dir()) / "swaysweeper" / "colors.gen.toml"
        self.theme_colours, problems = theme.load_first(self.theme_path)
        for p in problems:
            print(f"swaysweeper: {p}", file=sys.stderr)
        self.sound = Sound(Path(GLib.get_user_cache_dir()) / "swaysweeper")
        saved = self.store.load("game", Game.from_dict)
        if saved is not None and saved.status == PLAYING:
            self.game = saved
            self.settings["difficulty"] = saved.difficulty
            if saved.difficulty == "custom":
                b = saved.board
                self.settings["custom"] = [b.width, b.height, b.mine_count]
        else:
            self.store.delete("game")
            self.game = self._fresh()
        self.window = None
        self.view = None
        self._timer = 0
        self._watcher = None
        self._css = None

    # --- derived -------------------------------------------------------------

    @property
    def colours(self):
        return self.theme_colours if self.settings["color"] else theme.MONO

    @property
    def zoom(self):
        return self.settings["zoom"]

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
        self._watcher = theme.Watcher(self.theme_path, self._theme_changed)

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

    # --- menu (Task 12 replaces both) ------------------------------------------

    def _menu_model(self):
        game = Gio.Menu()
        game.append("_New", "app.new")
        game.append("E_xit", "app.quit")
        bar = Gio.Menu()
        bar.append_submenu("_Game", game)
        return bar

    def _install_actions(self):
        for name, handler in (("new", lambda *_: self.new_game()),
                              ("quit", lambda *_: self.quit())):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", handler)
            self.add_action(action)
        self.set_accels_for_action("app.new", ["F2"])
        self.set_accels_for_action("app.quit", ["<Control>q"])

    def _apply_size(self):
        if self.view is not None:
            self.view.resize()

    # --- play ----------------------------------------------------------------

    def act(self, action):
        kind = action[0]
        if kind == "new":
            self.new_game()
            return
        before = self.game.status
        _, x, y = action
        if kind == "reveal":
            self.game.release(x, y)
        elif kind == "chord":
            self.game.release(x, y, chord=True)
        elif kind == "mark":
            self.game.mark(x, y, self.settings["marks"])
        after = self.game.status
        self._sync_timer()
        self._save_game()
        if self.view is not None:
            self.view.queue_draw()
        if before != after:
            self._status_changed(before, after)

    def _status_changed(self, before, after):
        if self.settings["sound"]:
            if before == READY and after == PLAYING:
                self.sound.play("tick")
            elif after == WON:
                self.sound.play("win")
            elif after == LOST:
                self.sound.play("lose")
        if after == WON:
            self._won()

    def _won(self):
        """Task 12 records best times here."""

    def new_game(self):
        self.game = self._fresh()
        self._sync_timer()
        self._save_game()
        if self.view is not None:
            self.view.reset_cursor()
            self.view.gestures.mode = None
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
        if self.game.tick():
            if self.view is not None:
                self.view.queue_draw()
            self._save_game()
            if self.settings["sound"]:
                self.sound.play("tick")
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

    def _save_game(self):
        if self.game.status == PLAYING:
            self._save("game", self.game.to_dict())
        else:
            self.store.delete("game")

    # --- theme ---------------------------------------------------------------

    def _theme_changed(self):
        new = theme.reload(self.theme_path, self.theme_colours)
        if new is None or new == self.theme_colours:
            return
        self.theme_colours = new
        self._update_css()
        if self.view is not None:
            self.view.queue_draw()

    def _update_css(self):
        c = self.colours
        self._css.load_from_string(
            f".swaysweeper-menubar {{ background: {c['face']}; color: {c['text']}; }}\n"
            f".swaysweeper-menubar > item {{ color: {c['text']}; }}\n")


def run():
    return App().run([sys.argv[0]])
