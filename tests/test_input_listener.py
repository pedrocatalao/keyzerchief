import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Mock pynput before importing application modules
sys.modules["pynput"] = MagicMock()
sys.modules["pynput.keyboard"] = MagicMock()

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keyzerchief_app.input_listener import ModifierKeyMonitor

class TestModifierKeyMonitor(unittest.TestCase):

    def setUp(self):
        self.monitor = ModifierKeyMonitor()

    @patch('keyzerchief_app.input_listener.keyboard.Listener')
    def test_start_stop(self, mock_listener_cls):
        mock_listener_instance = MagicMock()
        mock_listener_cls.return_value = mock_listener_instance
        
        # Test start
        self.monitor.start()
        mock_listener_cls.assert_called_once()
        mock_listener_instance.start.assert_called_once()
        self.assertIsNotNone(self.monitor._listener)
        
        # Test start again (should be no-op)
        self.monitor.start()
        mock_listener_cls.assert_called_once() # Still called only once
        
        # Test stop
        self.monitor.stop()
        mock_listener_instance.stop.assert_called_once()
        self.assertIsNone(self.monitor._listener)

    def test_key_tracking(self):
        key = MagicMock()
        
        # Test on_press
        self.monitor._on_press(key)
        self.assertIn(key, self.monitor._pressed_keys)
        
        # Test on_release
        self.monitor._on_release(key)
        self.assertNotIn(key, self.monitor._pressed_keys)

    def test_is_shift_pressed(self):
        # Mock keyboard keys
        shift_key = MagicMock()
        other_key = MagicMock()
        
        # We need to match the keys used in the class
        # Since we mocked pynput.keyboard, ModifierKeyMonitor._SHIFT_KEYS will contain mocks
        # We need to make sure we use one of those mocks
        target_shift = self.monitor._SHIFT_KEYS[0]
        
        self.assertFalse(self.monitor.is_shift_pressed())
        
        self.monitor._on_press(target_shift)
        self.assertTrue(self.monitor.is_shift_pressed())
        
        self.monitor._on_release(target_shift)
        self.assertFalse(self.monitor.is_shift_pressed())
        
        self.monitor._on_press(other_key)
        self.assertFalse(self.monitor.is_shift_pressed())

if __name__ == '__main__':
    unittest.main()
