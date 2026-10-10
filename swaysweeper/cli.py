"""Entry point. Takes no arguments."""

import sys

USAGE = "usage: swaysweeper"


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        print(USAGE, file=sys.stderr)
        return 2
    from .app import run
    return run()
