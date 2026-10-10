"""Shared test helpers."""


def pixel(surface, x, y):
    surface.flush()
    data, stride = surface.get_data(), surface.get_stride()
    b, g, r, _a = data[y * stride + 4 * x: y * stride + 4 * x + 4]
    return f"#{r:02x}{g:02x}{b:02x}"
