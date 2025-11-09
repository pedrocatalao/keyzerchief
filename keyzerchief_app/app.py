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


_ALT_KEY_ATTRS = (
    "KEY_ALT_L",
    "KEY_ALT_R",
    "KEY_ALT",
    "KEY_LALT",
    "KEY_RALT",
    "KEY_OPTION_L",
    "KEY_OPTION_R",
    "KEY_OPTION",
    "KEY_META_L",
    "KEY_META_R",
    "KEY_META",
)


def _build_alt_keys() -> tuple[int, ...]:
    keys: list[int] = []
    for attr in _ALT_KEY_ATTRS:
        key_code = getattr(curses, attr, None)
        if key_code is not None:
            keys.append(key_code)
    return tuple(keys)


ALT_KEYS = _build_alt_keys()

_ALT_CANONICAL_NAMES = {
    "KEY_ALT_L": "ALT_LEFT",
    "KEY_ALT-L": "ALT_LEFT",
    "KEY_LALT": "ALT_LEFT",
    "ALT_L": "ALT_LEFT",
    "ALT_LEFT": "ALT_LEFT",
    "ALT-L": "ALT_LEFT",
    "OPTION_L": "ALT_LEFT",
    "OPTION_LEFT": "ALT_LEFT",
    "OPTION-L": "ALT_LEFT",
    "KEY_OPTION_L": "ALT_LEFT",
    "META_L": "ALT_LEFT",
    "META_LEFT": "ALT_LEFT",
    "META-L": "ALT_LEFT",
    "KEY_META_L": "ALT_LEFT",
    "KEY_ALT_R": "ALT_RIGHT",
    "KEY_ALT-R": "ALT_RIGHT",
    "KEY_RALT": "ALT_RIGHT",
    "ALT_R": "ALT_RIGHT",
    "ALT_RIGHT": "ALT_RIGHT",
    "ALT-R": "ALT_RIGHT",
    "OPTION_R": "ALT_RIGHT",
    "OPTION_RIGHT": "ALT_RIGHT",
    "OPTION-R": "ALT_RIGHT",
    "KEY_OPTION_R": "ALT_RIGHT",
    "META_R": "ALT_RIGHT",
    "META_RIGHT": "ALT_RIGHT",
    "META-R": "ALT_RIGHT",
    "KEY_META_R": "ALT_RIGHT",
    "KEY_ALT": "ALT_GENERIC",
    "ALT": "ALT_GENERIC",
    "KEY_OPTION": "ALT_GENERIC",
    "OPTION": "ALT_GENERIC",
    "KEY_META": "ALT_GENERIC",
    "META": "ALT_GENERIC",
}


def _canonicalize_alt_name(name: str) -> tuple[str, bool] | None:
    normalized = name.upper().replace(" ", "_")
    is_release = False

    if normalized.startswith("KEY_RELEASE_"):
        is_release = True
        normalized = normalized[len("KEY_RELEASE_"):]
    elif normalized.endswith("_RELEASE"):
        is_release = True
        normalized = normalized[: -len("_RELEASE")]

    canonical = _ALT_CANONICAL_NAMES.get(normalized)
    if canonical is None:
        return None

    return canonical, is_release


def _identify_alt_key(key: int | str) -> tuple[str, bool] | None:
    if isinstance(key, str):
        canonical = _canonicalize_alt_name(key)
        if canonical is not None:
            return canonical
        return None

    try:
        key_name = curses.keyname(key)
    except curses.error:
        key_name = None

    if key_name is not None:
        decoded = key_name.decode("ascii", "ignore")
        canonical = _canonicalize_alt_name(decoded)
        if canonical is not None:
            return canonical

    if key in ALT_KEYS:
        return (f"CODE_{key}", False)

    return None


def _extract_function_key_details(symbol: str) -> tuple[int, str] | None:
    normalized = symbol.upper().replace(" ", "_")
    patterns: tuple[tuple[str, str], ...] = (
        ("KEY_ALT_F", "alt"),
        ("KEY_OPTION_F", "alt"),
        ("KEY_META_F", "alt"),
        ("KEY_AF", "alt"),
        ("KEY_SHIFT_F", "shift"),
        ("KEY_SF", "shift"),
        ("KEY_F(", "raw_paren"),
        ("KEY_F", "raw"),
    )

    for prefix, kind in patterns:
        if normalized.startswith(prefix):
            fragment = normalized[len(prefix) :]
            if fragment.startswith("(") and fragment.endswith(")"):
                fragment = fragment[1:-1]
            if kind == "raw_paren":
                fragment = fragment[:-1] if fragment.endswith(")") else fragment
                kind = "raw"
            if fragment.isdigit():
                return int(fragment), kind

    return None


def _resolve_function_key_index(key: int | str) -> tuple[int, int] | None:
    number: int | None = None
    kind: str | None = None
    if isinstance(key, int):
        if curses.KEY_F1 <= key <= curses.KEY_F12:
            number = key - curses.KEY_F0
            kind = "base"
        else:
            try:
                key_name = curses.keyname(key)
            except curses.error:
                key_name = None
            if key_name:
                details = _extract_function_key_details(key_name.decode("ascii", "ignore"))
                if details:
                    number, kind = details
    else:
        details = _extract_function_key_details(key)
        if details:
            number, kind = details

    if number is None or number <= 0 or kind is None:
        return None

    footer_len = len(FOOTER_OPTIONS)

    if kind == "alt":
        index = number - 1
        offset = 24
    elif kind == "shift":
        index = number - 1
        offset = 12
    else:
        offset = None
        for candidate in (0, 12, 24, 36):
            start = candidate + 1
            end = candidate + footer_len
            if start <= number <= end:
                offset = candidate
                index = number - start
                break
        if offset is None:
            return None

    if not 0 <= index < footer_len:
        return None

    return index, offset

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
        alt_key = _identify_alt_key(modifier_identifier)
        if alt_key is not None:
            identifier, is_release = alt_key

            if is_release:
                state.alt_keys_down.discard(identifier)
            else:
                state.alt_keys_down.add(identifier)

            alt_active = bool(state.alt_keys_down)
            if state.alt_mode != alt_active:
                state.alt_mode = alt_active
                draw_footer(stdscr, state)
            continue

        function_key = _resolve_function_key_index(modifier_identifier)
        if function_key is not None and function_key[1] >= 24:
            key_index, _offset = function_key
            temporary_alt = False

            if not state.alt_mode:
                state.alt_mode = True
                draw_footer(stdscr, state)
                temporary_alt = True

            highlight_footer_key(stdscr, key_index, state)

            if temporary_alt and not state.alt_keys_down:
                state.alt_mode = False
                draw_footer(stdscr, state)
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
            if state.alt_mode:
                highlight_footer_key(stdscr, key - curses.KEY_F1, state)
                if not state.alt_keys_down:
                    state.alt_mode = False
                    draw_footer(stdscr, state)
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
