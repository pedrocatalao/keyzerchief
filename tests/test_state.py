import unittest
from keyzerchief_app.state import AppState, default_filter_state

class TestAppState(unittest.TestCase):

    def test_initialization(self):
        state = AppState()
        self.assertIsNone(state.original_keystore_path)
        self.assertIsNone(state.keystore_path)
        self.assertEqual(state.keystore_password, "")
        self.assertTrue(state.reload_entries)
        self.assertFalse(state.has_unsaved_changes)
        self.assertTrue(state.mouse_enabled)
        self.assertIsNone(state.right_panel_highlight_term)
        self.assertEqual(state.filter_state, default_filter_state())

    def test_mark_dirty_clean(self):
        state = AppState()
        self.assertFalse(state.has_unsaved_changes)
        
        state.mark_dirty()
        self.assertTrue(state.has_unsaved_changes)
        
        state.mark_clean()
        self.assertFalse(state.has_unsaved_changes)

    def test_default_filter_state(self):
        filters = default_filter_state()
        expected = {
            "name": "",
            "partial_name": "Yes",
            "valid": "Yes",
            "expired": "Yes",
            "keys": "Yes",
            "certificates": "Yes",
        }
        self.assertEqual(filters, expected)

if __name__ == '__main__':
    unittest.main()
