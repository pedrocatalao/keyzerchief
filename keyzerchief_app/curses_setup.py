"""Helpers for configuring the curses environment."""

from __future__ import annotations

import curses

from .constants import (
    COLOR_EXPIRED_RED,
    COLOR_EXPIRED_RED_DIM,
    COLOR_PAIR_CYAN,
    COLOR_PAIR_CYAN_DIM,
    COLOR_PAIR_DARK,
    COLOR_PAIR_DARKER,
    COLOR_PAIR_EXPIRED,
    COLOR_PAIR_EXPIRED_DIM,
    COLOR_PAIR_FKEYS,
    COLOR_PAIR_FIELD,
    COLOR_PAIR_HEADER,
    COLOR_PAIR_HIGHLIGHT_DIM,
    COLOR_PAIR_MENU,
    COLOR_PAIR_SELECTED,
    COLOR_PAIR_SELECTED_DIM,
    COLOR_PAIR_SELECTED_DIM_MORE,
    COLOR_PAIR_WHITE,
    COLOR_PAIR_WHITE_DIM,
)


def init_curses() -> None:
    """Initialise colors and global curses settings."""
    curses.set_escdelay(25)
    curses.curs_set(0)
    curses.start_color()
    curses.use_default_colors()
    curses.init_color(COLOR_EXPIRED_RED, 750, 200, 200)
    curses.init_color(COLOR_EXPIRED_RED_DIM, 600, 150, 150)
    curses.init_pair(COLOR_PAIR_SELECTED, curses.COLOR_BLACK, 80)
    curses.init_pair(COLOR_PAIR_SELECTED_DIM, curses.COLOR_BLACK, 73)
    curses.init_pair(COLOR_PAIR_SELECTED_DIM_MORE, curses.COLOR_BLACK, 23)
    curses.init_pair(COLOR_PAIR_HEADER, curses.COLOR_YELLOW, -1)
    curses.init_pair(COLOR_PAIR_MENU, curses.COLOR_BLACK, curses.COLOR_YELLOW)
    curses.init_pair(COLOR_PAIR_FKEYS, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(COLOR_PAIR_WHITE, 231, -1)
    curses.init_pair(COLOR_PAIR_WHITE_DIM, curses.COLOR_WHITE, -1)
    curses.init_pair(COLOR_PAIR_DARK, 245, -1)
    curses.init_pair(COLOR_PAIR_DARKER, 237, -1)
    curses.init_pair(COLOR_PAIR_CYAN, 116, -1)
    curses.init_pair(COLOR_PAIR_CYAN_DIM, 73, -1)
    curses.init_pair(COLOR_PAIR_EXPIRED, COLOR_EXPIRED_RED, -1)
    curses.init_pair(COLOR_PAIR_EXPIRED_DIM, COLOR_EXPIRED_RED_DIM, -1)
    curses.init_pair(COLOR_PAIR_FIELD, curses.COLOR_WHITE, 234)
    curses.init_pair(COLOR_PAIR_HIGHLIGHT_DIM, curses.COLOR_BLACK, 100)
    curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
