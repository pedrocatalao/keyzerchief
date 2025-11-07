"""Popup helpers used throughout the application."""

from __future__ import annotations

import curses
import os
import time
from typing import Iterable, Optional

from ..constants import (
    BUTTON_SPACING,
    COLOR_PAIR_DARKER,
    COLOR_PAIR_EXPIRED,
    COLOR_PAIR_FIELD,
    COLOR_PAIR_HEADER,
    COLOR_PAIR_MENU,
    COLOR_PAIR_SELECTED,
)


def popup_box(win: "curses.window", title: str) -> None:
    """Draw a bordered popup window with a title."""
    esc_label = "─┤esc├─"
    height, width = win.getmaxyx()
    label_x = width - len(esc_label) - 1
    win.erase()
    win.attron(curses.color_pair(COLOR_PAIR_DARKER))
    win.box()
    win.addstr(0, max(2, (width - len(title)) // 2), f"{title[:width - 4]}", curses.color_pair(COLOR_PAIR_MENU))
    win.addstr(height - 1, label_x, esc_label)
    win.attroff(curses.color_pair(COLOR_PAIR_DARKER))
    win.addstr(height - 1, label_x + 2, "esc", curses.color_pair(COLOR_PAIR_HEADER))


def clear_window(win: "curses.window") -> None:
    """Clear a window interior while preserving its border."""
    height, width = win.getmaxyx()
    for y in range(1, height - 1):
        win.move(y, 1)
        win.addstr(y, 1, " " * (width - 2))


def file_picker(
    stdscr: "curses.window",
    start_path: str = ".",
    title: str = "Select a file:",
    extensions: Optional[Iterable[str]] = None,
) -> Optional[str]:
    """Display a simple file picker dialog."""
    win_height = 20
    win_width = 70
    height, width = stdscr.getmaxyx()
    start_y = (height - win_height) // 2
    start_x = (width - win_width) // 2

    current_path = os.path.abspath(start_path)
    selected_index = 0
    scroll_offset = 0

    curses.curs_set(0)
    win = curses.newwin(win_height, win_width, start_y, start_x)
    win.keypad(True)
    popup_box(win, f"{title} {current_path}")

    while True:
        clear_window(win)
        popup_box(win, f"{title} {current_path}")
        try:
            entries = os.listdir(current_path)
            entries = [
                e
                for e in entries
                if os.path.isdir(os.path.join(current_path, e))
                or not extensions
                or any(e.lower().endswith(ext) for ext in extensions)
            ]
            entries.sort()
            entries = [".."] + entries
        except PermissionError:
            entries = [".."]

        visible_height = win_height - 3
        visible_entries = entries[scroll_offset : scroll_offset + visible_height]

        if selected_index >= len(entries):
            selected_index = len(entries) - 1

        win.addstr(1, 1, f" {'Name':<35} {'Size':>9} {'Modified':>20}", curses.A_BOLD)

        for idx, entry in enumerate(visible_entries):
            actual_index = scroll_offset + idx
            entry_path = os.path.join(current_path, entries[actual_index])
            is_dir = os.path.isdir(entry_path)
            is_cert = entry_path.endswith((".crt", ".cer", ".pem"))
            is_key = entry_path.endswith((".key", ".p12", ".pfx", ".jks"))
            is_selected = actual_index == selected_index

            try:
                size = os.path.getsize(entry_path)
                mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(entry_path)))
            except Exception:
                size = 0
                mtime = ""

            size_str = f"{size:,}" if not is_dir else "<DIR>"
            name_str = f"{entry}/" if is_dir else entry
            if is_selected:
                attr = curses.color_pair(COLOR_PAIR_SELECTED)
            elif is_cert:
                attr = curses.color_pair(COLOR_PAIR_HEADER)
            elif is_key:
                attr = curses.color_pair(COLOR_PAIR_EXPIRED)
            else:
                attr = curses.A_NORMAL

            win.addstr(idx + 2, 1, f" {name_str:<35.35} {size_str:>9} {mtime:>20}", attr)

        key = win.getch()

        if key in [curses.KEY_UP, ord("k")]:
            if selected_index > 0:
                selected_index -= 1
        elif key in [curses.KEY_DOWN, ord("j")]:
            if selected_index < len(entries) - 1:
                selected_index += 1
        elif key in [10, 13]:
            selected_entry = entries[selected_index]
            full_path = os.path.join(current_path, selected_entry)
            if os.path.isdir(full_path):
                current_path = os.path.abspath(full_path)
                selected_index = 0
                scroll_offset = 0
            else:
                win.clear()
                win.refresh()
                return os.path.abspath(full_path)
        elif key in [27]:
            win.clear()
            win.refresh()
            return None

        if selected_index < scroll_offset:
            scroll_offset = selected_index
        elif selected_index >= scroll_offset + visible_height:
            scroll_offset = selected_index - visible_height + 1


