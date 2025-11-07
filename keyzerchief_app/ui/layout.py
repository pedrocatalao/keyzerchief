"""Drawing helpers for the main UI."""

from __future__ import annotations
"""Drawing helpers for the main UI."""

import curses
from types import SimpleNamespace

from ..constants import (
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
    FOOTER_OPTIONS,
    LEFT_PANEL,
    MENU_ITEMS,
    MENU_SPACING,
    RIGHT_PANEL,
)
from ..state import AppState


def draw_footer(stdscr: "curses.window", state: AppState) -> None:
    """Render the footer with contextual shortcuts."""
    height, width = stdscr.getmaxyx()
    spacing = width // len(FOOTER_OPTIONS)
    for i, item in enumerate(FOOTER_OPTIONS):
        label = item[2:]
        prefix = item[:2]
        attr_key = (
            curses.color_pair(COLOR_PAIR_SELECTED)
            if "Save" in label and state.has_unsaved_changes
            else curses.color_pair(COLOR_PAIR_FKEYS)
        )
        stdscr.addstr(height - 1, i * spacing, prefix, attr_key)
        stdscr.addstr(height - 1, i * spacing + 2, label.ljust(spacing - 2), curses.color_pair(COLOR_PAIR_HEADER))


def highlight_footer_key(stdscr: "curses.window", key_index: int) -> None:
    """Briefly highlight a footer label when its key is pressed."""
    height, width = stdscr.getmaxyx()
    spacing = width // len(FOOTER_OPTIONS)
    label = FOOTER_OPTIONS[key_index][2:]
    stdscr.addstr(
        height - 1,
        key_index * spacing + 2,
        label.ljust(spacing - 2),
        curses.color_pair(COLOR_PAIR_HEADER) | curses.A_BOLD,
    )
    stdscr.refresh()
    curses.napms(200)
    stdscr.addstr(height - 1, key_index * spacing + 2, label.ljust(spacing - 2), curses.color_pair(COLOR_PAIR_HEADER))


def draw_menu_bar(active_menu: int | None, width: int) -> None:
    """Draw the top menu bar."""
    bar_win = curses.newwin(1, width, 0, 0)
    bar_win.bkgd(" ", curses.color_pair(COLOR_PAIR_MENU))
    x = 1
    for i, item in enumerate(MENU_ITEMS):
        if i == active_menu:
            bar_win.attron(curses.A_REVERSE)
        bar_win.addstr(0, x, f" {item} ")
        bar_win.attroff(curses.A_REVERSE)
        x += len(item) + MENU_SPACING
    bar_win.refresh()


