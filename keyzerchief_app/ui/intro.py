"""Introductory window and logo rendering."""

from __future__ import annotations
from keyzerchief_app import __version__

import base64
import curses
import gzip
import random
import time
from io import BytesIO

from ..audio import play_sfx
from ..constants import (
    COLOR_PAIR_CYAN,
    COLOR_PAIR_EXPIRED_DIM,
    COLOR_PAIR_FKEYS,
    COLOR_PAIR_HEADER,
    COLOR_PAIR_MENU,
    COLOR_PAIR_WHITE_DIM,
    LOGO_X,
    LOGO_Y,
)
from ..keystore import check_password
from ..state import AppState


ASCII_ART_BASE64 = "H4sIAAAAAAAC/+NSAIJH09phqAOG4CITuUAKOpDQRIgeFCEuNAHsynCobEdFROjowK2cXDvQ3YpVKVidAlb3dIF8jCTdC+SjSeOQnYhb18BqQUjBZBtAIgAb0FSANAIAAA=="


def get_logo_lines() -> list[str]:
    """Return decoded logo lines."""
    compressed_data = base64.b64decode(ASCII_ART_BASE64)
    with gzip.GzipFile(fileobj=BytesIO(compressed_data)) as file:
        return file.read().decode("utf-8").splitlines()


def popup_box(win: "curses.window", title: str) -> None:
    height, width = win.getmaxyx()
    win.erase()
    win.box()
    if title:
        win.addstr(0, max(2, (width - len(title)) // 2), title, curses.color_pair(COLOR_PAIR_MENU))


def intro_window(stdscr: "curses.window") -> "curses.window":
    height, width = stdscr.getmaxyx()
    box_width = 50
    box_height = max(len(get_logo_lines()), 5) + 5
    box_y = (height - box_height) // 2
    box_x = (width - box_width) // 2
    intro_win = curses.newwin(box_height, box_width, box_y, box_x)
    popup_box(intro_win, "")
    curses.noecho()
    play_sfx("intro")
    title = f"Keyzer Chief {__version__}"
    for i in range(len(title)):
        intro_win.addstr(4, 26, title[: i + 1], curses.color_pair(COLOR_PAIR_WHITE_DIM) | curses.A_BOLD)
        intro_win.refresh()
        curses.napms(9)
    intro_win.addstr(5, 24, "Java Keystore Manager", curses.color_pair(COLOR_PAIR_CYAN) | curses.A_ITALIC)
    intro_win.addstr(14, 22, "Keystore password:")
    return intro_win


def show_logo(win: "curses.window", final: bool) -> None:
    logo_lines = get_logo_lines()
    if not final:
        temp_lines = [["█" if ch != " " else " " for ch in line] for line in logo_lines]
        for idx, color in enumerate([236, 58, 100, 136, 178]):
            curses.init_pair(30 + idx, color, -1)
            for i, _ in enumerate(temp_lines):
                line = "".join(random.choice("▓ ▒ ░ ▀") if ch != " " else " " for ch in temp_lines[i])
                win.addstr(LOGO_Y + i, LOGO_X, line, curses.color_pair(30 + idx) | curses.A_DIM)
            win.refresh()
            curses.napms(35)

    for i, line in enumerate(logo_lines):
        win.addstr(LOGO_Y + i, LOGO_X, line, curses.color_pair(COLOR_PAIR_HEADER))
    win.refresh()
    curses.napms(100)


def fade_logo(win: "curses.window") -> None:
    logo_lines = get_logo_lines()
    popup_box(win, "")
    for idx, color in enumerate([220, 178, 136, 100, 58, 236, 234]):
        curses.init_pair(30 + idx, color, -1)
        for i, line in enumerate(logo_lines):
            win.addstr(LOGO_Y + i, LOGO_X, line, curses.color_pair(30 + idx) | curses.A_DIM)
        win.refresh()
        curses.napms(35)


def shake_logo(win: "curses.window") -> None:
    logo_lines = get_logo_lines()
    for shake in [-1, 1, -1, 1, 0]:
        for i, line in enumerate(logo_lines):
            win.addstr(LOGO_Y + i, LOGO_X, " " * (len(line) + 1))
        win.refresh()
        for i, line in enumerate(logo_lines):
            win.addstr(LOGO_Y + i, LOGO_X + shake, line, curses.color_pair(COLOR_PAIR_EXPIRED_DIM))
        win.refresh()
        curses.napms(35)
    show_logo(win, True)


def prompt_password(win: "curses.window", state: AppState) -> str:
    win_y, win_x = win.getbegyx()
    bright_attr = curses.color_pair(COLOR_PAIR_MENU) | curses.A_REVERSE | curses.A_BOLD
    dim_attr = curses.color_pair(COLOR_PAIR_FKEYS)
    while True:
        keypad_win = curses.newwin(1, 25, win_y + 15, win_x + 22)
        keypad_win.addstr(0, 0, " " * 24, curses.color_pair(COLOR_PAIR_FKEYS))
        keypad_win.keypad(True)
        keypad_win.move(0, 0)
        win.refresh()
        curses.curs_set(1)
        password = ""

        while True:
            ch = keypad_win.getch()
            play_sfx("typing")
            if ch in [10, 13]:
                if not state.keystore_path or not check_password(state.keystore_path, password):
                    curses.curs_set(0)
                    password = ""
                    shake_logo(win)
                    keypad_win.clear()
                    keypad_win.addstr(0, 0, " " * 24, curses.color_pair(COLOR_PAIR_FKEYS))
                    keypad_win.move(0, 0)
                    curses.curs_set(1)
                else:
                    curses.curs_set(0)
                    fade_logo(win)
                    return password
            elif ch in [27]:
                curses.curs_set(0)
                fade_logo(win)
                raise SystemExit(1)
            elif ch in [curses.KEY_BACKSPACE, 127, 8]:
                curses.curs_set(1)
                if password:
                    password = password[:-1]
                    pos = len(password)
                    keypad_win.addch(0, pos, "◂", bright_attr)
                    keypad_win.addch(0, pos + 1, " ", dim_attr)
                    keypad_win.refresh()
                    time.sleep(0.075)
                    keypad_win.addch(0, pos, " ", curses.color_pair(COLOR_PAIR_FKEYS))
                    keypad_win.move(0, pos)
            elif 32 <= ch <= 126:
                curses.curs_set(1)
                if len(password) + 1 > 24:
                    break
                if len(password) < 30:
                    password += chr(ch)
                    pos = len(password)
                    keypad_win.addch(0, pos - 1, "★", bright_attr)
                    keypad_win.refresh()
                    time.sleep(0.075)
                    keypad_win.addch(0, pos - 1, "★", dim_attr)
                    keypad_win.addch(0, pos, " ", bright_attr)
                    keypad_win.refresh()