def popup_form(
    stdscr: "curses.window",
    title: str,
    labels: list[str],
    file_fields: Optional[list[int]] = None,
    masked_fields: Optional[list[int]] = None,
    choice_fields: Optional[list[int]] = None,
    dependencies: Optional[dict[int, tuple[int, str | tuple[str, ...]]]] = None,
    choice_labels: Optional[dict[int, tuple[str, ...]]] = None,
    default_values: Optional[dict[int, str]] = None,
    placeholder_values: Optional[dict[int, str]] = None,
    buttons: Optional[list[str]] = None,
    rolling: bool = False,
):
    """Collect user input using a vertical form."""
    height, width = stdscr.getmaxyx()
    win_width = 75
    win_height = 2 * len(labels) + 6
    start_y = (height - win_height) // 2
    start_x = (width - win_width) // 2
    buttons = buttons or [" OK ", " Cancel "]

    file_fields = file_fields or []
    masked_fields = masked_fields or []
    choice_fields = choice_fields or []
    dependencies = dependencies or {}
    choice_labels = choice_labels or {i: ("Yes", "No") for i in choice_fields}
    default_values = default_values or {}
    placeholder_values = placeholder_values or {}

    values = [
        default_values.get(i, choice_labels[i][0] if i in choice_fields else "")
        for i in range(len(labels))
    ]
    current = 0
    selected_button = 0
    in_buttons = False

    win = curses.newwin(win_height, win_width, start_y, start_x)
    win.keypad(True)
    field_start_x = max(len(label) for label in labels)

    while True:
        popup_box(win, title)

        for y in range(2, win_height - 3):
            win.addstr(y, 2, " " * (win_width - 4))

        visible_fields: list[int] = []
        for i, label in enumerate(labels):
            dep = dependencies.get(i)
            if dep:
                dep_idx, expected = dep
                if isinstance(expected, (tuple, list)):
                    expected_values = tuple(expected)
                else:
                    expected_values = (expected,)
                if values[dep_idx] not in expected_values:
                    continue

            visible_fields.append(i)
            y = 2 + 2 * len(visible_fields) - 2
            is_selected = not in_buttons and i == current

            if i in choice_fields:
                options = choice_labels.get(i, ("Yes", "No"))
                selected_value = values[i]
                win.addstr(y, field_start_x - len(label) + 2, label)

                if rolling:
                    display_width = win_width - field_start_x - 5
                    attr = curses.A_REVERSE if is_selected else curses.color_pair(COLOR_PAIR_MENU)
                    display_text = f" {selected_value} "
                    win.addstr(
                        y,
                        field_start_x + 3,
                        display_text.ljust(display_width),
                        attr,
                    )
                else:
                    x = field_start_x + 3
                    for opt in options:
                        attr = curses.A_NORMAL
                        if is_selected and selected_value == opt:
                            attr |= curses.A_REVERSE
                        elif not is_selected and selected_value == opt:
                            attr = curses.color_pair(COLOR_PAIR_MENU)

                        win.addstr(y, x, f" {opt} ", attr)
                        x += len(opt) + 3
            else:
                val = values[i] if i not in masked_fields else "*" * len(values[i])

                placeholder = placeholder_values.get(i)
                if not placeholder and i in file_fields:
                    placeholder = "Type path or press enter to browse"

                if is_selected and not values[i] and placeholder:
                    display_val = placeholder
                    attr = curses.A_REVERSE | curses.A_DIM
                else:
                    display_val = val
                    attr = curses.A_REVERSE if is_selected else curses.color_pair(COLOR_PAIR_FIELD)

                win.addstr(y, field_start_x - len(label) + 2, label)
                win.addstr(
                    y,
                    field_start_x + 3,
                    display_val[: win_width - field_start_x - 5].ljust(win_width - field_start_x - 5),
                    attr,
                )

        btn_y = win_height - 2
        btn_x = (win_width - sum(len(b) for b in buttons) - BUTTON_SPACING) // 2
        for i, btn in enumerate(buttons):
            attr = curses.A_REVERSE if in_buttons and selected_button == i else curses.color_pair(COLOR_PAIR_FIELD)
            win.addstr(btn_y, btn_x, btn, attr)
            btn_x += len(btn) + BUTTON_SPACING

        if not in_buttons and current in visible_fields:
            y = 2 + 2 * visible_fields.index(current)
            if current in choice_fields:
                options = choice_labels[current]
                selected_index = options.index(values[current])
                if rolling:
                    x = field_start_x + 3
                else:
                    x = field_start_x + 3 + sum(len(opt) + 3 for opt in options[:selected_index])
                win.move(y, x + 1)
            else:
                val = values[current] if current not in masked_fields else "*" * len(values[current])
                win.move(y, min(field_start_x + 3 + len(val), win_width - 2))

        win.refresh()
        key = win.getch()

        if key == 27:
            return None, win

        if not in_buttons:
            if key == curses.KEY_UP:
                idx = visible_fields.index(current)
                if idx > 0:
                    current = visible_fields[idx - 1]
            elif key in [curses.KEY_DOWN, 9]:
                idx = visible_fields.index(current)
                if idx < len(visible_fields) - 1:
                    current = visible_fields[idx + 1]
                else:
                    in_buttons = True
                    selected_button = 0
            elif current in choice_fields:
                opts = choice_labels.get(current, ("Yes", "No"))
                idx = opts.index(values[current])
                if key == curses.KEY_LEFT:
                    values[current] = opts[(idx - 1) % len(opts)]
                elif key == curses.KEY_RIGHT:
                    values[current] = opts[(idx + 1) % len(opts)]
            elif key in [curses.KEY_BACKSPACE, 127, 8]:
                values[current] = values[current][:-1]
            elif 32 <= key <= 126 and len(values[current]) < 60:
                values[current] += chr(key)
            elif key in [10, 13] and current in file_fields:
                path = file_picker(stdscr, ".", labels[current], [".key", ".p12", ".cer", ".pem", ".crt", ".jks"])
                if path:
                    values[current] = path
        else:
            if key in [curses.KEY_LEFT, curses.KEY_RIGHT, 9]:
                selected_button = 1 - selected_button
            elif key in [10, 13]:
                if selected_button == 0:
                    curses.noecho()
                    return {
                        labels[i].rstrip(':?#').lower().replace(' ', '_'): values[i].strip()
                        for i in visible_fields
                    }, win
                return None, win
            elif key == curses.KEY_UP:
                in_buttons = False


def prompt_import_key_type(stdscr: "curses.window") -> Optional[str]:
    """Display a small menu to choose the key import type."""
    key_types = ["PKCS #12", "PKCS #8", "PVK", "OpenSSL"]
    height, width = stdscr.getmaxyx()
    win_height = len(key_types) + 4
    win_width = max(len(t) for t in key_types) + 13
    win = curses.newwin(win_height, win_width, (height - win_height) // 2, (width - win_width) // 2)
    win.keypad(True)
    popup_box(win, "Import Key Pair")
    selected = 0

    while True:
        for i, option in enumerate(key_types):
            mode = curses.A_REVERSE if i == selected else curses.A_NORMAL
            win.addstr(2 + i, 4, option.ljust(win_width - 8), mode)
        win.refresh()
        key = win.getch()
        if key == curses.KEY_UP and selected > 0:
            selected -= 1
        elif key == curses.KEY_DOWN and selected < len(key_types) - 1:
            selected += 1
        elif key in [10, 13]:
            return key_types[selected]
        elif key in [27]:
            return None
