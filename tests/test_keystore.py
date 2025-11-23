import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
import sys
import os
import subprocess
from unittest.mock import patch, MagicMock

# Mock pynput before importing application modules to avoid X server requirement in CI
sys.modules["pynput"] = MagicMock()
sys.modules["pynput.keyboard"] = MagicMock()

# Add the project root to sys.path so we can import keyzerchief_app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keyzerchief_app.keystore import (
    get_keystore_entries,
    parse_until_date,
    check_password,
    check_unsaved_changes,
    filter_entries,
    find_entry_index_by_alias
)
from keyzerchief_app.state import AppState, default_filter_state

class TestKeystoreParsing(unittest.TestCase):

    def setUp(self):
        self.state = AppState()
        self.state.keystore_path = "dummy.jks"
        self.state.keystore_password = "password"

    @patch('keyzerchief_app.keystore.subprocess.run')
    def test_get_keystore_entries_success(self, mock_run):
        # Sample output from keytool -list -v
        # Note: The parser skips the first 4 lines
        sample_output = """
Keystore type: PKCS12
Keystore provider: SUN

Your keystore contains 2 entries

Alias name: mykey
Creation date: Nov 23, 2023
Entry type: PrivateKeyEntry, 1
Certificate chain length: 1
Certificate[1]:
Owner: CN=Test, OU=Unit, O=Org, L=City, ST=State, C=US
Issuer: CN=Test, OU=Unit, O=Org, L=City, ST=State, C=US
Serial number: 12345678
Valid from: Thu Nov 23 10:00:00 UTC 2023 until: Fri Nov 22 10:00:00 UTC 2024
Certificate fingerprints:
\t SHA1: AA:BB:CC
\t SHA256: 11:22:33

Alias name: trustedcert
Creation date: Nov 23, 2023
Entry type: trustedCertEntry, 1
Owner: CN=CA, O=Org, C=US
Issuer: CN=CA, O=Org, C=US
Serial number: 87654321
Valid from: Thu Nov 23 10:00:00 UTC 2023 until: Sun Nov 23 10:00:00 UTC 2025
"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = sample_output
        mock_run.return_value = mock_result

        entries = get_keystore_entries(self.state)

        self.assertEqual(len(entries), 2)

        # Check first entry (PrivateKeyEntry)
        self.assertEqual(entries[0]['Alias name'], 'mykey')
        self.assertTrue(entries[0]['__is_key__'])
        self.assertFalse(entries[0]['__is_cert__'])
        self.assertEqual(entries[0]['Serial number'], '12345678')

        # Check second entry (trustedCertEntry)
        self.assertEqual(entries[1]['Alias name'], 'trustedcert')
        self.assertFalse(entries[1]['__is_key__'])
        self.assertTrue(entries[1]['__is_cert__'])
        self.assertEqual(entries[1]['Serial number'], '87654321')

    @patch('keyzerchief_app.keystore.subprocess.run')
    def test_get_keystore_entries_empty(self, mock_run):
        sample_output = """
Keystore type: PKCS12
Keystore provider: SUN

