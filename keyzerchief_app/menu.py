"""Menu handling for the main interface."""

from __future__ import annotations

import curses
from typing import Callable, Optional

from .constants import (
    COLOR_PAIR_DARK,
    COLOR_PAIR_DARKER,
    COLOR_PAIR_HEADER,
    COLOR_PAIR_MENU,
    MENU_ITEMS,
)
from .state import AppState, default_filter_state
from .ui.layout import draw_menu_bar, get_menu_item_positions
from .ui.popups import popup_form
from .keystore_actions import open_keystore
from .keystore import save_changes


def handle_filter_popup(stdscr: "curses.window", state: AppState) -> None:
    form_data, _ = popup_form(
        stdscr,
        title="Filter entries",
        labels=[
            "Name:",
            "Partial name:",
            "Valid:",
            "Expired:",
            "Keys:",
            "Certificates:",
        ],
        choice_fields=[1, 2, 3, 4, 5],
        choice_labels={
            1: ("Yes", "No"),
            2: ("Yes", "No"),
            3: ("Yes", "No"),
            4: ("Yes", "No"),
            5: ("Yes", "No"),
        },
    )
    if form_data:
        state.filter_state.update(form_data)
        state.reload_entries = True


def handle_toggle_mouse(state: AppState) -> None:
    state.mouse_enabled = not state.mouse_enabled
    if state.mouse_enabled:
        curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
    else:
        curses.mousemask(0)


def handle_search_content(stdscr: "curses.window", state: AppState) -> None:
    form_data, _ = popup_form(
        stdscr,
        title="Search content",
        labels=["Search term:"],
        buttons=[" Search ", " Cancel "],
        placeholder_values={0: "Enter a word or phrase to highlight"},
    )

    if not form_data:
        return

    term = form_data.get("search_term")
    if not term:
        return

    state.right_panel_highlight_term = term.lower()


