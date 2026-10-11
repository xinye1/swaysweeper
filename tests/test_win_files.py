"""Files the Windows build takes from the Python package stay in step with it."""

import importlib.util
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGENERATE = "stale: run /usr/bin/python3 tools/gen_c_sprites.py"


def generator():
    spec = importlib.util.spec_from_file_location("gen_c_sprites",
                                                  ROOT / "tools" / "gen_c_sprites.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Generated(unittest.TestCase):
    def test_sprites_header_is_current(self):
        self.assertEqual((ROOT / "win" / "sprites.h").read_text(), generator().header_text(),
                         REGENERATE)

    def test_icon_is_current(self):
        self.assertEqual((ROOT / "win" / "swaysweeper.ico").read_bytes(), generator().ico_bytes(),
                         REGENERATE)

    def test_icon_has_the_five_sizes(self):
        data = generator().ico_bytes()
        _reserved, kind, count = struct.unpack_from("<HHH", data)
        self.assertEqual((kind, count), (1, 5))
        self.assertEqual([data[6 + 16 * i] for i in range(count)], [16, 20, 24, 32, 48])

    def test_icon_corners_are_transparent_and_the_face_is_yellow(self):
        images = generator().icon_images()
        for image in images:
            self.assertEqual(image[0][0][3], 0)
        big = images[-1]                       # 48 px: the 24 px canvas doubled
        self.assertEqual(big[24][24], (0xff, 0xff, 0x00, 255))


if __name__ == "__main__":
    unittest.main()
