import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Mock pynput before importing application modules
sys.modules["pynput"] = MagicMock()
sys.modules["pynput.keyboard"] = MagicMock()

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keyzerchief_app.ui.layout import draw_footer, draw_menu_bar  # noqa: E402
from keyzerchief_app.state import AppState  # noqa: E402


class TestLayout(unittest.TestCase):

    def setUp(self):
        self.state = AppState()
        self.mock_stdscr = MagicMock()
        self.mock_stdscr.getmaxyx.return_value = (24, 80)

    @patch('keyzerchief_app.ui.layout.curses.color_pair')
    def test_draw_footer(self, mock_color_pair):
        mock_color_pair.return_value = 0
        options = ["F1 Help", "F10 Quit"]

        draw_footer(self.mock_stdscr, self.state, options)
        # Verify calls to addstr
        self.assertTrue(self.mock_stdscr.addstr.called)
        # We expect 2 calls per option (prefix + label)
        self.assertEqual(self.mock_stdscr.addstr.call_count, 4)

    @patch('keyzerchief_app.ui.layout.curses.newwin')
    @patch('keyzerchief_app.ui.layout.curses.color_pair')
    def test_draw_menu_bar(self, mock_color_pair, mock_newwin):
        mock_color_pair.return_value = 0
        mock_bar_win = MagicMock()
        mock_newwin.return_value = mock_bar_win

        draw_menu_bar(0, 80, self.state)

        mock_newwin.assert_called_once_with(1, 80, 0, 0)
        self.assertTrue(mock_bar_win.addstr.called)
        mock_bar_win.refresh.assert_called_once()


if __name__ == '__main__':
    unittest.main()
