"""Main application loop for Keyzerchief."""

from __future__ import annotations

import curses
import signal
from types import SimpleNamespace
from typing import Sequence

from .audio import play_sfx
from .constants import FOOTER_OPTIONS, LEFT_PANEL, MENU_ITEMS, MENU_SPACING, RIGHT_PANEL
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
)
from .menu import menu_modal
from .state import AppState
from .ui.layout import draw_footer, draw_menu_bar, draw_ui, highlight_footer_key
from .ui.popups import prompt_import_key_type, show_help_popup


_H_KEY_CODES = {ord("h"), ord("H")}

_H_CANONICAL_NAMES = {
    "H": "H",
    "KEY_H": "H",
    "KEY_DOWN_H": "H",
    "KEY_PRESSED_H": "H",
    "KEY_RELEASED_H": "H",
    "KEY_UP_H": "H",
}


def _canonicalize_h_name(name: str) -> tuple[str, bool] | None:
    normalized = name.upper().replace(" ", "_")
    is_release = False

    if normalized.startswith("KEY_RELEASE_"):
        is_release = True
        normalized = normalized[len("KEY_RELEASE_"):]
    elif normalized.startswith("KEY_RELEASED_"):
        is_release = True
        normalized = normalized[len("KEY_RELEASED_"):]
    elif normalized.startswith("KEY_UP_"):
        is_release = True
        normalized = normalized[len("KEY_UP_"):]
    elif normalized.endswith("_RELEASE"):
        is_release = True
        normalized = normalized[: -len("_RELEASE")]
    elif normalized.endswith("_RELEASED"):
        is_release = True
        normalized = normalized[: -len("_RELEASED")]

    canonical = _H_CANONICAL_NAMES.get(normalized)
    if canonical is None:
        return None

    return canonical, is_release


def _identify_h_modifier(key: int | str) -> bool | None:
    if isinstance(key, int):
        if key in _H_KEY_CODES:
            return True
        try:
            key_name = curses.keyname(key)
        except curses.error:
            key_name = None
        if key_name is not None:
            decoded = key_name.decode("ascii", "ignore")
            canonical = _canonicalize_h_name(decoded)
            if canonical is not None:
                _identifier, is_release = canonical
                return not is_release
        return None

    canonical = _canonicalize_h_name(key)
    if canonical is None:
        return None

    _identifier, is_release = canonical
    return not is_release


def _resolve_function_key_index(key: int | str) -> int | None:
    if isinstance(key, int):
        if curses.KEY_F1 <= key <= curses.KEY_F10:
            return key - curses.KEY_F1
        try:
            key_name = curses.keyname(key)
        except curses.error:
            key_name = None
        if key_name is None:
            return None
        key = key_name.decode("ascii", "ignore")

    if isinstance(key, str):
        normalized = key.upper().replace(" ", "")
        if normalized.startswith("KEY_RELEASE_"):
            return None
        fragment: str | None = None
        if normalized.startswith("KEY_F(") and normalized.endswith(")"):
            fragment = normalized[6:-1]
        elif normalized.startswith("KEY_F"):
            fragment = normalized[5:]
        if fragment and fragment.isdigit():
            number = int(fragment)
            if 1 <= number <= len(FOOTER_OPTIONS):
                return number - 1
    return None


