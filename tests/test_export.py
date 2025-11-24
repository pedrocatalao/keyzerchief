import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
from keyzerchief_app.state import AppState
from keyzerchief_app.keystore_actions import export_entry


class TestExport(unittest.TestCase):
    def setUp(self):
        self.stdscr = MagicMock()
        self.stdscr.getmaxyx.return_value = (24, 80)
        self.state = AppState()
        self.state.keystore_path = Path("/tmp/test.jks")
        self.state.keystore_password = "pass"

    @patch("keyzerchief_app.keystore_actions.popup_selection")
    @patch("keyzerchief_app.keystore_actions.popup_form")
    @patch("subprocess.run")
    def test_export_trusted_cert(self, mock_run, mock_form, mock_selection):
        # Setup
        mock_selection.return_value = "Certificate"
        mock_win = MagicMock()
        mock_win.getmaxyx.return_value = (24, 80)
        mock_form.return_value = (
            {"format": "X.509", "pem_encoded": "Yes", "export_file": "out.cer"},
            mock_win,
        )

        # Execute
        export_entry(self.stdscr, self.state, "myalias", "trustedCertEntry")

        # Verify
        mock_selection.assert_called_with(
            self.stdscr, "Export Options", ["Certificate", "Public Key"]
        )
        mock_form.assert_called()

        # Check keytool command
        args, _ = mock_run.call_args
        cmd = args[0]
        self.assertEqual(cmd[0], "keytool")
        self.assertEqual(cmd[1], "-exportcert")
        self.assertIn("-rfc", cmd)  # PEM enabled
        self.assertIn("out.cer", cmd)

    @patch("keyzerchief_app.keystore_actions.popup_selection")
    @patch("keyzerchief_app.keystore_actions.popup_form")
    @patch("subprocess.run")
    def test_export_public_key(self, mock_run, mock_form, mock_selection):
        # Setup
        mock_selection.return_value = "Public Key"
        mock_win = MagicMock()
        mock_win.getmaxyx.return_value = (24, 80)
        mock_form.return_value = (
            {"pem_encoded": "Yes", "export_file": "out.key"},
            mock_win,
        )

        # Execute
        export_entry(self.stdscr, self.state, "myalias", "trustedCertEntry")

        # Verify
        mock_selection.assert_called()

        # Should call keytool then openssl
        self.assertTrue(mock_run.call_count >= 2)

        # Check last call (openssl)
        args, _ = mock_run.call_args
        cmd = args[0]
        self.assertEqual(cmd[0], "openssl")
        self.assertEqual(cmd[1], "x509")
        self.assertIn("-pubkey", cmd)

    @patch("keyzerchief_app.keystore_actions.popup_selection")
    @patch("keyzerchief_app.keystore_actions.popup_form")
    @patch("subprocess.run")
    def test_export_key_pair_pkcs12(self, mock_run, mock_form, mock_selection):
        # Setup
        mock_selection.return_value = "Key Pair"
        mock_win = MagicMock()
        mock_win.getmaxyx.return_value = (24, 80)
        mock_form.return_value = (
            {
                "format": "PKCS#12",
                "current_key_password": "keypass",
                "export_password": "newpass",
                "confirm_export_password": "newpass",
                "export_file": "out.p12",
            },
            mock_win,
        )

        # Execute
        export_entry(self.stdscr, self.state, "mykey", "PrivateKeyEntry")

        # Verify
        mock_selection.assert_called_with(
            self.stdscr,
            "Export Options",
            ["Key Pair", "Certificate Chain", "Public Key"],
        )

        # Check keytool commands
        # First call should be verification (-list)
        # Second call should be export (-importkeystore)
        self.assertTrue(mock_run.call_count >= 2)

        # Verify the export command (last call)
        args, _ = mock_run.call_args
        cmd = args[0]
        self.assertEqual(cmd[0], "keytool")
        self.assertEqual(cmd[1], "-importkeystore")
        self.assertIn("-deststoretype", cmd)
        self.assertIn("PKCS12", cmd)


if __name__ == "__main__":
    unittest.main()
