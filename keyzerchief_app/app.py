"""Main application loop for Keyzerchief."""

from __future__ import annotations

import curses
import signal
from types import SimpleNamespace
from typing import Sequence

from .audio import play_sfx
from .constants import (
    FOOTER_OPTIONS,
    LEFT_PANEL,
    MENU_ITEMS,
    MENU_SPACING,
    RIGHT_PANEL,
    SHIFT_FOOTER_OPTIONS,
)
from .curses_setup import init_curses
from .keystore import check_unsaved_changes, find_entry_index_by_alias, get_keystore_entries, save_changes
from .keystore_actions import (
    change_keystore_password,
    delete_entry,
    generate_key_pair,
    import_cert_file,
    import_cert_from_url,
    import_pkcs12_keypair,
    import_pkcs8_keypair,
    open_keystore,
    rename_entry_alias,
)
from .input_listener import start_modifier_monitor, stop_modifier_monitor
from .menu import menu_modal
from .state import AppState
from .ui.layout import draw_clock, draw_footer, draw_menu_bar, draw_ui, highlight_footer_key


def _resolve_function_key_index(key_code: int) -> tuple[int, bool] | None:
    """Return the zero-based function key index and whether shift was implied."""

    if curses.KEY_F1 <= key_code <= curses.KEY_F10:
        return key_code - curses.KEY_F1, False

    shift_start = getattr(curses, "KEY_F13", None)
    if shift_start is not None and shift_start <= key_code <= shift_start + 9:
        return key_code - shift_start, True

    return None


def _capture_escape_sequence(stdscr: "curses.window") -> tuple[str | None, list[int]]:
    """Capture any pending escape sequence following an initial ESC key press."""

    captured: list[int] = []
    stdscr.nodelay(True)
    try:
        while True:
            ch = stdscr.getch()
            if ch == -1:
                break
            captured.append(ch)
    finally:
        stdscr.nodelay(False)
        stdscr.timeout(100)

    if not captured:
        return None, captured

    try:
        sequence = bytes([27, *captured]).decode("ascii", errors="ignore")
    except ValueError:
        sequence = None

    return sequence, captured
from .ui.popups import prompt_import_key_type, show_help_popup


