"""Capture Keyzerchief TUI screenshots without an interactive terminal."""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from keyzerchief_app.constants import (
    COLOR_PAIR_DARKER,
    COLOR_PAIR_HEADER,
    COLOR_PAIR_MENU,
    FOOTER_OPTIONS,
    LEFT_PANEL,
    MENU_ITEMS,
    MENU_SPACING,
    RIGHT_PANEL,
)
from keyzerchief_app.curses_setup import init_curses
from keyzerchief_app.keystore import get_keystore_entries
from keyzerchief_app.state import AppState
from keyzerchief_app.ui.layout import draw_footer, draw_menu_bar, draw_ui
from keyzerchief_app.ui.intro import intro_window as real_intro_window
from keyzerchief_app.ui.intro import show_logo as real_show_logo


@dataclass
class Cell:
    char: str = " "
    attr: int = 0


class FakeWindow:
    """Minimal window implementation that mimics ``curses.window``."""

    def __init__(
        self,
        height: int,
        width: int,
        y: int = 0,
        x: int = 0,
        parent: Optional["FakeWindow"] = None,
        registry: Optional["FakeCurses"] = None,
    ) -> None:
        self.height = height
        self.width = width
        self.origin_y = (parent.origin_y if parent else 0) + y
        self.origin_x = (parent.origin_x if parent else 0) + x
        self.parent = parent
        self.root = parent.root if parent else self
        self.registry = registry or getattr(parent, "registry", None)
        if parent is None:
            self.buffer = [[Cell() for _ in range(width)] for _ in range(height)]
        else:
            self.buffer = self.root.buffer
        self.cursor_y = 0
        self.cursor_x = 0
        self.current_attr = 0
        self.background_char = " "
        self.background_attr = 0

    # -- helpers -----------------------------------------------------------------
    def _write(self, y: int, x: int, char: str, attr: Optional[int]) -> None:
        if len(char) != 1:
            raise ValueError("single character expected")
        ay = self.origin_y + y
        ax = self.origin_x + x
        if not (0 <= ay < self.root.height and 0 <= ax < self.root.width):
            return
        cell = self.root.buffer[ay][ax]
        cell.char = char
        cell.attr = attr if attr is not None else self.current_attr

    def _normalize_coords(self, args: Tuple) -> Tuple[int, int, str, Optional[int]]:
        if not args:
            raise TypeError("addstr requires at least one argument")
        if isinstance(args[0], str):
            y, x = self.cursor_y, self.cursor_x
            text = args[0]
            attr = args[1] if len(args) > 1 else None
        elif len(args) >= 3 and isinstance(args[2], str):
            y, x, text = args[:3]
            attr = args[3] if len(args) > 3 else None
        else:
            raise TypeError("Unexpected addstr signature")
        return y, x, text, attr

    # -- curses-like API ---------------------------------------------------------
    def getmaxyx(self) -> Tuple[int, int]:
        return self.height, self.width

    def addstr(self, *args) -> None:  # type: ignore[override]
        y, x, text, attr = self._normalize_coords(args)
        self.cursor_y, self.cursor_x = y, x
        for offset, ch in enumerate(text):
            if ch == "\n":
                self.cursor_y += 1
                self.cursor_x = x
                continue
            self._write(self.cursor_y, self.cursor_x, ch, attr)
            self.cursor_x += 1

    def addch(self, *args) -> None:  # type: ignore[override]
        if len(args) == 1:
            y, x = self.cursor_y, self.cursor_x
            ch = args[0]
            attr = None
        elif len(args) == 2:
            if isinstance(args[0], int) and isinstance(args[1], (str, int)):
                y, x = self.cursor_y, self.cursor_x
                ch, attr = args
            else:
                y, x, ch = args
                attr = None
        elif len(args) >= 3:
            y, x, ch = args[:3]
            attr = args[3] if len(args) > 3 else None
        else:
            raise TypeError("Unexpected addch signature")

        if isinstance(ch, int):
            ch = chr(ch)
        if isinstance(ch, str) and len(ch) != 1:
            ch = ch[0]
        self.cursor_y, self.cursor_x = y, x
        self._write(y, x, ch, attr)
        self.cursor_x += 1

    def hline(self, y: int, x: int, ch: str, n: int) -> None:
        for i in range(n):
            self._write(y, x + i, ch if isinstance(ch, str) else chr(ch), None)

    def bkgd(self, ch: str, attr: int) -> None:
        self.background_char = ch
        self.background_attr = attr
        for y in range(self.height):
            for x in range(self.width):
                self._write(y, x, ch, attr)

    def box(self) -> None:
        h = self.height
        w = self.width
        for x in range(w):
            self._write(0, x, "─", None)
            self._write(h - 1, x, "─", None)
        for y in range(h):
            self._write(y, 0, "│", None)
            self._write(y, w - 1, "│", None)
        for char, coord in zip("┌┐└┘", ((0, 0), (0, w - 1), (h - 1, 0), (h - 1, w - 1))):
            self._write(coord[0], coord[1], char, None)

    def attron(self, attr: int) -> None:
        self.current_attr |= attr

    def attroff(self, attr: int) -> None:
        self.current_attr &= ~attr

    def clear(self) -> None:
        self.erase()

    def erase(self) -> None:
        for y in range(self.height):
            for x in range(self.width):
                self._write(y, x, self.background_char, self.background_attr)
        self.cursor_y = self.cursor_x = 0

    def refresh(self) -> None:  # pragma: no cover - no-op
        return

    def keypad(self, flag: bool) -> None:  # pragma: no cover - no-op
        return

    def nodelay(self, flag: bool) -> None:  # pragma: no cover - no-op
        return

    def move(self, y: int, x: int) -> None:
        self.cursor_y = y
        self.cursor_x = x


