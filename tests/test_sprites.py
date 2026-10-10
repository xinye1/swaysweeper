import unittest

import cairo

from swaysweeper import colours, sprites
from tests.fixtures import pixel


class Shapes(unittest.TestCase):
    def assertShape(self, sprite, w, h, name):
        self.assertEqual(len(sprite), h, name)
        for row in sprite:
            self.assertEqual(len(row), w, (name, row))
            for ch in row:
                self.assertTrue(ch == "." or ch in sprites.LEGEND, (name, ch))

    def test_cells(self):
        expected = {f"open{n}" for n in range(1, 9)} | {"mine", "flag", "question", "cross"}
        self.assertEqual(set(sprites.CELLS), expected)
        for name, s in sprites.CELLS.items():
            self.assertShape(s, 16, 16, name)

    def test_faces(self):
        self.assertEqual(set(sprites.FACES), {"normal", "wow", "dead", "cool", "pressed"})
        for name, s in sprites.FACES.items():
            self.assertShape(s, 24, 24, name)

    def test_led(self):
        self.assertEqual(set(sprites.LED), set("0123456789-"))
        for name, s in sprites.LED.items():
            self.assertShape(s, 13, 23, name)

    def test_numbers_use_their_own_slot(self):
        for n in range(1, 9):
            chars = {c for row in sprites.CELLS[f"open{n}"] for c in row} - {"."}
            self.assertEqual(chars, {str(n)})

    def test_led_segments(self):
        lit = lambda d: sum(row.count("O") for row in sprites.LED[d])
        self.assertEqual(lit("8"), sum(len(s) for s in sprites._SEGMENTS.values()))
        self.assertEqual(lit("-"), len(sprites._SEGMENTS["g"]))
        self.assertEqual(lit("1"), len(sprites._SEGMENTS["b"]) + len(sprites._SEGMENTS["c"]))

    def test_faces_differ(self):
        faces = [tuple(s) for s in sprites.FACES.values()]
        self.assertEqual(len(set(faces)), len(faces))


class Paint(unittest.TestCase):
    def test_paints_runs_and_skips_transparency(self):
        surf = cairo.ImageSurface(cairo.FORMAT_RGB24, 3, 1)
        cr = cairo.Context(surf)
        cr.set_source_rgb(1, 1, 1)
        cr.paint()
        cr.set_antialias(cairo.ANTIALIAS_NONE)
        sprites.paint(cr, ["11."], 0, 0, colours.WIN95)
        self.assertEqual(pixel(surf, 0, 0), colours.WIN95["num1"])
        self.assertEqual(pixel(surf, 1, 0), colours.WIN95["num1"])
        self.assertEqual(pixel(surf, 2, 0), "#ffffff")


if __name__ == "__main__":
    unittest.main()
