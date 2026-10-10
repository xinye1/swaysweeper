"""Entry point. `--check-colors FILE` never imports GTK."""

import sys

from . import theme

USAGE = "usage: swaysweeper [--check-colors FILE]"


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--check-colors"]:
        if len(argv) != 2:
            print(USAGE, file=sys.stderr)
            return 2
        problems = theme.check_file(argv[1])
        for p in problems:
            print(f"{argv[1]}: {p}", file=sys.stderr)
        return 1 if problems else 0
    if argv:
        print(USAGE, file=sys.stderr)
        return 2
    from .app import run
    return run()
