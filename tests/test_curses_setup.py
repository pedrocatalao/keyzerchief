import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import curses

# Mock pynput before importing application modules
sys.modules["pynput"] = MagicMock()
sys.modules["pynput.keyboard"] = MagicMock()

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keyzerchief_app.curses_setup import init_curses

class TestCursesSetup(unittest.TestCase):

    @patch('keyzerchief_app.curses_setup.curses')
    def test_init_curses(self, mock_curses):
        init_curses()
        
        mock_curses.set_escdelay.assert_called_with(25)
        mock_curses.curs_set.assert_called_with(0)
        mock_curses.start_color.assert_called_once()
        mock_curses.use_default_colors.assert_called_once()
        
        # Verify some color initializations
        self.assertTrue(mock_curses.init_color.called)
        self.assertTrue(mock_curses.init_pair.called)
        
        # Verify mousemask
        mock_curses.mousemask.assert_called_once()

if __name__ == '__main__':
    unittest.main()
