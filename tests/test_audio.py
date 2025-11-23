import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Mock pynput before importing application modules
sys.modules["pynput"] = MagicMock()
sys.modules["pynput.keyboard"] = MagicMock()

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keyzerchief_app.audio import play_sfx

class TestAudio(unittest.TestCase):

    @patch('keyzerchief_app.audio.platform.system')
    @patch('keyzerchief_app.audio.subprocess.Popen')
    def test_play_sfx_macos(self, mock_popen, mock_system):
        mock_system.return_value = "Darwin"
        
        # play_sfx starts a thread, so we need to wait for it or just verify the thread start logic
        # However, since the thread target is an inner function, we can't easily mock it directly without refactoring.
        # But we can verify that Popen is called if we let the thread run (it's daemon).
        # Actually, unit testing threaded code is tricky.
        # A better approach for this simple function is to mock threading.Thread to run synchronously or verify it was called.
        
        with patch('keyzerchief_app.audio.threading.Thread') as mock_thread:
            play_sfx("beep")
            mock_thread.assert_called_once()
            
            # Get the target function passed to Thread
            target = mock_thread.call_args[1]['target']
            
            # Execute the target function to verify subprocess call
            target()
            
            mock_popen.assert_called_once()
            args = mock_popen.call_args[0][0]
            self.assertEqual(args[0], "afplay")
            self.assertIn("beep.mp3", str(args[1]))

    @patch('keyzerchief_app.audio.platform.system')
    @patch('keyzerchief_app.audio.subprocess.Popen')
    def test_play_sfx_non_macos(self, mock_popen, mock_system):
        mock_system.return_value = "Linux"
        
        play_sfx("beep")
        
        mock_popen.assert_not_called()

if __name__ == '__main__':
    unittest.main()