def run_app(stdscr: "curses.window", argv: Sequence[str]) -> None:
    """Entry point for the curses application."""
    state = AppState()
    init_curses()
    stdscr.keypad(True)
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

    while True:
        height, width = stdscr.getmaxyx()
        panel_height = height - 4
        if state.reload_entries:
            state.reload_entries = False
            entries = get_keystore_entries(state)
            selected = 0
            scroll_offset = 0
            detail_scroll = 0

        draw_ui(stdscr, state, entries, selected, scroll_offset, detail_scroll, active_panel)
        draw_footer(stdscr, state)
        draw_menu_bar(None, width)

        try:
            raw_key = stdscr.get_wch()
        except curses.error:
            continue

        key_symbol: str | None = None
        if isinstance(raw_key, str):
            if len(raw_key) == 1:
                key: int | str = ord(raw_key)
            else:
                key_symbol = raw_key
                resolved = getattr(curses, raw_key, None)
                key = resolved if isinstance(resolved, int) else raw_key
        else:
            key = raw_key

        if isinstance(key, int) and key == curses.KEY_MOUSE and state.mouse_enabled:
            try:
                _, mx, my, _, mouse_event = curses.getmouse()

                if my == 0:
                    x = 1
                    for i, item in enumerate(MENU_ITEMS):
                        item_len = len(f" {item} ")
                        if x <= mx < x + item_len:
                            active_menu = i
                            draw_ui(stdscr, state, entries, selected, scroll_offset, detail_scroll, active_panel, True)
                            menu_modal(
                                stdscr,
                                state,
                                active_menu,
                                redraw_main_ui=lambda: draw_ui(
                                    stdscr, state, entries, selected, scroll_offset, detail_scroll, active_panel, True
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

        modifier_identifier = key_symbol or key
        h_event = _identify_h_modifier(modifier_identifier)
        if h_event is not None:
            if h_event:
                if not state.h_modifier_active:
                    state.h_modifier_active = True
                    if not state.alternate_mode:
                        state.alternate_mode = True
                        draw_footer(stdscr, state)
            else:
                if state.h_modifier_active:
                    state.h_modifier_active = False
                if state.alternate_mode:
                    state.alternate_mode = False
                    draw_footer(stdscr, state)
            continue

        function_index = _resolve_function_key_index(modifier_identifier)
        if function_index is not None and state.alternate_mode:
            highlight_footer_key(stdscr, function_index, state)
            continue

        if isinstance(key, int) and key == curses.KEY_UP:
            if active_panel == LEFT_PANEL:
                if selected > 0:
                    selected -= 1
                    if selected < scroll_offset:
                        scroll_offset -= 1
                detail_scroll = 0
            elif active_panel == RIGHT_PANEL and detail_scroll > 0:
                detail_scroll -= 1

        elif isinstance(key, int) and key == curses.KEY_DOWN:
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
            play_sfx("swipe")
            active_panel = RIGHT_PANEL if active_panel == LEFT_PANEL else LEFT_PANEL

        elif isinstance(key, int) and curses.KEY_F1 <= key <= curses.KEY_F10:
            if state.alternate_mode:
                highlight_footer_key(stdscr, key - curses.KEY_F1, state)
                continue

            highlight_footer_key(stdscr, key - curses.KEY_F1, state)

            if key == curses.KEY_F1:
                draw_ui(stdscr, state, entries, selected, scroll_offset, detail_scroll, active_panel, True)
                show_help_popup(stdscr)

            elif key == curses.KEY_F2:
                draw_ui(stdscr, state, entries, selected, scroll_offset, detail_scroll, active_panel, True)
                alias = generate_key_pair(stdscr, state)
                if alias:
                    entries = get_keystore_entries(state)
                    selected = find_entry_index_by_alias(entries, alias)
                    check_unsaved_changes(state)

            elif key == curses.KEY_F3:
                draw_ui(stdscr, state, entries, selected, scroll_offset, detail_scroll, active_panel, True)
                alias = import_cert_file(stdscr, state)
                if alias:
                    entries = get_keystore_entries(state)
                    selected = find_entry_index_by_alias(entries, alias)
                    check_unsaved_changes(state)

            elif key == curses.KEY_F4:
                draw_ui(stdscr, state, entries, selected, scroll_offset, detail_scroll, active_panel, True)
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

            elif key == curses.KEY_F5:
                draw_ui(stdscr, state, entries, selected, scroll_offset, detail_scroll, active_panel, True)
                alias = import_cert_from_url(stdscr, state)
                if alias:
                    entries = get_keystore_entries(state)
                    selected = find_entry_index_by_alias(entries, alias)
                    check_unsaved_changes(state)

            elif key == curses.KEY_F6:
                draw_ui(stdscr, state, entries, selected, scroll_offset, detail_scroll, active_panel, True)
                change_keystore_password(stdscr, state)
                check_unsaved_changes(state)

            elif key == curses.KEY_F7:
                draw_ui(stdscr, state, entries, selected, scroll_offset, detail_scroll, active_panel, True)
                save_changes(stdscr, state)

            elif key == curses.KEY_F8:
                draw_ui(stdscr, state, entries, selected, scroll_offset, detail_scroll, active_panel, True)
                if delete_entry(entries[selected].get("Alias name"), stdscr, state):
                    entries = get_keystore_entries(state)
                    selected = min(selected, len(entries) - 1)

            elif key == curses.KEY_F9:
                draw_ui(stdscr, state, entries, selected, scroll_offset, detail_scroll, active_panel, True)
                menu_modal(
                    stdscr,
                    state,
                    0,
                    redraw_main_ui=lambda: draw_ui(
                        stdscr, state, entries, selected, scroll_offset, detail_scroll, active_panel, True
                    ),
                )

            elif key == curses.KEY_F10:
                result = save_changes(stdscr, state)
                if result is None:
                    break

        elif key in [ord("q"), ord("Q"), 27]:
            ret = save_changes(stdscr, state)
            if ret is None:
                break

        if state.has_unsaved_changes and selected == len(entries) - 1:
            scroll_offset = max(0, len(entries) - panel_height)
