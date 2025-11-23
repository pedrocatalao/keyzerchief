import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import subprocess
from pathlib import Path

# Mock pynput before importing application modules
sys.modules["pynput"] = MagicMock()
sys.modules["pynput.keyboard"] = MagicMock()

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keyzerchief_app.state import AppState
from keyzerchief_app.keystore_actions import (
    delete_entry, 
    rename_entry_alias,
    import_cert_file,
    generate_key_pair,
    import_pkcs12_keypair,
    import_pkcs8_keypair,
    change_keystore_password
)

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

    @patch('keyzerchief_app.keystore_actions.subprocess.run')
    @patch('keyzerchief_app.keystore_actions.popup_form')
    @patch('keyzerchief_app.keystore_actions.curses.newwin')
    def test_import_cert_file(self, mock_newwin, mock_popup_form, mock_run):
        # Mock popup form
        mock_popup_form.return_value = ({"file_path": "cert.crt"}, self.mock_stdscr)
        
        # Mock subprocess
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        # Mock wait
        self.mock_stdscr.getch.return_value = -1
        
        result = import_cert_file(self.mock_stdscr, self.state)
        
        self.assertEqual(result, "cert") # stem of cert.crt
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertIn("-importcert", args)
        self.assertIn("cert.crt", args)

    @patch('keyzerchief_app.keystore_actions.subprocess.run')
    @patch('keyzerchief_app.keystore_actions.popup_form')
    @patch('keyzerchief_app.keystore_actions.curses.newwin')
    def test_generate_key_pair(self, mock_newwin, mock_popup_form, mock_run):
        # Mock popup forms sequence:
        # 1. Algorithm selection
        # 2. Certificate details
        # 3. Distinguished Name
        
        mock_popup_form.side_effect = [
            ({"algorithm": "RSA", "key_size": "2048"}, self.mock_stdscr),
            ({"alias": "newkey", "version": "Version 3"}, self.mock_stdscr),
            ({"cn": "Test"}, self.mock_stdscr)
        ]
        
        # Mock subprocess
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        # Mock wait
        self.mock_stdscr.getch.return_value = -1
        
        result = generate_key_pair(self.mock_stdscr, self.state)
        
        self.assertEqual(result, "newkey")
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertIn("-genkeypair", args)
        self.assertIn("newkey", args)
    @patch('keyzerchief_app.keystore_actions.subprocess.run')
    @patch('keyzerchief_app.keystore_actions.popup_form')
    @patch('keyzerchief_app.keystore_actions.curses.newwin')
    def test_import_pkcs12_keypair(self, mock_newwin, mock_popup_form, mock_run):
        mock_popup_form.return_value = ({"key_pair_file": "key.p12", "decryption_password": "pass"}, self.mock_stdscr)
        
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        self.mock_stdscr.getch.return_value = -1
        
        result = import_pkcs12_keypair(self.mock_stdscr, self.state)
        
        self.assertEqual(result, "key")
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertIn("-importkeystore", args)
        self.assertIn("key.p12", args)

    @patch('keyzerchief_app.keystore_actions.subprocess.run')
    @patch('keyzerchief_app.keystore_actions.popup_form')
    @patch('keyzerchief_app.keystore_actions.curses.newwin')
    @patch('keyzerchief_app.keystore_actions.tempfile.NamedTemporaryFile')
    @patch('keyzerchief_app.keystore_actions.os.remove')
    @patch('keyzerchief_app.keystore_actions.os.path.exists')
    def test_import_pkcs8_keypair(self, mock_exists, mock_remove, mock_tempfile, mock_newwin, mock_popup_form, mock_run):
        mock_popup_form.return_value = ({
            "certificates_file": "cert.pem",
            "pkcs8_key_file": "key.pem",
            "decryption_password": "pass"
        }, self.mock_stdscr)
        
        # Mock tempfile
        mock_temp_obj = MagicMock()
        mock_temp_obj.name = "temp.p12"
        mock_tempfile.return_value.__enter__.return_value = mock_temp_obj
        
        # Mock subprocess calls (openssl then keytool)
        mock_openssl_result = MagicMock()
        mock_openssl_result.returncode = 0
        mock_keytool_result = MagicMock()
        mock_keytool_result.returncode = 0
        
        mock_run.side_effect = [mock_openssl_result, mock_keytool_result]
        
        self.mock_stdscr.getch.return_value = -1
        mock_exists.return_value = True
        
        result = import_pkcs8_keypair(self.mock_stdscr, self.state)
        
        self.assertEqual(result, "key")
        self.assertEqual(mock_run.call_count, 2)
        
        # Verify OpenSSL call
        openssl_args = mock_run.call_args_list[0][0][0]
        self.assertIn("openssl", openssl_args)
        self.assertIn("pkcs12", openssl_args)
        
        # Verify Keytool call
        keytool_args = mock_run.call_args_list[1][0][0]
        self.assertIn("keytool", keytool_args)
        self.assertIn("-importkeystore", keytool_args)

    @patch('keyzerchief_app.keystore_actions.subprocess.check_call')
    @patch('keyzerchief_app.keystore_actions.subprocess.check_output')
    @patch('keyzerchief_app.keystore_actions.popup_form')
    @patch('keyzerchief_app.keystore_actions.curses.newwin')
    @patch('keyzerchief_app.keystore_actions.curses.color_pair')
    def test_change_keystore_password(self, mock_color_pair, mock_newwin, mock_popup_form, mock_check_output, mock_check_call):
        mock_color_pair.return_value = 0
        # Success scenario
        mock_popup_form.return_value = ({
            "new_password": "newpass",
            "confirm_new_password": "newpass"
        }, self.mock_stdscr)
        
        # Mock listing aliases (must contain "entry" as per code logic)
        mock_check_output.return_value = "mykey, Nov 23, 2023, PrivateKeyEntry, entry\n"
        
        self.mock_stdscr.getch.return_value = -1
        
        change_keystore_password(self.mock_stdscr, self.state)
        
        # Verify storepasswd call
        mock_check_call.assert_any_call([
            "keytool", "-storepasswd", "-keystore", str(self.state.keystore_path),
            "-storepass", "password", "-new", "newpass"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Verify keypasswd call
        mock_check_call.assert_any_call([
            "keytool", "-keypasswd", "-keystore", str(self.state.keystore_path),
            "-alias", "mykey", "-storepass", "newpass",
            "-keypass", "password", "-new", "newpass"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        self.assertEqual(self.state.keystore_password, "newpass")

if __name__ == '__main__':
    unittest.main()