def menu_modal(
    stdscr: "curses.window",
    state: AppState,
    active_menu: int = 0,
    redraw_main_ui: Optional[Callable[[], None]] = None,
) -> tuple[Optional[int], Optional[int]]:
    """Handle navigation within the top menu bar."""
    submenus = {
        "Left": ["Filter", "Clear filter"],
        "File": ["Open keystore", "Save", "Quit"],
        "Options": ["Enable/Disable mouse"],
        "Right": ["Search content"],
    }

    selected_index: Optional[int] = None
    _, width = stdscr.getmaxyx()

    def draw_submenu() -> "curses.window":
        items = submenus[MENU_ITEMS[active_menu]]
        max_width = max(len(item) for item in items) + 4
        box_height = len(items) + 2
        menu_positions = get_menu_item_positions()
        start_x = menu_positions[active_menu][0]
        start_y = 1

        submenu_win = curses.newwin(box_height, max_width, start_y, start_x)
        submenu_win.bkgd(" ", curses.color_pair(COLOR_PAIR_DARKER))
        submenu_win.box()

        for idx, label in enumerate(items):
            is_disabled = False
            if label == "Save" and not state.has_unsaved_changes:
                is_disabled = True
            elif label == "Clear filter" and state.filter_state == default_filter_state():
                is_disabled = True

            if is_disabled:
                if idx == selected_index:
                    attr = curses.color_pair(COLOR_PAIR_DARK) | curses.A_REVERSE
                else:
                    attr = curses.color_pair(COLOR_PAIR_DARK)
            else:
                attr = (
                    curses.color_pair(COLOR_PAIR_MENU)
                    if idx == selected_index
                    else curses.color_pair(COLOR_PAIR_HEADER)
                )
            submenu_win.addstr(1 + idx, 2, label.ljust(max_width - 4), attr)

        submenu_win.refresh()
        return submenu_win

    draw_menu_bar(active_menu, width, state)
    submenu_win = draw_submenu()
    menu_positions = get_menu_item_positions()
    submenu_bounds = {
        "x": menu_positions[active_menu][0],
        "y": 1,
        "width": max(len(item) for item in submenus[MENU_ITEMS[active_menu]]) + 4,
        "height": len(submenus[MENU_ITEMS[active_menu]]) + 2,
    }

    while True:
        key = stdscr.getch()

        if key == curses.KEY_MOUSE:
            _, mx, my, _, mouse_event = curses.getmouse()
            if my == 0:
                # Get accurate menu item positions
                menu_positions = get_menu_item_positions()
                for i, (start_x, end_x) in enumerate(menu_positions):
                    if start_x <= mx < end_x:
                        if active_menu == i:
                            if submenu_win:
                                submenu_win.clear()
                                submenu_win.refresh()
                            return None, None
                        active_menu = i
                        if submenu_win:
                            submenu_win.clear()
                            submenu_win.refresh()
                            submenu_win = None
                            selected_index = None
                        if redraw_main_ui:
                            redraw_main_ui()
                        draw_menu_bar(active_menu, width, state)
                        submenu_win = draw_submenu()
                        break

            elif submenu_win and submenu_bounds:
                # Check if click is inside the submenu window (including borders)
                is_inside_submenu = (
                    submenu_bounds["x"] <= mx < submenu_bounds["x"] + submenu_bounds["width"]
                    and submenu_bounds["y"] <= my < submenu_bounds["y"] + submenu_bounds["height"]
                )

                if is_inside_submenu:
                    # Check if on a specific item (excluding top/bottom borders)
                    if submenu_bounds["y"] < my < submenu_bounds["y"] + submenu_bounds["height"] - 1:
                        selected_index = my - submenu_bounds["y"] - 1
                        submenu_win = draw_submenu()
                        curses.napms(35)
                        items = submenus[MENU_ITEMS[active_menu]]
                        selected_label = items[selected_index]
                        submenu_win.clear()
                        submenu_win.refresh()
                        if redraw_main_ui:
                            redraw_main_ui()
                        if selected_label == "Filter":
                            handle_filter_popup(stdscr, state)
                        elif selected_label == "Open keystore":
                            open_keystore(stdscr, state, None)
                        elif selected_label == "Save":
                            save_changes(stdscr, state)
                        elif selected_label == "Quit":
                            result = save_changes(stdscr, state)
                            if result != "esc":
                                raise SystemExit(0)
                        elif selected_label == "Enable/Disable mouse":
                            handle_toggle_mouse(state)
                        elif selected_label == "Search content":
                            handle_search_content(stdscr, state)
                        elif selected_label == "Clear filter":
                            if state.filter_state != default_filter_state():
                                state.filter_state = default_filter_state()
                                state.reload_entries = True
                        break
                else:
                    # Clicked outside submenu (and not on top bar) -> Close
                    if submenu_win:
                        submenu_win.clear()
                        submenu_win.refresh()
                    return None, None

        elif key == curses.KEY_LEFT:
            if submenu_win:
                submenu_win.clear()
                submenu_win.refresh()
                submenu_win = None
                selected_index = None
            active_menu = (active_menu - 1) % len(MENU_ITEMS)
            if redraw_main_ui:
                redraw_main_ui()
            draw_menu_bar(active_menu, width, state)
            submenu_win = draw_submenu()

        elif key == curses.KEY_RIGHT:
            if submenu_win:
                submenu_win.clear()
                submenu_win.refresh()
                submenu_win = None
                selected_index = None
            active_menu = (active_menu + 1) % len(MENU_ITEMS)
            if redraw_main_ui:
                redraw_main_ui()
            draw_menu_bar(active_menu, width, state)
            submenu_win = draw_submenu()

        elif key == curses.KEY_DOWN:
            if selected_index is None:
                selected_index = 0
            else:
                selected_index = (selected_index + 1) % len(submenus[MENU_ITEMS[active_menu]])
            submenu_win = draw_submenu()

        elif key == curses.KEY_UP and submenu_win:
            if selected_index is None:
                selected_index = len(submenus[MENU_ITEMS[active_menu]]) - 1
            else:
                selected_index = (selected_index - 1) % len(submenus[MENU_ITEMS[active_menu]])
            submenu_win = draw_submenu()

        elif key in [10, 13] and selected_index is not None:
            selected_label = submenus[MENU_ITEMS[active_menu]][selected_index]
            if selected_label == "Filter":
                submenu_win.clear()
                draw_menu_bar(None, width, state)
                if redraw_main_ui:
                    redraw_main_ui()
                handle_filter_popup(stdscr, state)
            elif selected_label == "Open keystore":
                submenu_win.clear()
                draw_menu_bar(None, width, state)
                if redraw_main_ui:
                    redraw_main_ui()
                open_keystore(stdscr, state, None)
            elif selected_label == "Save":
                if state.has_unsaved_changes:
                    submenu_win.clear()
                    draw_menu_bar(None, width, state)
                    if redraw_main_ui:
                        redraw_main_ui()
                    save_changes(stdscr, state)
                else:
                    continue
            elif selected_label == "Quit":
                submenu_win.clear()
                draw_menu_bar(None, width, state)
                if redraw_main_ui:
                    redraw_main_ui()
                result = save_changes(stdscr, state)
                if result != "esc":
                    raise SystemExit(0)
            elif selected_label == "Enable/Disable mouse":
                submenu_win.clear()
                draw_menu_bar(None, width, state)
                if redraw_main_ui:
                    redraw_main_ui()
                handle_toggle_mouse(state)
            elif selected_label == "Search content":
                submenu_win.clear()
                draw_menu_bar(None, width, state)
                if redraw_main_ui:
                    redraw_main_ui()
                handle_search_content(stdscr, state)
            elif selected_label == "Clear filter":
                if state.filter_state != default_filter_state():
                    state.filter_state = default_filter_state()
                    state.reload_entries = True
                    submenu_win.clear()
                    draw_menu_bar(None, width, state)
                    if redraw_main_ui:
                        redraw_main_ui()
                else:
                    continue
            return None, None

        elif key in [curses.KEY_F9, 27]:
            if submenu_win:
                submenu_win.clear()
                submenu_win.refresh()
            return None, None

        elif key == curses.KEY_F10:
            result = save_changes(stdscr, state)
            if result != "esc":
                raise SystemExit(0)
