"""Utilities for interacting with Java keystores."""

from __future__ import annotations

import curses
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import shutil
from typing import Iterable, Optional

from .constants import BUTTON_SPACING, COLOR_PAIR_FIELD
from .state import AppState
from .ui.popups import popup_box


TZ_MAP = {
    "WET": "+0000",
    "WEST": "+0100",
    "CET": "+0100",
    "CEST": "+0200",
}


def check_password(keystore_path: Path | str, password: str) -> bool:
    """Return ``True`` if ``password`` unlocks ``keystore_path``."""
    path = Path(keystore_path)
    try:
        subprocess.run(
            ["keytool", "-list", "-keystore", str(path), "-storepass", password],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False
    return True


def check_unsaved_changes(state: AppState) -> None:
    """Update ``state.has_unsaved_changes`` based on the keystore copies."""
    if not state.original_keystore_path or not state.keystore_path:
        state.mark_clean()
        return

    try:
        with state.original_keystore_path.open("rb") as original, state.keystore_path.open("rb") as working:
            state.has_unsaved_changes = original.read() != working.read()
    except FileNotFoundError:
        # If either file disappears we conservatively assume the session is dirty.
        state.mark_dirty()


def save_changes(stdscr: "curses.window", state: AppState) -> Optional[str]:
    """Prompt to persist the in-memory keystore back to disk."""
    if not state.has_unsaved_changes or not state.keystore_path or not state.original_keystore_path:
        return None

    confirm_height, confirm_width = 7, 50
    height, width = stdscr.getmaxyx()
    confirm_y = (height - confirm_height) // 2
    confirm_x = (width - confirm_width) // 2
    confirm_win = curses.newwin(confirm_height, confirm_width, confirm_y, confirm_x)
    confirm_win.keypad(True)
    popup_box(confirm_win, "Save changes?")
    confirm_win.addstr(2, 2, "Overwrite the original keystore?")

    options = ["Yes", "No"]
    selected_option = 1
    while True:
        btn_y = confirm_height - 2
        btn_x = (confirm_width - sum(len(b) for b in options) - BUTTON_SPACING) // 2
        for i, btn in enumerate(options):
            attr = curses.A_REVERSE if selected_option == i else curses.color_pair(COLOR_PAIR_FIELD)
            confirm_win.addstr(btn_y, btn_x, f" {btn} ", attr)
            btn_x += len(btn) + BUTTON_SPACING
        confirm_win.refresh()

        ch = confirm_win.getch()
        if ch in (curses.KEY_LEFT, curses.KEY_RIGHT, 9):
            selected_option = (selected_option + 1) % len(options)
            continue
        if ch in (10, 13):
            if selected_option == 0:
                shutil.copyfile(state.keystore_path, state.original_keystore_path)
                confirm_win.addstr(5, 2, "Saving:                        ")
                for i in range(30):
                    confirm_win.addstr(5, 10 + i, "█")
                    confirm_win.refresh()
                    curses.napms(20)
                state.mark_clean()
            break
        elif ch == 27:
            return "esc"

    check_unsaved_changes(state)
    return None


def get_keystore_entries(state: AppState) -> list[dict]:
    """Load and parse entries from the active keystore."""
    if not state.keystore_path:
        return []

    result = subprocess.run(
        [
            "keytool",
            "-list",
            "-v",
            "-keystore",
            str(state.keystore_path),
            "-storepass",
            state.keystore_password,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to load keystore:\n{result.stderr}")

    entries: list[dict[str, str]] = []
    current_entry: dict[str, str] = {}
    lines = result.stdout.splitlines()[4:]
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("Alias name:"):
            if current_entry:
                entries.append(current_entry)
            current_entry = {"Alias name": line.split("Alias name:", 1)[1].strip()}
            continue
        if ":" in line:
            key, value = map(str.strip, line.split(":", 1))
            current_entry[key] = value
    if current_entry:
        entries.append(current_entry)

    for entry in entries:
        entry_type = entry.get("Entry type", "")
        entry_type_lower = entry_type.lower()
        entry["__is_key__"] = "key" in entry_type_lower
        entry["__is_cert__"] = "cert" in entry_type_lower or "trustedcert" in entry_type_lower

        if "trustedcertentry" in entry_type_lower:
            entry["__icon__"] = "⬔"
        elif "privatekeyentry" in entry_type_lower:
            entry["__icon__"] = "⬚"
        else:
            entry["__icon__"] = "☠"

        detail_lines: list[tuple[str, str]] = []
        priority = ["Alias name", "Entry type", "Creation date", "Valid from"]
        keys = priority + [k for k in entry if k not in priority and not k.startswith("__")]
        for key in keys:
            value = entry.get(key, "")
            detail_lines.append((key, value))
        entry["__rendered__"] = detail_lines

        valid_from = entry.get("Valid from")
        if valid_from and "until:" in valid_from:
            until_date = parse_until_date(valid_from)
            if until_date is not None:
                entry["__expired__"] = until_date < datetime.now(timezone.utc)
            else:
                entry["__expired__"] = False
        else:
            entry["__expired__"] = False

    return filter_entries(entries, state.filter_state)


def parse_until_date(valid_from: str) -> Optional[datetime]:
    """Extract the end date from the ``Valid from`` field."""
    try:
        until_str = valid_from.split("until:", 1)[1].strip()
        parts = until_str.split()
        if len(parts) >= 2:
            parts[-2] = TZ_MAP.get(parts[-2], "+0000")
        until_str_clean = " ".join(parts)
        return datetime.strptime(until_str_clean, "%a %b %d %H:%M:%S %z %Y")
    except Exception:
        return None


def filter_entries(entries: Iterable[dict], filter_state: dict[str, str]) -> list[dict]:
    """Filter ``entries`` based on ``filter_state`` selections."""
    filtered: list[dict] = []
    for entry in entries:
        alias = entry.get("Alias name", "").lower()
        name_filter = filter_state.get("name", "").lower()
        if name_filter:
            if filter_state.get("partial_name", "Yes") == "Yes":
                if name_filter not in alias:
                    continue
            elif name_filter != alias:
                continue

        expired = bool(entry.get("__expired__", False))
        if filter_state.get("expired", "Yes") == "No" and expired:
            continue
        if filter_state.get("valid", "Yes") == "No" and not expired:
            continue
        if filter_state.get("keys", "Yes") == "No" and entry.get("__is_key__"):
            continue
        if filter_state.get("certificates", "Yes") == "No" and entry.get("__is_cert__"):
            continue

        filtered.append(entry)
    return filtered


def find_entry_index_by_alias(entries: list[dict], alias: str | None) -> int:
    """Return the index of ``alias`` in ``entries`` (defaulting to ``0``)."""
    if not alias:
        return 0
    for index, entry in enumerate(entries):
        if entry.get("Alias name") == alias:
            return index
    return 0