def run_app(stdscr: "curses.window", argv: Sequence[str]) -> None:
    """Entry point for the curses application."""
    state = AppState()
    init_curses()
    stdscr.timeout(100)
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    keystore_arg = argv[0] if argv else None

    selected = 0
    scroll_offset = 0
    detail_scroll = 0
    active_panel = LEFT_PANEL

    entries = [SimpleNamespace(get=lambda k, default=None: {"Alias name": ""}.get(k, default))]  # type: ignore
    draw_ui(stdscr, state, entries, selected, scroll_offset, detail_scroll, active_panel, True)

    open_keystore(stdscr, state, keystore_arg)

    entries = get_keystore_entries(state)
    modifier_monitor = start_modifier_monitor()

    try:
        while True:
            height, width = stdscr.getmaxyx()
            shift_active = modifier_monitor.is_shift_pressed()
            footer_options = SHIFT_FOOTER_OPTIONS if shift_active else FOOTER_OPTIONS
            panel_height = height - 4
            if state.reload_entries:
                state.reload_entries = False
                entries = get_keystore_entries(state)
                selected = 0
                scroll_offset = 0
                detail_scroll = 0

            draw_ui(stdscr, state, entries, selected, scroll_offset, detail_scroll, active_panel)
            draw_footer(stdscr, state, footer_options)
            draw_menu_bar(None, width)
            draw_clock(stdscr, width)

            key = stdscr.getch()

            if key == -1:
                continue

            consumed_codes: list[int] = []
            fkey_info: tuple[int, bool] | None = _resolve_function_key_index(key)
            if key == 27 and fkey_info is None:
                seq, consumed_codes = _capture_escape_sequence(stdscr)
                if seq in ("\x1b[1;2R", "\x1b[13;2~"):
                    fkey_info = (2, True)
                else:
                    for code in reversed(consumed_codes):
                        curses.ungetch(code)

            if key == curses.KEY_MOUSE and state.mouse_enabled:
                try:
                    _, mx, my, _, mouse_event = curses.getmouse()

                    if my == 0:
                        x = 1
                        for i, item in enumerate(MENU_ITEMS):
                            item_len = len(f" {item} ")
                            if x <= mx < x + item_len:
                                active_menu = i
                                draw_ui(
                                    stdscr,
                                    state,
                                    entries,
                                    selected,
                                    scroll_offset,
                                    detail_scroll,
                                    active_panel,
                                    True,
                                )
                                menu_modal(
                                    stdscr,
                                    state,
                                    active_menu,
                                    redraw_main_ui=lambda: draw_ui(
                                        stdscr,
                                        state,
                                        entries,
                                        selected,
                                        scroll_offset,
                                        detail_scroll,
                                        active_panel,
                                        True,
                                    ),
                                )
                                break
                            x += item_len + MENU_SPACING

                    if my == 1 and width // 2 - 6 <= mx < width // 2:
                        selected = 0
                        scroll_offset = 0
                    elif my == height - 2 and width // 2 - 6 <= mx < width // 2:
                        selected = len(entries) - 1
                        scroll_offset = max(0, len(entries) - panel_height)

                    if 1 < my < height - 2:
                        if 0 < mx < width // 2:
                            active_panel = LEFT_PANEL
                        elif mx >= width // 2:
                            active_panel = RIGHT_PANEL

                    if mouse_event & 0x80000:
                        if active_panel == LEFT_PANEL and selected > 0:
                            selected -= 1
                            if selected < scroll_offset:
                                scroll_offset -= 1
                            detail_scroll = 0
                        elif active_panel == RIGHT_PANEL and detail_scroll > 0:
                            detail_scroll -= 1

                    elif mouse_event & 0x8000000:
                        if active_panel == LEFT_PANEL and selected < len(entries) - 1:
                            selected += 1
                            if selected >= scroll_offset + panel_height:
                                scroll_offset += 1
                            detail_scroll = 0
                        elif active_panel == RIGHT_PANEL:
                            detail_scroll += 1
                except curses.error:
                    pass
                continue

            if key == curses.KEY_UP:
                if active_panel == LEFT_PANEL:
                    if selected > 0:
                        selected -= 1
                        if selected < scroll_offset:
                            scroll_offset -= 1
                    detail_scroll = 0
                elif active_panel == RIGHT_PANEL and detail_scroll > 0:
                    detail_scroll -= 1

            elif key == curses.KEY_DOWN:
                if active_panel == LEFT_PANEL:
                    if selected < len(entries) - 1:
                        selected += 1
                        if selected >= scroll_offset + panel_height:
                            scroll_offset += 1
                    detail_scroll = 0
                elif active_panel == RIGHT_PANEL:
                    detail_scroll += 1

            elif key == ord("t"):
                if active_panel == LEFT_PANEL:
                    selected = 0
                    scroll_offset = 0
                else:
                    detail_scroll = 0

            elif key == ord("b"):
                if active_panel == LEFT_PANEL:
                    selected = len(entries) - 1
                    scroll_offset = max(0, len(entries) - panel_height)
                else:
                    detail_scroll = max(0, len(entries[selected].get("__rendered__", [])) - 1)

            elif key in (ord("\t"), 9):
                if active_panel == LEFT_PANEL:
                    active_panel = RIGHT_PANEL
                    play_sfx("swipe-right")
                else:
                    active_panel = LEFT_PANEL
                    play_sfx("swipe-left")

            elif fkey_info is not None:
                key_index, shift_from_code = fkey_info
                shift_active = shift_from_code or modifier_monitor.is_shift_pressed()
                footer_options = SHIFT_FOOTER_OPTIONS if shift_active else FOOTER_OPTIONS

                if 0 <= key_index < len(footer_options):
                    highlight_footer_key(stdscr, key_index, footer_options)

                if shift_active:
                    if key_index == 1:
                        draw_ui(
                            stdscr,
                            state,
                            entries,
                            selected,
                            scroll_offset,
                            detail_scroll,
                            active_panel,
                            True,
                        )
                        alias = generate_key_pair(stdscr, state)
                        if alias:
                            entries = get_keystore_entries(state)
                            selected = find_entry_index_by_alias(entries, alias)
                            check_unsaved_changes(state)
                        continue

                    if key_index == 2:
                        draw_ui(
                            stdscr,
                            state,
                            entries,
                            selected,
                            scroll_offset,
                            detail_scroll,
                            active_panel,
                            True,
                        )
                        choice = prompt_import_key_type(stdscr)
                        if choice == "PKCS #12":
                            alias = import_pkcs12_keypair(stdscr, state)
                        elif choice == "PKCS #8":
                            alias = import_pkcs8_keypair(stdscr, state)
                        else:
                            alias = None
                        if alias:
                            entries = get_keystore_entries(state)
                            selected = find_entry_index_by_alias(entries, alias)
                            check_unsaved_changes(state)
                        continue

                    if key_index == 3:
                        draw_ui(
                            stdscr,
                            state,
                            entries,
                            selected,
                            scroll_offset,
                            detail_scroll,
                            active_panel,
                            True,
                        )
                        alias = import_cert_file(stdscr, state)
                        if alias:
                            entries = get_keystore_entries(state)
                            selected = find_entry_index_by_alias(entries, alias)
                            check_unsaved_changes(state)
                        continue

                    if key_index == 4:
                        draw_ui(
                            stdscr,
                            state,
                            entries,
                            selected,
                            scroll_offset,
                            detail_scroll,
                            active_panel,
                            True,
                        )
                        alias = import_cert_from_url(stdscr, state)
                        if alias:
                            entries = get_keystore_entries(state)
                            selected = find_entry_index_by_alias(entries, alias)
                            check_unsaved_changes(state)
                        continue

                if key_index == 0:
                    draw_ui(
                        stdscr,
                        state,
                        entries,
                        selected,
                        scroll_offset,
                        detail_scroll,
                        active_panel,
                        True,
                    )
                    show_help_popup(stdscr)

                elif key_index == 1:
                    draw_ui(
                        stdscr,
                        state,
                        entries,
                        selected,
                        scroll_offset,
                        detail_scroll,
                        active_panel,
                        True,
                    )
                    change_keystore_password(stdscr, state)
                    check_unsaved_changes(state)

                elif key_index == 5 and entries:
                    alias = entries[selected].get("Alias name")
                    if alias:
                        draw_ui(
                            stdscr,
                            state,
                            entries,
                            selected,
                            scroll_offset,
                            detail_scroll,
                            active_panel,
                            True,
                        )
                        renamed_alias = rename_entry_alias(stdscr, state, alias)
                        if renamed_alias and renamed_alias != alias:
                            entries = get_keystore_entries(state)
                            selected = find_entry_index_by_alias(entries, renamed_alias)
                            check_unsaved_changes(state)

                elif key_index == 6:
                    draw_ui(
                        stdscr,
                        state,
                        entries,
                        selected,
                        scroll_offset,
                        detail_scroll,
                        active_panel,
                        True,
                    )
                    save_changes(stdscr, state)

                elif key_index == 7:
                    draw_ui(
                        stdscr,
                        state,
                        entries,
                        selected,
                        scroll_offset,
                        detail_scroll,
                        active_panel,
                        True,
                    )
                    if delete_entry(entries[selected].get("Alias name"), stdscr, state):
                        entries = get_keystore_entries(state)
                        selected = min(selected, len(entries) - 1)

                elif key_index == 8:
                    draw_ui(
                        stdscr,
                        state,
                        entries,
                        selected,
                        scroll_offset,
                        detail_scroll,
                        active_panel,
                        True,
                    )
                    menu_modal(
                        stdscr,
                        state,
                        0,
                        redraw_main_ui=lambda: draw_ui(
                            stdscr,
                            state,
                            entries,
                            selected,
                            scroll_offset,
                            detail_scroll,
                            active_panel,
                            True,
                        ),
                    )

                elif key_index == 9:
                    result = save_changes(stdscr, state)
                    if result is None:
                        break

            elif key in [ord("q"), ord("Q"), 27]:
                ret = save_changes(stdscr, state)
                if ret is None:
                    break

            if state.has_unsaved_changes and selected == len(entries) - 1:
                scroll_offset = max(0, len(entries) - panel_height)
    finally:
        stop_modifier_monitor()
