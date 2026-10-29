"""The GTK app's Game ▸ Zoom wiring. Needs a display; skipped without one."""

import itertools
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

HAVE_DISPLAY = Gtk.init_check()
if HAVE_DISPLAY:
    from swaysweeper.app import APP_ID, App
_ids = itertools.count()


@unittest.skipUnless(HAVE_DISPLAY, "needs a display")
class Zoom(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        env = mock.patch.dict(os.environ, {"XDG_STATE_HOME": self.dir.name})
        env.start()
        self.addCleanup(env.stop)

    def build(self, levels):
        """The window, on a monitor that fits `levels`."""
        fits = mock.patch.object(App, "_fitting_zooms", lambda _self: levels)
        fits.start()
        self.addCleanup(fits.stop)
        app = App()
        app.set_application_id(f"{APP_ID}.test{next(_ids)}")   # one bus path per app
        app.register(None)
        app._build_window()
        self.addCleanup(app.window.destroy)
        return app

    def labels(self, app):
        menu = app._zoom_levels
        return [menu.get_item_attribute_value(i, "label").get_string()
                for i in range(menu.get_n_items())]

    def saved_zoom(self):
        path = Path(self.dir.name, "swaysweeper", "settings.json")
        return json.loads(path.read_text())["zoom"]

    def test_lists_100_when_nothing_bigger_fits(self):
        app = self.build((1,))
        self.assertEqual(self.labels(app), ["100%"])
        self.assertFalse(app.lookup_action("zoom-in").get_enabled())

    def test_lists_the_levels_that_fit(self):
        app = self.build((1, 1.25, 1.5))
        self.assertEqual(self.labels(app), ["100%", "125%", "150%"])

    def test_zoom_in_steps_a_level_and_is_saved(self):
        app = self.build((1, 1.25, 1.5))
        app.lookup_action("zoom-in").activate(None)
        self.assertEqual(app.zoom, 1.25)
        self.assertEqual(app.lookup_action("zoom").get_state().get_string(), "1.25")
        self.assertEqual(self.saved_zoom(), 1.25)

    def test_a_choice_that_doesnt_fit_shows_the_largest_that_does_and_is_kept(self):
        Path(self.dir.name, "swaysweeper").mkdir()
        Path(self.dir.name, "swaysweeper", "settings.json").write_text('{"zoom": 3}')
        app = self.build((1, 1.25))
        self.assertEqual(app.zoom, 1.25)
        self.assertEqual(app.settings["zoom"], 3)

    def test_a_fractional_size_rounds_up(self):
        app = self.build((1, 1.25, 1.5))
        app.lookup_action("zoom-in").activate(None)
        app.lookup_action("zoom-in").activate(None)
        self.assertEqual((app.view.get_content_width(), app.view.get_content_height()),
                         (252, 317))                    # 168 x 211 at 150%: 316.5 -> 317


if __name__ == "__main__":
    unittest.main()
