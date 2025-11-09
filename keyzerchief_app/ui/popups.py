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

    choice_offsets: dict[int, int] = {i: 0 for i in choice_fields}
    visible_choice_ranges: dict[int, tuple[int, int]] = {}

    def compute_visible_options(field_idx: int, offset: int) -> list[tuple[int, str]]:
        options = choice_labels.get(field_idx, ("Yes", "No"))
        if not options:
            return []

        max_offset = len(options) - 1
        offset = max(0, min(offset, max_offset))
        x = field_start_x + 3
        max_x = win_width - 4
        visible: list[tuple[int, str]] = []
        idx = offset

        while idx < len(options):
            opt = options[idx]
            if x + len(opt) + 1 > max_x:
                if not visible:
                    visible.append((idx, opt))
                break
            visible.append((idx, opt))
            x += len(opt) + 3
            idx += 1

        if not visible:
            visible.append((offset, options[offset]))

        return visible

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

                visible_options = compute_visible_options(i, choice_offsets.get(i, 0))
                if visible_options:
                    choice_offsets[i] = visible_options[0][0]
                    visible_choice_ranges[i] = (
                        visible_options[0][0],
                        visible_options[-1][0],
                    )
                else:
                    visible_choice_ranges[i] = (0, 0)

                x = field_start_x + 3
                show_left = visible_options[0][0] > 0 if visible_options else False
                show_right = (
                    visible_options[-1][0] < len(options) - 1 if visible_options else False
                )

                for idx, opt in visible_options:
                    attr = curses.A_NORMAL
                    if is_selected and selected_value == opt:
                        attr |= curses.A_REVERSE
                    elif not is_selected and selected_value == opt:
                        attr = curses.color_pair(COLOR_PAIR_MENU)

                    win.addstr(y, x, f" {opt} ", attr)
                    x += len(opt) + 3

                if is_selected and show_right and x <= win_width - 3:
                    win.addstr(y, min(x, win_width - 5), "》", curses.A_NORMAL)

                if is_selected and show_left and x - 2 >= 2:
                    win.addstr(y, len(label) + 2, "《", curses.A_NORMAL)
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
                if not opts:
                    continue

                try:
                    idx = opts.index(values[current])
                except ValueError:
                    idx = 0
                    values[current] = opts[idx]

                visible_range = visible_choice_ranges.get(current)

                if key == curses.KEY_LEFT and idx > 0:
                    new_idx = idx - 1
                    if visible_range and idx == visible_range[0] and visible_range[0] > 0:
                        choice_offsets[current] = visible_range[0] - 1
                    elif new_idx < choice_offsets.get(current, 0):
                        choice_offsets[current] = new_idx
                    values[current] = opts[new_idx]
                elif key == curses.KEY_RIGHT and idx < len(opts) - 1:
                    new_idx = idx + 1
                    if (
                        visible_range
                        and idx == visible_range[1]
                        and visible_range[1] < len(opts) - 1
                    ):
                        choice_offsets[current] = visible_range[0] + 1
                    values[current] = opts[new_idx]
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


def show_help_popup(stdscr: "curses.window") -> None:
    """Display the keyboard shortcut reference dialog."""
    key_col_width = 16

    def format_item(shortcut: str, description: str) -> str:
        return f"  {shortcut:<{key_col_width}} {description}"

    help_lines = [
        "Navigation:",
        format_item("↑ / ↓", "Move through entries or scroll details"),
        format_item("Tab", "Switch between entries and details panels"),
        format_item("t", "Jump to the first entry / top of details"),
        format_item("b", "Jump to the last entry / bottom of details"),
        format_item("Mouse click", "Activate a panel (if mouse support is enabled)"),
        format_item("Mouse wheel", "Scroll the active panel"),
        "",
        "Main shortcuts:",
        format_item("F1", "Show this help window"),
        format_item("F2", "Change the keystore password"),
        format_item("F3", "Export the selected entry"),
        format_item("F4", "Verify the selected certificate"),
        format_item("F5", "Copy certificate details"),
        format_item("F6", "Rename the selected entry"),
        format_item("F7", "Save keystore changes"),
        format_item("F8", "Delete the selected entry"),
        format_item("F9", "Open the menu bar"),
        format_item("F10", "Save changes and exit"),
        "",
        "Alternative shortcuts (hold Shift):",
        format_item("Shift+F1", "Show this help window"),
        format_item("Shift+F2", "Generate a new key pair"),
        format_item("Shift+F3", "Import a PKCS #12 or PKCS #8 key pair"),
        format_item("Shift+F4", "Import a certificate from file"),
        format_item("Shift+F5", "Import a certificate from URL"),
        format_item("Shift+F9", "Open the menu bar"),
        format_item("Shift+F10", "Save changes and exit"),
        "",
        "General:",
        format_item("Enter", "Activate a highlighted menu option or confirm dialogs"),
        format_item("q / Esc", "Prompt to quit and optionally save changes"),
        format_item("Menu actions", "Filter, open keystore, toggle mouse, search content, quit"),
    ]

    height, width = stdscr.getmaxyx()
    content_width = max(len(line) for line in help_lines)
    available_width = max(20, width - 2)
    target_width = max(70, content_width + 4)
    win_width = min(target_width, available_width + 1)
    if available_width >= 60:
        win_width = max(win_width, 60)

    available_height = max(6, height - 2)
    target_height = max(18, len(help_lines) + 4)
    win_height = min(target_height, available_height)

    start_y = max(0, (height - win_height) // 2)
    start_x = max(0, (width - win_width) // 2)

    win = curses.newwin(win_height, win_width, start_y, start_x)
    win.keypad(True)

    view_height = max(1, win_height - 5)
    max_offset = max(0, len(help_lines) - view_height)
    scroll_offset = 0

    while True:
        popup_box(win, "Help & Shortcuts")
        clear_window(win)

        for idx in range(view_height):
            line_idx = scroll_offset + idx
            y = 2 + idx
            win.move(y, 2)
            if line_idx >= len(help_lines):
                continue
            line = help_lines[line_idx]
            attr = curses.color_pair(COLOR_PAIR_HEADER) if line.endswith(":") else curses.A_NORMAL
            win.addstr(y, 2, line[: win_width - 4], attr)

        instructions = "Use ↑/↓ or PgUp/PgDn to scroll. Enter or Esc to close."
        win.addstr(win_height - 2, 2, instructions[: win_width - 4], curses.color_pair(COLOR_PAIR_FIELD))
        win.refresh()

        key = win.getch()

        if key in (27, ord("q"), ord("Q"), 10, 13):
            break
        if key == curses.KEY_UP and scroll_offset > 0:
            scroll_offset -= 1
        elif key == curses.KEY_DOWN and scroll_offset < max_offset:
            scroll_offset += 1
        elif key == curses.KEY_PPAGE and scroll_offset > 0:
            scroll_offset = max(0, scroll_offset - view_height)
        elif key == curses.KEY_NPAGE and scroll_offset < max_offset:
            scroll_offset = min(max_offset, scroll_offset + view_height)
        elif key == curses.KEY_HOME:
            scroll_offset = 0
        elif key == curses.KEY_END:
            scroll_offset = max_offset

    win.clear()
    win.refresh()


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
