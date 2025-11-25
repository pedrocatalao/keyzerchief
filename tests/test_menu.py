import unittest
from unittest.mock import patch, MagicMock, call
import sys
import os
import curses

# Mock pynput before importing application modules
sys.modules["pynput"] = MagicMock()
sys.modules["pynput.keyboard"] = MagicMock()

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keyzerchief_app.menu import (
    menu_modal,
    handle_filter_popup,
    handle_toggle_mouse,
    handle_search_content
)
from keyzerchief_app.state import AppState

class TestMenu(unittest.TestCase):

    def setUp(self):
        self.state = AppState()
        self.mock_stdscr = MagicMock()
        self.mock_stdscr.getmaxyx.return_value = (24, 80)

    @patch('keyzerchief_app.menu.curses.newwin')
    @patch('keyzerchief_app.menu.draw_menu_bar')
    @patch('keyzerchief_app.menu.curses.color_pair')
    def test_menu_navigation(self, mock_color_pair, mock_draw_menu_bar, mock_newwin):
        mock_color_pair.return_value = 0
        mock_submenu = MagicMock()
        mock_newwin.return_value = mock_submenu

        # Simulate keys: Right, Left, Escape
        self.mock_stdscr.getch.side_effect = [
            curses.KEY_RIGHT,
            curses.KEY_LEFT,
            27 # Escape
        ]

        menu_modal(self.mock_stdscr, self.state)

        # Verify draw_menu_bar was called with different active menus
        # Initial call (0), then Right (1), then Left (0)
        # Note: draw_menu_bar is called initially, then after each key press
        self.assertTrue(mock_draw_menu_bar.called)
        self.assertGreaterEqual(mock_draw_menu_bar.call_count, 3)

    @patch('keyzerchief_app.menu.curses.newwin')
    @patch('keyzerchief_app.menu.draw_menu_bar')
    @patch('keyzerchief_app.menu.curses.color_pair')
    @patch('keyzerchief_app.menu.popup_form')
    def test_menu_filter_selection(self, mock_popup_form, mock_color_pair, mock_draw_menu_bar, mock_newwin):
        mock_color_pair.return_value = 0
        mock_submenu = MagicMock()
        mock_newwin.return_value = mock_submenu
        mock_popup_form.return_value = ({"name": "test"}, self.mock_stdscr)

        # "Left" menu is index 0. "Filter" is index 0 in "Left" menu.
        # Sequence: Down (select first item), Enter (activate), Escape (exit loop - wait, Enter returns)
        self.mock_stdscr.getch.side_effect = [
            curses.KEY_DOWN, # Select "Filter"
            10 # Enter
        ]

        menu_modal(self.mock_stdscr, self.state, active_menu=0)

        mock_popup_form.assert_called_once()
        self.assertEqual(self.state.filter_state["name"], "test")
        self.assertTrue(self.state.reload_entries)

    @patch('keyzerchief_app.menu.curses.newwin')
    @patch('keyzerchief_app.menu.draw_menu_bar')
    @patch('keyzerchief_app.menu.curses.color_pair')
    @patch('keyzerchief_app.menu.save_changes')
    def test_menu_quit(self, mock_save_changes, mock_color_pair, mock_draw_menu_bar, mock_newwin):
        mock_color_pair.return_value = 0
        mock_submenu = MagicMock()
        mock_newwin.return_value = mock_submenu
        mock_save_changes.return_value = None # Success

        # "File" menu is index 1. "Quit" is index 2 in "File" menu (["Open keystore", "Save", "Quit"]).
        # Sequence: Down (select "Open keystore"), Down (select "Save"), Down (select "Quit"), Enter
        self.mock_stdscr.getch.side_effect = [
            curses.KEY_DOWN,
            curses.KEY_DOWN,
            curses.KEY_DOWN,
            10
        ]

        with self.assertRaises(SystemExit):
            menu_modal(self.mock_stdscr, self.state, active_menu=1)

    @patch('keyzerchief_app.menu.save_changes')
    @patch('keyzerchief_app.menu.curses.newwin')
    @patch('keyzerchief_app.menu.draw_menu_bar')
    @patch('keyzerchief_app.menu.curses.color_pair')
    def test_menu_save(self, mock_color_pair, mock_draw_menu_bar, mock_newwin, mock_save_changes):
        mock_color_pair.return_value = 0
        mock_submenu = MagicMock()
        mock_newwin.return_value = mock_submenu
        self.state.has_unsaved_changes = True # Enable Save

        # "File" menu is index 1. "Save" is index 1 in "File" menu (["Open keystore", "Save", "Quit"]).
        # Sequence: Down (select "Open keystore"), Down (select "Save"), Enter
        self.mock_stdscr.getch.side_effect = [
            curses.KEY_DOWN,
            curses.KEY_DOWN,
            10
        ]

        menu_modal(self.mock_stdscr, self.state, active_menu=1)

        mock_save_changes.assert_called_once_with(self.mock_stdscr, self.state)

    @patch('keyzerchief_app.menu.save_changes')
    @patch('keyzerchief_app.menu.curses.newwin')
    @patch('keyzerchief_app.menu.draw_menu_bar')
    @patch('keyzerchief_app.menu.curses.color_pair')
    def test_menu_save_disabled(self, mock_color_pair, mock_draw_menu_bar, mock_newwin, mock_save_changes):
        mock_color_pair.return_value = 0
        mock_submenu = MagicMock()
        mock_newwin.return_value = mock_submenu
        self.state.has_unsaved_changes = False # Disable Save

        # "File" menu is index 1. "Save" is index 1 in "File" menu.
        # Sequence: Down, Down, Enter (should do nothing), Escape (to exit)
        self.mock_stdscr.getch.side_effect = [
            curses.KEY_DOWN,
            curses.KEY_DOWN,
            10,
            27
        ]

        menu_modal(self.mock_stdscr, self.state, active_menu=1)

        mock_save_changes.assert_not_called()
        # Verify that we stayed in the menu (consumed all 4 keys: Down, Down, Enter, Escape)
        self.assertEqual(self.mock_stdscr.getch.call_count, 4)
    @patch('keyzerchief_app.menu.popup_form')
    def test_handle_filter_popup(self, mock_popup_form):
        mock_popup_form.return_value = ({"name": "test"}, self.mock_stdscr)

        handle_filter_popup(self.mock_stdscr, self.state)

        self.assertEqual(self.state.filter_state["name"], "test")
        self.assertTrue(self.state.reload_entries)

    @patch('keyzerchief_app.menu.curses.mousemask')
    def test_handle_toggle_mouse(self, mock_mousemask):
        # Initial state: mouse_enabled is True (default in AppState)

        # Toggle off
        handle_toggle_mouse(self.state)
        self.assertFalse(self.state.mouse_enabled)
        mock_mousemask.assert_called_with(0)

        # Toggle on
        handle_toggle_mouse(self.state)
        self.assertTrue(self.state.mouse_enabled)
        mock_mousemask.assert_called_with(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)

    @patch('keyzerchief_app.menu.popup_form')
    def test_handle_search_content(self, mock_popup_form):
        mock_popup_form.return_value = ({"search_term": "searchterm"}, self.mock_stdscr)

        handle_search_content(self.mock_stdscr, self.state)

        self.assertEqual(self.state.right_panel_highlight_term, "searchterm")

    @patch('keyzerchief_app.menu.save_changes')
    @patch('keyzerchief_app.menu.curses.newwin')
    @patch('keyzerchief_app.menu.draw_menu_bar')
    @patch('keyzerchief_app.menu.curses.color_pair')
    def test_menu_up_initial(self, mock_color_pair, mock_draw_menu_bar, mock_newwin, mock_save_changes):
        """Test pressing UP immediately after opening menu (regression test for crash)."""
        mock_color_pair.return_value = 0
        mock_submenu = MagicMock()
        mock_newwin.return_value = mock_submenu
        mock_save_changes.return_value = "esc"  # Prevent SystemExit

        # Sequence: UP (should select last item "Quit"), Enter
        self.mock_stdscr.getch.side_effect = [
            curses.KEY_UP,
            10
        ]

        # Use "File" menu (["Open keystore", "Save", "Quit"])
        menu_modal(self.mock_stdscr, self.state, active_menu=1)

        # Verify that we didn't crash and processed the keys
        self.assertEqual(self.mock_stdscr.getch.call_count, 2)
        # Verify save_changes was called (confirming "Quit" was selected)
        mock_save_changes.assert_called_once()

if __name__ == '__main__':
    unittest.main()
