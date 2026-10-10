"""The board widget: paints through render.draw, turns raw input into actions."""

import cairo
import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Graphene", "1.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Graphene, Gtk  # noqa: E402

from . import geometry as G  # noqa: E402
from . import render  # noqa: E402
from .board import REVEALED  # noqa: E402
from .gestures import Gestures  # noqa: E402
from .theme import rgb  # noqa: E402

_DIRS = {"Left": (-1, 0), "h": (-1, 0), "Right": (1, 0), "l": (1, 0),
         "Up": (0, -1), "k": (0, -1), "Down": (0, 1), "j": (0, 1)}
_INPUT = (Gdk.EventType.BUTTON_PRESS, Gdk.EventType.BUTTON_RELEASE,
          Gdk.EventType.MOTION_NOTIFY)


class BoardView(Gtk.DrawingArea):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.gestures = Gestures()
        self.cursor = None
        self.cache = render.CellCache()
        self.set_focusable(True)
        self.set_draw_func(self._draw)
        # Legacy, not GestureClick: a click gesture ignores a second button
        # pressed while the first is held, and that IS the chord.
        legacy = Gtk.EventControllerLegacy()
        legacy.connect("event", self._event)
        self.add_controller(legacy)

    # --- geometry ------------------------------------------------------------

    def _layout(self):
        b = self.app.game.board
        return G.layout(b.width, b.height)

    def _origin(self):
        lay, z = self._layout(), self.app.zoom
        ox = max(0, (self.get_width() - lay.width * z) // 2)
        oy = max(0, (self.get_height() - lay.height * z) // 2)
        return ox, oy, z, lay

    def resize(self):
        lay, z = self._layout(), self.app.zoom
        self.set_content_width(lay.width * z)
        self.set_content_height(lay.height * z)
        self.queue_draw()

    def reset_cursor(self):
        self.cursor = None

    def _surface_to_widget(self, sx, sy):
        native = self.get_native()
        nx, ny = native.get_surface_transform()
        ok, p = native.compute_point(self, Graphene.Point().init(sx - nx, sy - ny))
        return (p.x, p.y) if ok else (-1.0, -1.0)

    def _hit(self, sx, sy):
        wx, wy = self._surface_to_widget(sx, sy)
        ox, oy, z, lay = self._origin()
        gx, gy = (wx - ox) / z, (wy - oy) / z
        return G.cell_at(lay, gx, gy), G.on_face(lay, gx, gy)

    # --- input ---------------------------------------------------------------

    def _event(self, controller, _event):
        # PyGObject hands this signal's GdkEvent over as None; the controller
        # still has it.
        event = controller.get_current_event()
        if event is None:
            return False
        kind = event.get_event_type()
        if kind not in _INPUT:
            return False
        ok, sx, sy = event.get_position()
        if not ok:
            return False
        cell, face = self._hit(sx, sy)
        if kind == Gdk.EventType.MOTION_NOTIFY:
            self.gestures.motion(cell, face)
            had_cursor = self.cursor is not None
            if cell is not None:
                self.cursor = None
            if self.gestures.mode or (had_cursor and self.cursor is None):
                self.queue_draw()
            return False
        button = event.get_button()
        if kind == Gdk.EventType.BUTTON_PRESS:
            self.grab_focus()
            shift = bool(event.get_modifier_state() & Gdk.ModifierType.SHIFT_MASK)
            actions = self.gestures.press(button, cell, face, shift=shift,
                                          active=not self.app.game.board.over)
        else:
            actions = self.gestures.release(button, cell, face)
        for action in actions:
            self.app.act(action)
        self.queue_draw()
        return True

    def key(self, keyval, state):
        if state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK):
            return False
        name = Gdk.keyval_name(keyval)
        b = self.app.game.board
        if name in _DIRS:
            if self.cursor is None:
                self.cursor = (b.width // 2, b.height // 2)
            else:
                dx, dy = _DIRS[name]
                x, y = self.cursor
                self.cursor = (min(max(x + dx, 0), b.width - 1),
                               min(max(y + dy, 0), b.height - 1))
            self.queue_draw()
            return True
        if name == "question":
            self.app.activate_action("keys", None)
            return True
        if self.cursor is None:
            return False
        x, y = self.cursor
        if name in ("space", "Return", "KP_Enter"):
            chord = b.marks[y][x] == REVEALED
            self.app.act(("chord" if chord else "reveal", x, y))
        elif name == "f":
            self.app.act(("mark", x, y))
        elif name == "c":
            self.app.act(("chord", x, y))
        else:
            return False
        self.queue_draw()
        return True

    # --- paint ---------------------------------------------------------------

    def _draw(self, _area, cr, _width, _height):
        ox, oy, z, _lay = self._origin()
        colours = self.app.colours
        cr.set_antialias(cairo.ANTIALIAS_NONE)
        cr.set_source_rgb(*rgb(colours["backdrop"]))
        cr.paint()
        cr.translate(ox, oy)
        cr.scale(z, z)
        game = self.app.game
        render.draw(cr, game, colours,
                    pressed=self.gestures.preview(game.board.width, game.board.height),
                    face=self.gestures.face(game.status),
                    cursor=self.cursor, cache=self.cache)
