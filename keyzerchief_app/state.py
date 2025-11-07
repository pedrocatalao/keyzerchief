"""Application state containers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


def default_filter_state() -> dict[str, str]:
    """Return the default filter configuration."""
    return {
        "name": "",
        "partial_name": "Yes",
        "valid": "Yes",
        "expired": "Yes",
        "keys": "Yes",
        "certificates": "Yes",
    }


@dataclass
class AppState:
    """Encapsulate mutable application state."""

    original_keystore_path: Optional[Path] = None
    keystore_path: Optional[Path] = None
    keystore_password: str = ""
    reload_entries: bool = True
    has_unsaved_changes: bool = False
    mouse_enabled: bool = True
    right_panel_highlight_term: Optional[str] = None
    filter_state: dict[str, str] = field(default_factory=default_filter_state)

    def mark_dirty(self) -> None:
        self.has_unsaved_changes = True

    def mark_clean(self) -> None:
        self.has_unsaved_changes = False
