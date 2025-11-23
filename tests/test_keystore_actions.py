import unittest
from unittest.mock import patch, MagicMock
import sys
import os
from pathlib import Path

# Mock pynput before importing application modules
sys.modules["pynput"] = MagicMock()
sys.modules["pynput.keyboard"] = MagicMock()

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keyzerchief_app.state import AppState
from keyzerchief_app.keystore_actions import delete_entry, rename_entry_alias

class TestKeystoreActions(unittest.TestCase):

    def setUp(self):
        self.state = AppState()
        self.state.keystore_path = Path("dummy.jks")
        self.state.keystore_password = "password"
        self.mock_stdscr = MagicMock()
        # Mock getmaxyx to return a decent size
        self.mock_stdscr.getmaxyx.return_value = (24, 80)

    @patch('keyzerchief_app.keystore_actions.subprocess.run')
    @patch('keyzerchief_app.keystore_actions.curses.newwin')
    @patch('keyzerchief_app.keystore_actions.curses.color_pair')
    def test_delete_entry_success(self, mock_color_pair, mock_newwin, mock_run):
        # Mock confirmation window
        mock_confirm_win = MagicMock()
        mock_newwin.return_value = mock_confirm_win
        
        # Mock color_pair to return an integer
        mock_color_pair.return_value = 0
        
        # Simulate user selecting "Yes" (index 0)
        # Sequence: right arrow (switch to No), left arrow (switch to Yes), Enter (confirm)
        # Actually, default is "No" (index 1).
        # To select "Yes" (index 0), we need to press Left or Right once, then Enter.
        # Let's say: KEY_LEFT (switch to Yes), Enter (confirm)
        import curses
        mock_confirm_win.getch.side_effect = [curses.KEY_LEFT, 10]

        # Mock subprocess success
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result

        result = delete_entry("myalias", self.mock_stdscr, self.state)
        
        self.assertTrue(result)
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertIn("-delete", args)
        self.assertIn("myalias", args)

    @patch('keyzerchief_app.keystore_actions.subprocess.run')
    @patch('keyzerchief_app.keystore_actions.curses.newwin')
    @patch('keyzerchief_app.keystore_actions.curses.color_pair')
    def test_delete_entry_cancel(self, mock_color_pair, mock_newwin, mock_run):
        mock_confirm_win = MagicMock()
        mock_newwin.return_value = mock_confirm_win
        
        # Mock color_pair to return an integer
        mock_color_pair.return_value = 0
        
        # Default is "No". Press Enter immediately.
        mock_confirm_win.getch.return_value = 10

        result = delete_entry("myalias", self.mock_stdscr, self.state)
        
        self.assertFalse(result)
        mock_run.assert_not_called()

    @patch('keyzerchief_app.keystore_actions.subprocess.run')
    @patch('keyzerchief_app.keystore_actions.popup_form')
    def test_rename_entry_success(self, mock_popup_form, mock_run):
        # Mock popup form returning new alias
        mock_popup_form.return_value = ({"new_alias": "newname"}, self.mock_stdscr)
        
        # Mock subprocess success
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        # Mock getch for the success message wait
        self.mock_stdscr.getch.return_value = -1

        result = rename_entry_alias(self.mock_stdscr, self.state, "oldname")
        
        self.assertEqual(result, "newname")
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertIn("-changealias", args)
        self.assertIn("oldname", args)
        self.assertIn("newname", args)

    @patch('keyzerchief_app.keystore_actions.popup_form')
    def test_rename_entry_cancel(self, mock_popup_form):
        # Mock popup form returning None (cancelled)
        mock_popup_form.return_value = (None, self.mock_stdscr)
        
        result = rename_entry_alias(self.mock_stdscr, self.state, "oldname")
        
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()
