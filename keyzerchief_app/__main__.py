"""CLI entry point for the Keyzerchief application."""

from __future__ import annotations

import curses
import sys

from .app import run_app


def main(argv: list[str] | None = None) -> None:
    """Run the curses application."""
    if argv is None:
        argv = sys.argv[1:]
    curses.wrapper(lambda stdscr: run_app(stdscr, argv))


if __name__ == "__main__":
    main()
