"""Background listener for modifier keys that curses cannot detect."""

from __future__ import annotations

import threading
from typing import Iterable

from pynput import keyboard


class ModifierKeyMonitor:
    """Track the state of modifier keys using a background listener."""

    _SHIFT_KEYS: tuple[keyboard.Key, ...] = (
        keyboard.Key.shift,
        keyboard.Key.shift_l,
        keyboard.Key.shift_r,
    )

    def __init__(self) -> None:
        self._pressed_keys: set[keyboard.Key | keyboard.KeyCode] = set()
        self._lock = threading.Lock()
        self._listener: keyboard.Listener | None = None

    def start(self) -> None:
        """Start the pynput listener if it isn't already running."""

        if self._listener is not None:
            return

        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.daemon = True
        self._listener.start()

    def stop(self) -> None:
        """Stop the listener and reset captured state."""

        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        with self._lock:
            self._pressed_keys.clear()

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        with self._lock:
            self._pressed_keys.add(key)

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        with self._lock:
            self._pressed_keys.discard(key)

    def _any_pressed(self, keys: Iterable[keyboard.Key]) -> bool:
        with self._lock:
            return any(key in self._pressed_keys for key in keys)

    def is_shift_pressed(self) -> bool:
        """Return ``True`` when any shift key is pressed."""

        return self._any_pressed(self._SHIFT_KEYS)


_MONITOR = ModifierKeyMonitor()


def start_modifier_monitor() -> ModifierKeyMonitor:
    """Ensure the global modifier monitor is running and return it."""

    _MONITOR.start()
    return _MONITOR


def stop_modifier_monitor() -> None:
    """Stop the global modifier monitor."""

    _MONITOR.stop()