Your keystore contains 0 entries
"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = sample_output
        mock_run.return_value = mock_result

        entries = get_keystore_entries(self.state)
        self.assertEqual(len(entries), 0)

    def test_parse_until_date(self):
        # Test standard format
        valid_from = "Valid from: Thu Nov 23 10:00:00 UTC 2023 until: Fri Nov 22 10:00:00 UTC 2024"
        dt = parse_until_date(valid_from)
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2024)
        self.assertEqual(dt.month, 11)
        self.assertEqual(dt.day, 22)

        # Test with mapped timezone (e.g., CET -> +0100)
        valid_from_cet = "Valid from: Thu Nov 23 10:00:00 CET 2023 until: Fri Nov 22 10:00:00 CET 2024"
        dt_cet = parse_until_date(valid_from_cet)
        self.assertIsNotNone(dt_cet)
        # Verify timezone offset handling if possible, or just that it parses

        # Test invalid format
        self.assertIsNone(parse_until_date("Invalid string"))

    def test_filter_entries(self):
        entries = [
            {"Alias name": "alpha", "__is_key__": True, "__is_cert__": False, "__expired__": False},
            {"Alias name": "beta", "__is_key__": False, "__is_cert__": True, "__expired__": True},
            {"Alias name": "gamma", "__is_key__": True, "__is_cert__": False, "__expired__": False},
        ]

        # Test name filter (partial)
        filters = default_filter_state()
        filters["name"] = "al"
        filtered = filter_entries(entries, filters)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["Alias name"], "alpha")

        # Test name filter (exact)
        filters["name"] = "alpha"
        filters["partial_name"] = "No"
        filtered = filter_entries(entries, filters)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["Alias name"], "alpha")

        # Test name filter (exact mismatch)
        filters["name"] = "alp"
        filtered = filter_entries(entries, filters)
        self.assertEqual(len(filtered), 0)

        # Test expired filter
        filters = default_filter_state()
        filters["expired"] = "No"
        filtered = filter_entries(entries, filters)
        self.assertEqual(len(filtered), 2)
        self.assertNotIn("beta", [e["Alias name"] for e in filtered])

        # Test valid filter
        filters = default_filter_state()
        filters["valid"] = "No"
        filtered = filter_entries(entries, filters)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["Alias name"], "beta")

        # Test keys filter
        filters = default_filter_state()
        filters["keys"] = "No"
        filtered = filter_entries(entries, filters)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["Alias name"], "beta")

        # Test certificates filter
        filters = default_filter_state()
        filters["certificates"] = "No"
        filtered = filter_entries(entries, filters)
        self.assertEqual(len(filtered), 2)
        self.assertNotIn("beta", [e["Alias name"] for e in filtered])

    def test_find_entry_index_by_alias(self):
        entries = [
            {"Alias name": "one"},
            {"Alias name": "two"},
            {"Alias name": "three"},
        ]
        self.assertEqual(find_entry_index_by_alias(entries, "two"), 1)
        self.assertEqual(find_entry_index_by_alias(entries, "four"), 0) # Default to 0 if not found
        self.assertEqual(find_entry_index_by_alias(entries, None), 0)

    @patch('keyzerchief_app.keystore.subprocess.run')
    def test_check_password(self, mock_run):
        # Success case
        mock_run.return_value.returncode = 0
        self.assertTrue(check_password("dummy.jks", "correct"))

        # Failure case (CalledProcessError)
        mock_run.side_effect = subprocess.CalledProcessError(1, "cmd")
        self.assertFalse(check_password("dummy.jks", "wrong"))

        # Failure case (FileNotFoundError)
        mock_run.side_effect = FileNotFoundError
        self.assertFalse(check_password("dummy.jks", "wrong"))

    def test_check_unsaved_changes(self):
        # Setup mocks for file opening
        self.state.original_keystore_path = MagicMock()
        self.state.keystore_path = MagicMock()

        # Mock context managers
        mock_orig_file = MagicMock()
        mock_work_file = MagicMock()

        self.state.original_keystore_path.open.return_value.__enter__.return_value = mock_orig_file
        self.state.keystore_path.open.return_value.__enter__.return_value = mock_work_file

        # Case 1: Content identical
        mock_orig_file.read.return_value = b"content"
        mock_work_file.read.return_value = b"content"
        check_unsaved_changes(self.state)
        self.assertFalse(self.state.has_unsaved_changes)

        # Case 2: Content different
        mock_work_file.read.return_value = b"modified"
        check_unsaved_changes(self.state)
        self.assertTrue(self.state.has_unsaved_changes)

        # Case 3: FileNotFoundError
        self.state.original_keystore_path.open.side_effect = FileNotFoundError
        check_unsaved_changes(self.state)
        self.assertTrue(self.state.has_unsaved_changes)

if __name__ == '__main__':
    unittest.main()