class FakeCurses:
    """Lightweight drop-in replacement for the ``curses`` module."""

    COLOR_SHIFT = 8

    A_BOLD = 1 << 16
    A_DIM = 1 << 17
    A_UNDERLINE = 1 << 18
    A_REVERSE = 1 << 19
    A_ITALIC = 1 << 20

    A_CHARTEXT = 0xFF
    A_ATTRIBUTES = ~A_CHARTEXT

    KEY_MOUSE = 409
    KEY_UP = 259
    KEY_DOWN = 258
    KEY_LEFT = 260
    KEY_RIGHT = 261
    KEY_F1 = 265
    KEY_F10 = 274

    ALL_MOUSE_EVENTS = 0
    REPORT_MOUSE_POSITION = 0

    ACS_VLINE = "│"
    ACS_HLINE = "─"
    ACS_ULCORNER = "┌"
    ACS_URCORNER = "┐"
    ACS_LLCORNER = "└"
    ACS_LRCORNER = "┘"

    COLOR_BLACK = 0
    COLOR_RED = 1
    COLOR_GREEN = 2
    COLOR_YELLOW = 3
    COLOR_BLUE = 4
    COLOR_MAGENTA = 5
    COLOR_CYAN = 6
    COLOR_WHITE = 7

    def __init__(self) -> None:
        self.color_pairs: Dict[int, Tuple[int, int]] = {}
        self.custom_colors: Dict[int, Tuple[int, int, int]] = {}
        self.root_window: Optional[FakeWindow] = None

    # -- module-like helpers -----------------------------------------------------
    def color_pair(self, pair_number: int) -> int:
        return pair_number << self.COLOR_SHIFT

    def pair_number(self, attr: int) -> int:
        return (attr >> self.COLOR_SHIFT) & 0xFF

    def newwin(self, height: int, width: int, y: int, x: int) -> FakeWindow:
        if self.root_window is None:
            raise RuntimeError("Root window is not initialised")
        return FakeWindow(height, width, y, x, parent=self.root_window, registry=self)

    def initscr(self) -> FakeWindow:
        if self.root_window is None:
            raise RuntimeError("Root window must be provided externally")
        return self.root_window

    def init_pair(self, pair_number: int, fg: int, bg: int) -> None:
        self.color_pairs[pair_number] = (fg, bg)

    def init_color(self, index: int, r: int, g: int, b: int) -> None:
        self.custom_colors[index] = (r, g, b)

    def curs_set(self, _: int) -> None:  # pragma: no cover - no-op
        return

    def set_escdelay(self, _: int) -> None:  # pragma: no cover - no-op
        return

    def start_color(self) -> None:  # pragma: no cover - no-op
        return

    def use_default_colors(self) -> None:  # pragma: no cover - no-op
        return

    def mousemask(self, _: int) -> None:  # pragma: no cover - no-op
        return
    
    def noecho(self) -> None:  # pragma: no cover - no-op
        return

    def napms(self, _: int) -> None:  # pragma: no cover - no-op
        return


