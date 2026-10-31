"""The board widget: paints the session, turns raw input into session events."""

import math

import cairo
import gi

gi.require_version("Gdk", "4.0")
gi.require_version("Graphene", "1.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Graphene, Gtk  # noqa: E402

from . import geometry as G  # noqa: E402
from . import render  # noqa: E402
from .colours import rgb  # noqa: E402

_MASKS = ((Gdk.ModifierType.BUTTON1_MASK, 1), (Gdk.ModifierType.BUTTON2_MASK, 2),
          (Gdk.ModifierType.BUTTON3_MASK, 3))
_INPUT = (Gdk.EventType.BUTTON_PRESS, Gdk.EventType.BUTTON_RELEASE,
          Gdk.EventType.MOTION_NOTIFY)
_KEY_NAMES = {"KP_Enter": "Return"}


class BoardView(Gtk.DrawingArea):
    def __init__(self, app):
        super().__init__()
        self.app = app
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
        ox = max(0, (self.get_width() - math.ceil(lay.width * z)) // 2)
        oy = max(0, (self.get_height() - math.ceil(lay.height * z)) // 2)
        return ox, oy, z, lay

    def resize(self):
        lay, z = self._layout(), self.app.zoom
        self.set_content_width(math.ceil(lay.width * z))      # up: never clip the frame
        self.set_content_height(math.ceil(lay.height * z))
        self.queue_draw()

    def _surface_to_widget(self, sx, sy):
        native = self.get_native()
        nx, ny = native.get_surface_transform()
        ok, p = native.compute_point(self, Graphene.Point().init(sx - nx, sy - ny))
        return (p.x, p.y) if ok else (-1.0, -1.0)

    def _game_point(self, sx, sy):
        wx, wy = self._surface_to_widget(sx, sy)
        ox, oy, z, _lay = self._origin()
        return (wx - ox) / z, (wy - oy) / z

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
        px, py = self._game_point(sx, sy)
        session = self.app.session
        if kind == Gdk.EventType.MOTION_NOTIFY:
            self.app.apply(session.motion(px, py))
            return False
        button = event.get_button()
        state = event.get_modifier_state()
        held = frozenset(b for mask, b in _MASKS if state & mask)
        if kind == Gdk.EventType.BUTTON_PRESS:
            self.grab_focus()
            effects = session.press(button, px, py,
                                    shift=bool(state & Gdk.ModifierType.SHIFT_MASK), held=held)
        else:
            effects = session.release(button, px, py, held=held)
        self.app.apply(effects)
        return True

    def key(self, keyval, state):
        if state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK):
            return False
        name = Gdk.keyval_name(keyval)
        effects = self.app.session.key(_KEY_NAMES.get(name, name))
        self.app.apply(effects)
        return ("unhandled",) not in effects

    # --- paint ---------------------------------------------------------------

    def _draw(self, _area, cr, _width, _height):
        ox, oy, z, _lay = self._origin()
        colours = self.app.colours
        cr.set_antialias(cairo.ANTIALIAS_NONE)
        cr.set_source_rgb(*rgb(colours["backdrop"]))
        cr.paint()
        cr.translate(ox, oy)
        cr.scale(z, z)
        face, pressed, cursor = self.app.session.paint_state()
        render.draw(cr, self.app.game, colours, pressed=pressed, face=face,
                    cursor=cursor, cache=self.cache)