def draw_ui(
    stdscr: "curses.window",
    state: AppState,
    entries: list[dict],
    selected: int,
    scroll_offset: int,
    detail_scroll: int,
    active_panel: int,
    dim: bool = False,
) -> int:
    """Render the main two panel layout."""
    if not entries:
        entries = [SimpleNamespace(get=lambda k, default=None: {"Alias name": ""}.get(k, default))]  # type: ignore

    height, width = stdscr.getmaxyx()
    panel_width = width // 2
    max_detail_width = width - panel_width - 5
    visible_height = height - 4

    if dim:
        stdscr.attron(curses.A_DIM)
        title_attr = curses.color_pair(COLOR_PAIR_HEADER) | curses.A_DIM
    else:
        stdscr.attroff(curses.A_DIM)
        title_attr = curses.color_pair(COLOR_PAIR_HEADER)

    if selected < scroll_offset:
        scroll_offset = selected
    elif selected >= scroll_offset + visible_height:
        scroll_offset = selected - visible_height + 1

    for y in range(2, height - 2):
        stdscr.addch(y, 0, curses.ACS_VLINE)
        stdscr.addch(y, panel_width - 1, curses.ACS_VLINE)
        stdscr.addch(y, panel_width, curses.ACS_VLINE)
        stdscr.addch(y, width - 1, curses.ACS_VLINE)

    stdscr.addch(1, 0, curses.ACS_ULCORNER)
    stdscr.addch(1, panel_width - 1, curses.ACS_URCORNER)
    stdscr.hline(1, 1, curses.ACS_HLINE, panel_width - 2)
    stdscr.addstr(1, panel_width - 7, "─┤")
    stdscr.addstr("t", curses.color_pair(COLOR_PAIR_DARK))
    stdscr.addstr("op├")
    keystore_label = str(state.original_keystore_path or "")
    stdscr.addstr(1, 3, f" Keystore: {keystore_label} ", title_attr)
    stdscr.addch(height - 2, 0, curses.ACS_LLCORNER)
    stdscr.addch(height - 2, panel_width - 1, curses.ACS_LRCORNER)
    stdscr.hline(height - 2, 1, curses.ACS_HLINE, panel_width - 2)
    stdscr.addstr(height - 2, panel_width - 7, "─┤")
    stdscr.addstr("b", curses.color_pair(COLOR_PAIR_DARK))
    stdscr.addstr("ot├")

    stdscr.addch(1, panel_width, curses.ACS_ULCORNER)
    stdscr.addch(1, width - 1, curses.ACS_URCORNER)
    stdscr.hline(1, panel_width + 1, curses.ACS_HLINE, width - panel_width - 2)
    stdscr.addstr(1, panel_width + 3, " Details ", title_attr)
    stdscr.addch(height - 2, panel_width, curses.ACS_LLCORNER)
    stdscr.addch(height - 2, width - 1, curses.ACS_LRCORNER)
    stdscr.hline(height - 2, panel_width + 1, curses.ACS_HLINE, width - panel_width - 2)

    for i in range(scroll_offset, min(len(entries), scroll_offset + visible_height)):
        y_pos = 2 + i - scroll_offset
        alias = entries[i].get("Alias name", "<unknown>")
        is_expired = entries[i].get("__expired__", False)
        if active_panel == LEFT_PANEL:
            if i == selected:
                attr = curses.color_pair(COLOR_PAIR_SELECTED if not dim else COLOR_PAIR_SELECTED_DIM_MORE)
            elif is_expired:
                attr = curses.color_pair(COLOR_PAIR_EXPIRED)
            else:
                attr = curses.color_pair(COLOR_PAIR_WHITE)
        else:
            if i == selected:
                attr = curses.color_pair(COLOR_PAIR_SELECTED_DIM if not dim else COLOR_PAIR_SELECTED_DIM_MORE)
            elif is_expired:
                attr = curses.color_pair(COLOR_PAIR_EXPIRED_DIM)
            else:
                attr = curses.color_pair(COLOR_PAIR_WHITE_DIM)

        if dim:
            attr |= curses.A_DIM

        stdscr.addstr(y_pos, 2, " " * (panel_width - 4))
        stdscr.addstr(y_pos, 2, alias[: panel_width - 4], attr)

    for y in range(2 + len(entries) - scroll_offset, height - 2):
        stdscr.addstr(y, 2, " " * (panel_width - 4))

    detail_lines = entries[selected].get("__rendered__", [])[detail_scroll:]
    line_num = 2
    highlight_term = state.right_panel_highlight_term.lower() if state.right_panel_highlight_term else None
    for key, value in detail_lines:
        if line_num >= height - 2:
            break
        lines = [value[i : i + max_detail_width] for i in range(0, len(value), max_detail_width)]
        attr = curses.color_pair(COLOR_PAIR_WHITE if active_panel == RIGHT_PANEL else COLOR_PAIR_WHITE_DIM)
        attr_title = curses.color_pair(COLOR_PAIR_CYAN if active_panel == RIGHT_PANEL else COLOR_PAIR_CYAN_DIM)
        attr_expired = curses.color_pair(COLOR_PAIR_EXPIRED if active_panel == RIGHT_PANEL else COLOR_PAIR_EXPIRED_DIM)
        highlight_attr = curses.color_pair(COLOR_PAIR_MENU)

        if dim:
            attr |= curses.A_DIM
            attr_title |= curses.A_DIM
            attr_expired |= curses.A_DIM
            highlight_attr = curses.color_pair(COLOR_PAIR_HIGHLIGHT_DIM)

        stdscr.addstr(line_num, panel_width + 2, " " * (width - panel_width - 3))

        key_str = str(key)
        x = panel_width + 2
        start = 0
        lower_key = key_str.lower()
        while start < len(key_str):
            idx = lower_key.find(highlight_term, start) if highlight_term else -1
            if idx == -1:
                color = attr_expired if key == "Valid from" and entries[selected].get("__expired__") else attr_title
                stdscr.addstr(line_num, x, key_str[start:] + ":", curses.A_UNDERLINE | color)
                x += len(key_str[start:]) + 1
                break
            if idx > start:
                color = attr_expired if key == "Valid from" and entries[selected].get("__expired__") else attr_title
                stdscr.addstr(line_num, x, key_str[start:idx], curses.A_UNDERLINE | color)
                x += idx - start
            stdscr.addstr(line_num, x, key_str[idx : idx + len(highlight_term)], curses.A_UNDERLINE | highlight_attr)
            x += len(highlight_term)
            start = idx + len(highlight_term)
        else:
            stdscr.addstr(line_num, x, ":", curses.A_UNDERLINE | attr_title)

        line_num += 1
        for segment in lines:
            if line_num >= height - 2:
                break
            stdscr.addstr(line_num, panel_width + 2, " " * (width - panel_width - 3))
            if highlight_term and highlight_term in segment.lower():
                start = 0
                x = panel_width + 4
                segment_lower = segment.lower()
                while start < len(segment):
                    idx = segment_lower.find(highlight_term, start)
                    if idx == -1:
                        stdscr.addstr(line_num, x, segment[start:], attr)
                        break
                    if idx > start:
                        stdscr.addstr(line_num, x, segment[start:idx], attr)
                        x += idx - start
                    stdscr.addstr(line_num, x, segment[idx : idx + len(highlight_term)], highlight_attr)
                    x += len(highlight_term)
                    start = idx + len(highlight_term)
            else:
                stdscr.addstr(line_num, panel_width + 4, segment, attr)
            line_num += 1

    for y in range(line_num, height - 2):
        stdscr.addstr(y, panel_width + 2, " " * (width - panel_width - 3))

    stdscr.move(0, 0)
    stdscr.refresh()
    return scroll_offset
