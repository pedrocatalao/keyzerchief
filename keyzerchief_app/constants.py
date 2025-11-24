"""Shared constant values for the Keyzerchief TUI application."""

from pathlib import Path

# Logo position
LOGO_X = 4
LOGO_Y = 2

# Colors
COLOR_EXPIRED_RED = 196
COLOR_EXPIRED_RED_DIM = 197

# Color pairs
COLOR_PAIR_SELECTED = 1
COLOR_PAIR_SELECTED_DIM = 2
COLOR_PAIR_SELECTED_DIM_MORE = 3
COLOR_PAIR_HEADER = 4
COLOR_PAIR_MENU = 5
COLOR_PAIR_FKEYS = 6
COLOR_PAIR_WHITE = 7
COLOR_PAIR_WHITE_DIM = 8
COLOR_PAIR_CYAN = 9
COLOR_PAIR_CYAN_DIM = 10
COLOR_PAIR_EXPIRED = 11
COLOR_PAIR_EXPIRED_DIM = 12
COLOR_PAIR_DARK = 13
COLOR_PAIR_DARKER = 14
COLOR_PAIR_FIELD = 15
COLOR_PAIR_HIGHLIGHT_DIM = 16

# Mouse support constants
LEFT_PANEL = 0
RIGHT_PANEL = 1

# Menu, footer and other settings
BUTTON_SPACING = 4
MENU_SPACING = 3
MENU_ITEMS = ["Left", "File", "Options", "Right"]
FOOTER_OPTIONS = [
    " 1Help",
    " 2Actions",
    " 3Export",
    " 4Verify",
    " 5Copy",
    " 6Rename",
    " 7SetPwd",
    " 8Delete",
    " 9PullDn",
    "10Quit",
]

SHIFT_FOOTER_OPTIONS = [
    " 1Help",
    " 2GenKeyPair",
    " 3ImpKeyPair",
    " 4ImpCert",
    " 5ImpFromWeb",
    " 6      ",
    " 7      ",
    " 8      ",
    " 9PullDn",
    "10Quit",
]

# Application directories
BASE_DIR = Path(__file__).resolve().parent.parent
