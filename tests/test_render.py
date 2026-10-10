import unittest

import cairo

from swaysweeper import geometry as G
from swaysweeper import colours, render, sprites
from swaysweeper.board import Board
from swaysweeper.game import Game
from tests.fixtures import pixel


def paint(game, colours, **kw):
    lay = G.layout(game.board.width, game.board.height)
    surf = cairo.ImageSurface(cairo.FORMAT_RGB24, lay.width, lay.height)
    render.draw(cairo.Context(surf), game, colours, **kw)
    return surf


def cell_origin(x, y):
    return G.BOARD_X + G.CELL * x, G.BOARD_Y + G.CELL * y


def first_ink(sprite):
    for y, row in enumerate(sprite):
        for x, ch in enumerate(row):
            if ch != ".":
                return x, y


def lost_expert():
    # The column at x = 15 stops the first click's flood from winning outright.
    g = Game("expert", Board(30, 16, [(15, y) for y in range(16)] + [(0, 15)]))
    g.release(0, 0)
    g.release(0, 15)
    assert g.board.state == "lost"
    return g


class Text(unittest.TestCase):
    def test_counter_text(self):
        self.assertEqual(render.counter_text(10), "010")
        self.assertEqual(render.counter_text(0), "000")
        self.assertEqual(render.counter_text(-5), "-05")
        self.assertEqual(render.counter_text(-99), "-99")


class Chrome(unittest.TestCase):
    def test_frame_is_raised_and_board_sunken(self):
        surf = paint(Game.new("beginner"), colours.WIN95)
        self.assertEqual(pixel(surf, 0, 0), colours.WIN95["light"])
        self.assertEqual(pixel(surf, 167, 210), colours.WIN95["shadow"])
        self.assertEqual(pixel(surf, 9, 52), colours.WIN95["shadow"])
        self.assertEqual(pixel(surf, 158, 201), colours.WIN95["light"])

    def test_covered_cell_is_raised(self):
        surf = paint(Game.new("beginner"), colours.WIN95)
        x, y = cell_origin(0, 0)
        self.assertEqual(pixel(surf, x, y), colours.WIN95["light"])
        self.assertEqual(pixel(surf, x + 8, y + 8), colours.WIN95["face"])
        self.assertEqual(pixel(surf, x + 15, y + 15), colours.WIN95["shadow"])

    def test_led_digits_drawn(self):
        surf = paint(Game.new("beginner"), colours.WIN95)
        lay = G.layout(9, 9)
        # counter "010": the middle digit's top segment (a) is lit, at (x+2, DIGIT_Y+1)
        self.assertEqual(pixel(surf, lay.counter_x[1] + 5, G.DIGIT_Y + 1), colours.WIN95["led_off"])
        self.assertEqual(pixel(surf, lay.counter_x[1] + 11, G.DIGIT_Y + 5), colours.WIN95["led_on"])


class LostBoardSmoke(unittest.TestCase):
    def test_under_every_colour_set(self):
        g = lost_expert()
        for name, palette in (("win95", colours.WIN95), ("mono", colours.MONO)):
            with self.subTest(name):
                surf = paint(g, palette)
                ex, ey = cell_origin(0, 15)
                self.assertEqual(pixel(surf, ex + 1, ey + 1), palette["exploded"])
                nx, ny = cell_origin(0, 14)              # a 1 next to the mine
                gx, gy = first_ink(sprites.CELLS["open1"])
                self.assertEqual(pixel(surf, nx + gx, ny + gy), palette["num1"])


class Interaction(unittest.TestCase):
    def test_pressed_covered_cell_draws_sunken_open(self):
        g = Game.new("beginner")
        surf = paint(g, colours.WIN95, pressed={(0, 0)})
        x, y = cell_origin(0, 0)
        self.assertEqual(pixel(surf, x, y), colours.WIN95["grid"])
        self.assertEqual(pixel(surf, x + 8, y + 8), colours.WIN95["revealed"])

    def test_cursor_outline(self):
        surf = paint(Game.new("beginner"), colours.WIN95, cursor=(4, 4))
        x, y = cell_origin(4, 4)
        self.assertEqual(pixel(surf, x, y), colours.WIN95["cursor"])
        self.assertEqual(pixel(surf, x + 15, y + 15), colours.WIN95["cursor"])

    def test_cache_follows_the_color_toggle(self):
        cache = render.CellCache()
        cache.prepare(colours.WIN95)
        a = cache.get("open1")
        cache.prepare(colours.MONO)
        b = cache.get("open1")
        self.assertIsNot(a, b)
        gx, gy = first_ink(sprites.CELLS["open1"])
        self.assertEqual(pixel(a, gx, gy), colours.WIN95["num1"])
        self.assertEqual(pixel(b, gx, gy), colours.MONO["num1"])


if __name__ == "__main__":
    unittest.main()
