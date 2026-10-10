"""winmine's mouse model (windowing.c:495-548), with no GTK in it.

- Right PRESS marks, unless left is already held (then it turns the press
  into a chord). Left pressed while right is held also chords; so do middle
  and Shift+left.
- A reveal or chord fires on the FIRST button released, on the square under
  the pointer; released off the board, nothing happens.
- The smiley is its own button: pressed while held under the pointer.

Pass `held` (from the event's button mask) whenever you have it: a release
can be delivered elsewhere — to a modal dialog opened mid-gesture — and a
button remembered as down would turn every later left press into a chord.
"""

from .board import LOST, WON

LEFT, MIDDLE, RIGHT = 1, 2, 3


class Gestures:
    def __init__(self):
        self.held = set()
        self.mode = None            # None | "single" | "chord" | "face"
        self.cell = None
        self.on_face = False

    def press(self, button, cell, on_face, shift=False, active=True, held=None):
        if held is not None:               # GTK's mask: buttons down before this press
            self.held = set(held)
        self.held.add(button)
        self.cell, self.on_face = cell, on_face
        if self.mode == "face":
            return []
        if button == LEFT and on_face and self.mode is None and self.held == {LEFT}:
            self.mode = "face"
            return []
        if not active:
            return []
        if button == RIGHT:
            if self.mode == "single":
                self.mode = "chord"
                return []
            if self.mode is None and LEFT not in self.held and cell is not None:
                return [("mark", *cell)]
            return []
        if button == MIDDLE or (button == LEFT and (shift or RIGHT in self.held)):
            self.mode = "chord"
        elif button == LEFT:
            self.mode = "single"
        return []

    def motion(self, cell, on_face):
        self.cell, self.on_face = cell, on_face

    def release(self, button, cell, on_face, held=None):
        if held is not None:               # GTK's mask: buttons down, this one included
            self.held = set(held)
        self.held.discard(button)
        self.cell, self.on_face = cell, on_face
        mode = self.mode
        if mode == "face":
            if button != LEFT:
                return []
            self.mode = None
            return [("new",)] if on_face else []
        self.mode = None
        if mode in ("single", "chord") and cell is not None:
            return [("chord" if mode == "chord" else "reveal", *cell)]
        return []

    def preview(self, width, height):
        if self.cell is None or self.mode not in ("single", "chord"):
            return frozenset()
        x, y = self.cell
        if self.mode == "single":
            return frozenset({(x, y)})
        return frozenset((x + dx, y + dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                         if 0 <= x + dx < width and 0 <= y + dy < height)

    def face(self, status):
        if self.mode == "face" and self.on_face:
            return "pressed"
        if status == LOST:
            return "dead"
        if status == WON:
            return "cool"
        if self.mode in ("single", "chord"):
            return "wow"
        return "normal"