def _xterm_index_to_rgb(index: int) -> Tuple[int, int, int]:
    if index < 0:
        return (28, 28, 28)
    if index < 16:
        base = [
            (0, 0, 0),
            (205, 0, 0),
            (0, 205, 0),
            (205, 205, 0),
            (0, 0, 238),
            (205, 0, 205),
            (0, 205, 205),
            (229, 229, 229),
            (127, 127, 127),
            (255, 0, 0),
            (0, 255, 0),
            (255, 255, 0),
            (92, 92, 255),
            (255, 0, 255),
            (0, 255, 255),
            (255, 255, 255),
        ]
        return base[index]
    if 16 <= index <= 231:
        index -= 16
        r = index // 36
        g = (index % 36) // 6
        b = index % 6
        def level(value: int) -> int:
            return 55 + value * 40 if value else 0
        return level(r), level(g), level(b)
    index = max(232, min(index, 255))
    level = 8 + (index - 232) * 10
    return (level, level, level)


def _scale_custom(color: Tuple[int, int, int]) -> Tuple[int, int, int]:
    return tuple(int(component / 1000 * 255) for component in color)


def _apply_bold(rgb: Tuple[int, int, int]) -> Tuple[int, int, int]:
    return tuple(min(255, int(value * 1.15)) for value in rgb)


def _apply_dim(rgb: Tuple[int, int, int]) -> Tuple[int, int, int]:
    return tuple(int(value * 0.7) for value in rgb)


