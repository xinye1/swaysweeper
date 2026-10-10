import unittest

from swaysweeper import colours


class Sets(unittest.TestCase):
    def test_sets_cover_exactly_the_slots(self):
        self.assertEqual(set(colours.WIN95), set(colours.SLOTS))
        self.assertEqual(set(colours.MONO), set(colours.SLOTS))

    def test_rgb(self):
        self.assertEqual(colours.rgb("#ff0000"), (1.0, 0.0, 0.0))
        self.assertEqual(colours.rgb("#000080"), (0.0, 0.0, 128 / 255))


if __name__ == "__main__":
    unittest.main()
