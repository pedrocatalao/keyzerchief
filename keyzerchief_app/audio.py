"""Simple sound playback helpers."""

from __future__ import annotations

import subprocess
import threading
import platform

from .constants import BASE_DIR


def play_sfx(sound_file: str, volume: float = 0.6) -> None:
    """Play a short sound effect asynchronously."""

    if platform.system() != "Darwin":
        return  # skip on non-macOS systems

    def _play() -> None:
        sfx_file = BASE_DIR / "sfx" / f"{sound_file}.mp3"
        subprocess.Popen(["afplay", sfx_file, "-v", str(volume)])

    threading.Thread(target=_play, daemon=True).start()