def _to_hex(rgb: Tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % rgb


def _resolve_color(fake: FakeCurses, index: int) -> Tuple[int, int, int]:
    if index in fake.custom_colors:
        return _scale_custom(fake.custom_colors[index])
    return _xterm_index_to_rgb(index)


def _colors_for_attr(fake: FakeCurses, attr: int) -> Tuple[str, str]:
    pair = fake.pair_number(attr)
    fg_idx, bg_idx = fake.color_pairs.get(pair, (15, -1))
    if attr & FakeCurses.A_REVERSE:
        fg_idx, bg_idx = bg_idx, fg_idx
    fg_rgb = _resolve_color(fake, fg_idx)
    bg_rgb = _resolve_color(fake, bg_idx)
    if attr & FakeCurses.A_BOLD:
        fg_rgb = _apply_bold(fg_rgb)
    if attr & FakeCurses.A_DIM:
        fg_rgb = _apply_dim(fg_rgb)
        bg_rgb = _apply_dim(bg_rgb)
    return _to_hex(fg_rgb), _to_hex(bg_rgb)


def _export_svg(fake: FakeCurses, window: FakeWindow, path: Path, title: str) -> None:
    cell_width = 9
    cell_height = 18
    baseline = 13
    height, width = window.getmaxyx()
    svg_width = width * cell_width
    svg_height = height * cell_height

    lines = ["<?xml version=\"1.0\" encoding=\"UTF-8\"?>"]
    lines.append(
        f"<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{svg_width}\" height=\"{svg_height}\" viewBox=\"0 0 {svg_width} {svg_height}\" role=\"img\" aria-label=\"{title}\">"
    )
    lines.append(f"  <rect width=\"90%\" height=\"90%\" fill=\"#0f1419\" />")
    lines.append("  <g font-family=\"'3270 Nerd Font Mono', 'JetBrains Mono', 'DejaVu Sans Mono', monospace\" font-size=\"21\">")

    for y in range(height):
        for x in range(width):
            cell = window.root.buffer[y][x]
            char = cell.char
            attr = cell.attr or 0
            fg, bg = _colors_for_attr(fake, attr)
            if char == " ":
                if bg != "#0f1419":
                    lines.append(
                        f"    <rect x=\"{x * cell_width}\" y=\"{y * cell_height}\" width=\"{cell_width}\" height=\"{cell_height}\" fill=\"{bg}\" />"
                    )
                continue
            lines.append(
                f"    <rect x=\"{x * cell_width}\" y=\"{y * cell_height}\" width=\"{cell_width}\" height=\"{cell_height}\" fill=\"{bg}\" />"
            )
            escaped = (
                char.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            lines.append(
                f"    <text x=\"{x * cell_width}\" y=\"{y * cell_height + baseline}\" fill=\"{fg}\">{escaped}</text>"
            )

    lines.append("  </g>")
    lines.append("</svg>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _draw_menu_overlay(stdscr: FakeWindow, fake: FakeCurses, active_menu: int, selected_index: int) -> None:
    submenus = {
        "Left": ["Filter"],
        "File": ["Open keystore", "Quit"],
        "Options": ["Enable/Disable mouse"],
        "Right": ["Search content"],
    }
    _, width = stdscr.getmaxyx()
    draw_menu_bar(active_menu, width)
    items = submenus[MENU_ITEMS[active_menu]]
    max_width = max(len(item) for item in items) + 4
    start_x = 1 + sum(len(f" {MENU_ITEMS[i]} ") + MENU_SPACING for i in range(active_menu))
    submenu_win = fake.newwin(len(items) + 2, max_width, 1, start_x)
    submenu_win.bkgd(" ", fake.color_pair(COLOR_PAIR_DARKER))
    submenu_win.box()
    for idx, label in enumerate(items):
        attr = fake.color_pair(COLOR_PAIR_MENU if idx == selected_index else COLOR_PAIR_HEADER)
        submenu_win.addstr(1 + idx, 2, label.ljust(max_width - 4), attr)


def _load_state(demo_path: Path) -> Tuple[AppState, List[dict]]:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jks") as tmp_file:
        tmp_path = Path(tmp_file.name)
    shutil.copyfile(demo_path, tmp_path)
    state = AppState()
    state.original_keystore_path = demo_path
    state.keystore_path = tmp_path
    state.keystore_password = "changeit"
    try:
        entries = get_keystore_entries(state)
    finally:
        tmp_path.unlink(missing_ok=True)
        state.keystore_path = demo_path
    return state, entries

def _render_overview(fake: FakeCurses, demo_path: Path, output: Path) -> None:
    stdscr = fake.root_window
    if stdscr is None:
        raise RuntimeError("Root window missing")
    stdscr.erase()
    state, entries = _load_state(demo_path)
    selected = 1 if len(entries) > 1 else 0
    draw_ui(stdscr, state, entries, selected, 0, 0, LEFT_PANEL)
    draw_footer(stdscr, state, FOOTER_OPTIONS)
    height, width = stdscr.getmaxyx()
    draw_menu_bar(None, width)
    _export_svg(fake, stdscr, output, "Keyzerchief overview screenshot")


def _render_menu(fake: FakeCurses, demo_path: Path, output: Path) -> None:
    stdscr = fake.root_window
    if stdscr is None:
        raise RuntimeError("Root window missing")
    stdscr.erase()
    state, entries = _load_state(demo_path)
    state.right_panel_highlight_term = "keyzerchief"
    draw_ui(stdscr, state, entries, 0, 0, 0, RIGHT_PANEL)
    draw_footer(stdscr, state, FOOTER_OPTIONS)
    _draw_menu_overlay(stdscr, fake, active_menu=1, selected_index=0)
    _export_svg(fake, stdscr, output, "Keyzerchief command menu screenshot")

def _render_intro(fake: FakeCurses, demo_path: Path, output: Path) -> None:
    stdscr = fake.root_window
    if stdscr is None:
        raise RuntimeError("Root window missing")
    stdscr.erase()
    state, entries = _load_state(demo_path)
    draw_ui(stdscr, state, entries, 0, 0, 0, LEFT_PANEL, dim=True)
    draw_footer(stdscr, state, FOOTER_OPTIONS)
    height, width = stdscr.getmaxyx()
    draw_menu_bar(None, width)
    intro_win = real_intro_window(stdscr)
    real_show_logo(intro_win, final=True)
    intro_win.addstr(
        15,
        22,
        "★★★★★★",
        fake.color_pair(COLOR_PAIR_MENU) | FakeCurses.A_BOLD,
    )
    _export_svg(fake, stdscr, output, "Keyzerchief intro window screenshot")


def main() -> None:
    repo_root = REPO_ROOT
    demo_path = repo_root / ".." / "mykeystore.jks"
    if not demo_path.exists():
        raise SystemExit(f"Missing demo keystore at {demo_path}")
    height, width = 30, 140
    fake = FakeCurses()
    root = FakeWindow(height, width, registry=fake)
    fake.root_window = root

    # Monkey patch modules to use our fake curses implementation.
    import keyzerchief_app.curses_setup as curses_setup
    import keyzerchief_app.ui.layout as layout
    import keyzerchief_app.ui.intro as intro
    import keyzerchief_app.menu as menu

    curses_setup.curses = fake
    layout.curses = fake
    intro.curses = fake
    intro.play_sfx = lambda *args, **kwargs: None
    menu.curses = fake

    init_curses()

    screenshots_dir = repo_root / "docs" / "images"
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    _render_intro(fake, demo_path, screenshots_dir / "intro.svg")
    _render_overview(fake, demo_path, screenshots_dir / "overview.svg")
    _render_menu(fake, demo_path, screenshots_dir / "command-menu.svg")


    print("Generated docs/images/intro.svg")
    print("Generated docs/images/overview.svg")
    print("Generated docs/images/command-menu.svg")


if __name__ == "__main__":
    main()
