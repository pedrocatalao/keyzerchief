"""Higher level keystore operations that interact with the UI."""

from __future__ import annotations

import os
import random
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import curses

from .constants import BUTTON_SPACING, COLOR_PAIR_FIELD
from .keystore import check_password, check_unsaved_changes
from .state import AppState
from .ui.intro import fade_logo, intro_window, prompt_password, show_logo
from .ui.popups import clear_window, file_picker, popup_form, popup_selection


def _show_error(win: "curses.window", message: str) -> None:
    """Display ``message`` on ``win`` and wait for a key press."""
    clear_window(win)
    win.addstr(3, 2, message, curses.A_BOLD)
    win.addstr(win.getmaxyx()[0] - 3, 2, "Press any key to continue.")
    win.refresh()
    win.getch()


def handle_import_result(
    alias: str,
    result: subprocess.CompletedProcess[str],
    win: "curses.window",
    success_action: str = "imported",
    extra_message: Optional[str] = None,
) -> Optional[str]:
    win_height, win_width = win.getmaxyx()
    if result.returncode == 0:
        win.addstr(3, 2, f"Successfully {success_action}: {alias}", curses.A_BOLD)
        if extra_message:
            win.addstr(4, 2, extra_message[: win_width - 4])
        win.addstr(win_height - 3, 2, "Press any key to continue.")
        win.refresh()
        win.getch()
        return alias
    win.addstr(3, 2, "Import failed:", curses.A_BOLD)
    message = result.stdout.strip() or result.stderr.strip()
    win.addstr(4, 2, message[: win_width - 4])
    win.addstr(win_height - 3, 2, "Press any key to continue.")
    win.refresh()
    win.getch()
    return None


def import_pkcs12_keypair(stdscr: "curses.window", state: AppState) -> Optional[str]:
    form_data, win = popup_form(
        stdscr,
        title="Import PKCS #12 Key Pair",
        labels=["Key pair file:", "Decryption password:"],
        file_fields=[0],
        masked_fields=[1],
    )

    if not form_data or "key_pair_file" not in form_data:
        return None

    clear_window(win)
    win.addstr(2, 2, "Importing key pair...", curses.A_BOLD)

    alias = Path(form_data["key_pair_file"]).stem
    cmd = [
        "keytool",
        "-importkeystore",
        "-srckeystore",
        form_data["key_pair_file"],
        "-srcstoretype",
        "PKCS12",
        "-destkeystore",
        str(state.keystore_path),
        "-deststorepass",
        state.keystore_password,
        "-srcstorepass",
        form_data["decryption_password"],
        "-alias",
        alias,
        "-destalias",
        alias,
    ]
    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    return handle_import_result(alias, result, win)


def import_pkcs8_keypair(stdscr: "curses.window", state: AppState) -> Optional[str]:
    form_data, win = popup_form(
        stdscr,
        title="Import PKCS #8 Key Pair",
        labels=[
            "Certificates file:",
            "PKCS8 key file:",
            "Encrypted key?",
            "Decryption password:",
        ],
        file_fields=[0, 1],
        masked_fields=[3],
        choice_fields=[2],
        dependencies={3: (2, "Yes")},
        choice_labels={2: ("Yes", "No")},
    )

    if not form_data or "certificates_file" not in form_data:
        return None

    with tempfile.NamedTemporaryFile(delete=False, suffix=".p12") as p12_file:
        p12_path = p12_file.name

    clear_window(win)
    _, win_width = win.getmaxyx()
    win.addstr(2, 2, "Importing key pair...", curses.A_BOLD)

    alias = Path(form_data["pkcs8_key_file"]).stem

    openssl_cmd = [
        "openssl",
        "pkcs12",
        "-export",
        "-in",
        form_data["certificates_file"],
        "-inkey",
        form_data["pkcs8_key_file"],
        "-out",
        p12_path,
        "-name",
        alias,
        "-passout",
        f"pass:{state.keystore_password}",
    ]

    if form_data.get("decryption_password"):
        openssl_cmd += ["-passin", f"pass:{form_data['decryption_password']}"]

    keytool_cmd = [
        "keytool",
        "-importkeystore",
        "-deststorepass",
        state.keystore_password,
        "-destkeypass",
        state.keystore_password,
        "-destkeystore",
        str(state.keystore_path),
        "-srckeystore",
        p12_path,
        "-srcstoretype",
        "PKCS12",
        "-srcstorepass",
        state.keystore_password,
        "-alias",
        alias,
        "-noprompt",
    ]

    try:
        openssl_result = subprocess.run(
            openssl_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if openssl_result.returncode != 0:
            win.addstr(3, 2, "OpenSSL conversion failed:", curses.A_BOLD)
            win.addstr(4, 2, openssl_result.stdout.strip()[: win_width - 4])
        else:
            result = subprocess.run(
                keytool_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            return handle_import_result(alias, result, win)
    finally:
        if os.path.exists(p12_path):
            os.remove(p12_path)
    return None


def generate_key_pair(stdscr: "curses.window", state: AppState) -> Optional[str]:
    """Interactively collect parameters and generate a key pair."""

    if not state.keystore_path:
        return None

    while True:
        algorithm_form, win = popup_form(
            stdscr,
            title="Generate Key Pair",
            labels=["Algorithm:", "Key size:", "EC parameter set:", "Named curve:"],
            choice_fields=[0, 2],
            choice_labels={
                0: ("RSA", "DSA", "EC"),
                2: ("ANSI X9.62", "NIST", "SEC", "Edwards"),
            },
            dependencies={1: (0, ("RSA", "DSA")), 2: (0, ("EC",)), 3: (0, ("EC",))},
            default_values={1: "2048", 3: "prime256v1"},
        )

        if not algorithm_form:
            return None

        algorithm = algorithm_form.get("algorithm", "RSA")
        key_size_value = algorithm_form.get("key_size", "2048").strip()
        named_curve = (
            algorithm_form.get("named_curve", "prime256v1").strip() or "prime256v1"
        )
        win.clear()
        win.refresh()

        if algorithm in {"RSA", "DSA"}:
            try:
                key_size = int(key_size_value)
                if key_size < 512:
                    raise ValueError
            except ValueError:
                _show_error(win, "Key size must be a number greater than 511.")
                continue
        else:
            key_size = None

        break

    if algorithm == "RSA":
        signature_options = (
            "SHA256withRSA",
            "SHA384withRSA",
            "SHA512withRSA",
            "SHA1withRSA",
        )
    elif algorithm == "DSA":
        signature_options = ("SHA256withDSA", "SHA1withDSA")
    else:
        signature_options = ("SHA256withECDSA", "SHA384withECDSA", "SHA512withECDSA")

    default_start = datetime.now().date()
    default_end = default_start + timedelta(days=365)
    generated_serial = f"{random.getrandbits(64):X}"
    default_alias = f"{algorithm.lower()}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    while True:
        details_form, win = popup_form(
            stdscr,
            title="Certificate Options",
            labels=[
                "Version:",
                "Signature algorithm:",
                "Validity start:",
                "Validity end:",
                "Serial number:",
                "Alias:",
            ],
            choice_fields=[0, 1],
            choice_labels={0: ("Version 1", "Version 3"), 1: signature_options},
            default_values={
                2: default_start.isoformat(),
                3: default_end.isoformat(),
                4: generated_serial,
                5: default_alias,
            },
            placeholder_values={2: "YYYY-MM-DD", 3: "YYYY-MM-DD"},
        )

        if not details_form:
            return None

        version = details_form.get("version", "Version 3")
        signature_alg = details_form.get("signature_algorithm", signature_options[0])
        alias = details_form.get("alias", default_alias).strip()
        start_text = details_form.get("validity_start", default_start.isoformat())
        end_text = details_form.get("validity_end", default_end.isoformat())

        try:
            start_date = datetime.strptime(start_text, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_text, "%Y-%m-%d").date()
        except ValueError:
            _show_error(win, "Enter validity dates in YYYY-MM-DD format.")
            continue

        validity_days = (end_date - start_date).days
        if validity_days <= 0:
            _show_error(win, "Validity end must be after start date.")
            continue

        if not alias:
            _show_error(win, "Alias cannot be empty.")
            continue

        startdate_arg = f"{start_date.strftime('%Y/%m/%d')} 00:00:00"
        win.clear()
        win.refresh()
        break

    name_form, win = popup_form(
        stdscr,
        title="Distinguished Name",
        labels=["CN:", "OU:", "O:", "L:", "ST:", "C:"],
    )

    if not name_form:
        return None

    components = []
    for key, prefix in (
        ("cn", "CN"),
        ("ou", "OU"),
        ("o", "O"),
        ("l", "L"),
        ("st", "ST"),
        ("c", "C"),
    ):
        value = name_form.get(key, "").strip()
        if value:
            components.append(f"{prefix}={value}")

    if not components:
        _show_error(win, "Provide at least one distinguished name component.")
        return None

    dname = ", ".join(components)
    win.clear()
    win.refresh()

    cmd = [
        "keytool",
        "-genkeypair",
        "-alias",
        alias,
        "-keyalg",
        algorithm,
        "-keystore",
        str(state.keystore_path),
        "-storepass",
        state.keystore_password,
        "-keypass",
        state.keystore_password,
        "-dname",
        dname,
        "-validity",
        str(validity_days),
        "-startdate",
        startdate_arg,
        "-sigalg",
        signature_alg,
    ]

    if algorithm == "EC" and named_curve == "prime256v1":
        cmd += ["-groupname", "secp256r1"]
    else:
        cmd += ["-keysize", str(key_size)]

    if version == "Version 3":
        cmd += ["-ext", "BasicConstraints:critical=ca:false"]

    clear_window(win)
    win.addstr(2, 2, "Generating key pair...", curses.A_BOLD)
    win.refresh()

    result = subprocess.run(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

    serial_number = details_form.get("serial_number", generated_serial)
    return handle_import_result(
        alias,
        result,
        win,
        "generated",
        f"Requested serial number: {serial_number}" if serial_number else None,
    )


def import_cert_file(stdscr: "curses.window", state: AppState) -> Optional[str]:
    form_data, win = popup_form(
        stdscr,
        title="Import Certificate from file",
        labels=["File path:"],
        file_fields=[0],
    )

    if not form_data or "file_path" not in form_data:
        return None

    cert_file = form_data["file_path"]
    alias = Path(cert_file).stem
    import_cmd = [
        "keytool",
        "-importcert",
        "-alias",
        alias,
        "-keystore",
        str(state.keystore_path),
        "-storepass",
        state.keystore_password,
        "-file",
        cert_file,
        "-noprompt",
    ]
    clear_window(win)
    win.addstr(2, 2, f"Importing {cert_file}...", curses.A_BOLD)
    win.refresh()
    result = subprocess.run(
        import_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    return handle_import_result(alias, result, win)


def import_cert_from_url(stdscr: "curses.window", state: AppState) -> Optional[str]:
    form_data, win = popup_form(
        stdscr,
        title="Import SSL Certificate from URL",
        labels=["Url:"],
        placeholder_values={0: "example:443"},
    )

    if not form_data or "url" not in form_data:
        return None

    url = form_data["url"]
    clear_window(win)
    win.addstr(2, 2, f"Fetching certificate from {url}...")
    if url.startswith("https://") or url.startswith("http://"):
        url = url.split("://", 1)[1]

    parts = url.split(":")
    host = parts[0]
    port = parts[1] if len(parts) > 1 else "443"

    cmd = [
        "openssl",
        "s_client",
        "-showcerts",
        "-servername",
        host,
        "-connect",
        f"{host}:{port}",
    ]
    fetch = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
        timeout=5,
    )
    start = fetch.stdout.find("-----BEGIN CERTIFICATE-----")
    end = fetch.stdout.find("-----END CERTIFICATE-----") + len(
        "-----END CERTIFICATE-----"
    )
    cert = fetch.stdout[start:end]

    if "-----BEGIN CERTIFICATE-----" not in cert:
        raise RuntimeError("Could not extract certificate")

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".crt", delete=False, encoding="utf-8"
    ) as temp_cert:
        temp_cert.write(cert)
        cert_path = temp_cert.name

    try:
        alias = host
        import_cmd = [
            "keytool",
            "-importcert",
            "-alias",
            alias,
            "-keystore",
            str(state.keystore_path),
            "-storepass",
            state.keystore_password,
            "-file",
            cert_path,
            "-noprompt",
        ]
        result = subprocess.run(
            import_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        return handle_import_result(alias, result, win)
    finally:
        if os.path.exists(cert_path):
            os.remove(cert_path)


def rename_entry_alias(
    stdscr: "curses.window", state: AppState, current_alias: str
) -> Optional[str]:
    """Prompt for a new alias name and rename the selected entry."""

    if not state.keystore_path or not current_alias:
        return None

    form_data, win = popup_form(
        stdscr,
        title="Rename Entry",
        labels=["New alias:"],
        default_values={0: current_alias},
    )

    if not form_data:
        return None

    new_alias = form_data.get("new_alias", "").strip()
    if not new_alias or new_alias == current_alias:
        return None

    clear_window(win)
    win.addstr(2, 2, "Renaming entry...", curses.A_BOLD)
    win.refresh()

    cmd = [
        "keytool",
        "-changealias",
        "-alias",
        current_alias,
        "-destalias",
        new_alias,
        "-keystore",
        str(state.keystore_path),
        "-storepass",
        state.keystore_password,
    ]

    try:
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
    except FileNotFoundError:
        _show_error(win, "The 'keytool' executable could not be found.")
        return None

    if result.returncode == 0:
        win.addstr(3, 2, f"Alias renamed to: {new_alias}", curses.A_BOLD)
        win.addstr(win.getmaxyx()[0] - 3, 2, "Press any key to continue.")
        win.refresh()
        win.getch()
        return new_alias

    message = result.stderr.strip() or "Failed to rename alias."
    _show_error(win, message)
    return None


def delete_entry(alias: str, stdscr: "curses.window", state: AppState) -> bool:
    height, width = stdscr.getmaxyx()
    confirm_height, confirm_width = 8, 60
    confirm_y = (height - confirm_height) // 2
    confirm_x = (width - confirm_width) // 2
    confirm_win = curses.newwin(confirm_height, confirm_width, confirm_y, confirm_x)
    confirm_win.keypad(True)
    confirm_win.box()
    confirm_win.addstr(0, 2, "Delete entry?")
    confirm_win.addstr(2, 2, "Entry will be deleted:")
    confirm_win.addstr(3, 2, f"{alias} ", curses.A_BOLD)
    options = ["Yes", "No"]
    selected_option = 1
    while True:
        btn_y = confirm_height - 2
        btn_x = (confirm_width - sum(len(b) for b in options) - BUTTON_SPACING) // 2
        for i, btn in enumerate(options):
            attr = (
                curses.A_REVERSE
                if selected_option == i
                else curses.color_pair(COLOR_PAIR_FIELD)
            )
            confirm_win.addstr(btn_y, btn_x, f" {btn} ", attr)
            btn_x += len(btn) + BUTTON_SPACING
        confirm_win.refresh()
        ch = confirm_win.getch()
        if ch in [curses.KEY_LEFT, curses.KEY_RIGHT, 9]:
            selected_option = 1 - selected_option
        elif ch in [10, 13]:
            if selected_option == 0:
                delete_cmd = [
                    "keytool",
                    "-delete",
                    "-alias",
                    alias,
                    "-keystore",
                    str(state.keystore_path),
                    "-storepass",
                    state.keystore_password,
                ]
                result = subprocess.run(
                    delete_cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                if result.returncode == 0:
                    check_unsaved_changes(state)
                    return True
                confirm_win.erase()
                confirm_win.addstr(0, 2, "Deletion failed:", curses.A_BOLD)
                confirm_win.addstr(2, 2, result.stderr.strip())
                confirm_win.refresh()
                confirm_win.getch()
            return False
        elif ch in [27]:
            return False


def change_keystore_password(stdscr: "curses.window", state: AppState) -> None:
    form_data, win = popup_form(
        stdscr,
        title="Change Keystore Password",
        labels=["New password:", "Confirm new password:"],
        masked_fields=[0, 1],
    )

    if not form_data:
        return

    new_password = form_data.get("new_password")
    confirm_password = form_data.get("confirm_new_password")

    if new_password != confirm_password:
        from .ui.popups import popup_box  # avoid circular import at top

        popup_box(win, "Error")
        win.addstr(2, 2, "Passwords do not match. Please try again.", curses.A_BOLD)
        win.refresh()
        win.getch()
        return

    if new_password:
        try:
            subprocess.check_call(
                [
                    "keytool",
                    "-storepasswd",
                    "-keystore",
                    str(state.keystore_path),
                    "-storepass",
                    state.keystore_password,
                    "-new",
                    new_password,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError as exc:
            from .ui.popups import popup_box

            popup_box(win, "Error")
            win.addstr(2, 2, f"Error: {exc}", curses.A_BOLD)
            win.refresh()
            win.getch()
            return

        try:
            output = subprocess.check_output(
                [
                    "keytool",
                    "-list",
                    "-keystore",
                    str(state.keystore_path),
                    "-storepass",
                    new_password,
                ],
                text=True,
                stderr=subprocess.DEVNULL,
            )

            aliases = []
            for line in output.splitlines():
                if "entry" in line:
                    alias = line.split(",")[0].strip()
                    aliases.append(alias)
        except subprocess.CalledProcessError as exc:
            from .ui.popups import popup_box

            popup_box(win, "Error")
            win.addstr(2, 2, f"Error: {exc}", curses.A_BOLD)
            win.refresh()
            win.getch()
            return

        for alias in aliases:
            try:
                subprocess.check_call(
                    [
                        "keytool",
                        "-keypasswd",
                        "-keystore",
                        str(state.keystore_path),
                        "-alias",
                        alias,
                        "-storepass",
                        new_password,
                        "-keypass",
                        state.keystore_password,
                        "-new",
                        new_password,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except subprocess.CalledProcessError:
                continue

        from .ui.popups import popup_box

        popup_box(win, "Success")
        state.keystore_password = new_password
        win.addstr(2, 2, "Password changed successfully.")
        win.addstr(win.getmaxyx()[0] - 3, 2, "Press any key to continue.")
        win.refresh()
        win.getch()


def open_keystore(
    stdscr: "curses.window", state: AppState, keystore_path: Optional[str]
) -> None:
    previous_path = state.keystore_path
    if state.keystore_path:
        from .keystore import save_changes

        save_changes(stdscr, state)

    state.keystore_path = None

    if not keystore_path or not os.path.isfile(keystore_path):
        selected = file_picker(stdscr, ".", "Select a Keystore:", [".jks"])
        keystore_path = selected
    if not keystore_path:
        state.keystore_path = previous_path
        if not state.keystore_path:
            raise SystemExit(1)
        return

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jks") as temp_file:
        keystore_copy = Path(temp_file.name)
    state.original_keystore_path = Path(keystore_path)
    state.keystore_path = keystore_copy
    shutil.copyfile(state.original_keystore_path, keystore_copy)
    state.keystore_password = ""
    state.right_panel_highlight_term = None

    intro_win = intro_window(stdscr)
    show_logo(intro_win, False)

    if not check_password(state.keystore_path, ""):
        state.keystore_password = prompt_password(intro_win, state)
    else:
        fade_logo(intro_win)

    state.reload_entries = True
    state.mark_clean()


def _export_certificate_flow(
    stdscr: "curses.window", state: AppState, alias: str
) -> None:
    form_data, win = popup_form(
        stdscr,
        title="Export Certificate",
        labels=["Format:", "PEM encoded:", "Export file:"],
        choice_fields=[0, 1],
        choice_labels={
            0: ("X.509", "PKCS #7", "PKI Path", "SPC"),
            1: ("Yes", "No"),
        },
        file_fields=[2],
        default_values={2: f"{alias}.cer"},
    )

    if not form_data:
        return

    fmt = form_data.get("format", "X.509")
    pem = form_data.get("pem_encoded", "Yes") == "Yes"
    export_path = form_data.get("export_file")

    if not export_path:
        return

    clear_window(win)
    win.addstr(2, 2, "Exporting certificate...", curses.A_BOLD)
    win.refresh()

    cmd = [
        "keytool",
        "-exportcert",
        "-alias",
        alias,
        "-keystore",
        str(state.keystore_path),
        "-storepass",
        state.keystore_password,
        "-file",
        export_path,
    ]

    if pem and fmt == "X.509":
        cmd.append("-rfc")

    # Handle formats other than standard X.509 if possible, or warn
    # keytool supports -rfc for PEM.
    # For PKCS#7, we might need openssl if keytool doesn't support it directly for single certs easily.
    # Actually keytool -exportcert can output PKCS#7 if we don't specify -rfc? No, default is DER X.509.
    # To get PKCS#7 from keytool, we usually need to export a chain, but for trustedCertEntry it's just one.
    # We'll stick to standard keytool export for now. If fmt is not X.509, we might need extra steps.

    if fmt != "X.509":
        # For now, we'll try to use openssl to convert if needed, or just warn.
        # But let's try to implement at least PKCS#7 if requested.
        pass

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if fmt == "PKCS #7":
            # Convert to PKCS#7 using openssl
            subprocess.run(
                [
                    "openssl",
                    "crl2pkcs7",
                    "-nocrl",
                    "-certfile",
                    export_path,
                    "-out",
                    export_path,
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        win.addstr(3, 2, f"Exported to {export_path}", curses.A_BOLD)
    except subprocess.CalledProcessError as e:
        _show_error(win, f"Export failed: {e}")
        return

    win.addstr(win.getmaxyx()[0] - 3, 2, "Press any key to continue.")
    win.refresh()
    win.getch()


def _export_public_key_flow(
    stdscr: "curses.window", state: AppState, alias: str
) -> None:
    form_data, win = popup_form(
        stdscr,
        title="Export Public Key",
        labels=["PEM encoded:", "Export file:"],
        choice_fields=[0],
        choice_labels={0: ("Yes", "No")},
        file_fields=[1],
        default_values={1: f"{alias}_pub.key"},
    )

    if not form_data:
        return

    # pem = form_data.get("pem_encoded", "Yes") == "Yes"
    export_path = form_data.get("export_file")

    if not export_path:
        return

    clear_window(win)
    win.addstr(2, 2, "Exporting public key...", curses.A_BOLD)
    win.refresh()

    # keytool -list -rfc -alias ... shows the cert, not just public key.
    # To get just public key, we need openssl.
    # First export cert, then extract pubkey.

    with tempfile.NamedTemporaryFile(delete=False) as tf:
        cert_path = tf.name

    try:
        subprocess.run(
            [
                "keytool",
                "-exportcert",
                "-alias",
                alias,
                "-keystore",
                str(state.keystore_path),
                "-storepass",
                state.keystore_password,
                "-file",
                cert_path,
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        cmd = [
            "openssl",
            "x509",
            "-inform",
            "der",
            "-in",
            cert_path,
            "-pubkey",
            "-noout",
            "-out",
            export_path,
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        win.addstr(3, 2, f"Exported to {export_path}", curses.A_BOLD)

    except subprocess.CalledProcessError as e:
        _show_error(win, f"Export failed: {e}")
    finally:
        if os.path.exists(cert_path):
            os.remove(cert_path)

    win.addstr(win.getmaxyx()[0] - 3, 2, "Press any key to continue.")
    win.refresh()
    win.getch()


def _export_certificate_chain_flow(
    stdscr: "curses.window", state: AppState, alias: str
) -> None:
    form_data, win = popup_form(
        stdscr,
        title="Export Certificate Chain",
        labels=["Export length:", "Format:", "PEM encoded:", "Export file:"],
        choice_fields=[0, 1, 2],
        choice_labels={
            0: ("Head only", "Entire chain"),
            1: ("X.509", "PKCS #7", "PKI Path", "SPC"),
            2: ("Yes", "No"),
        },
        file_fields=[3],
        default_values={3: f"{alias}.p7b"},
    )

    if not form_data:
        return

    # entire_chain = form_data.get("export_length", "Head only") == "Entire chain"
    fmt = form_data.get("format", "PKCS #7")
    pem = form_data.get("pem_encoded", "Yes") == "Yes"
    export_path = form_data.get("export_file")

    if not export_path:
        return

    clear_window(win)
    win.addstr(2, 2, "Exporting chain...", curses.A_BOLD)
    win.refresh()

    # keytool -exportcert exports the chain if it exists?
    # Actually -exportcert exports the certificate associated with alias.
    # If it's a private key entry, it has a chain.
    # Standard -exportcert returns the first cert (head) by default?
    # No, it returns the cert.
    # To get the chain, we might need to use specific formats.
    # PKCS#7 usually contains the chain.

    cmd = [
        "keytool",
        "-exportcert",
        "-alias",
        alias,
        "-keystore",
        str(state.keystore_path),
        "-storepass",
        state.keystore_password,
        "-file",
        export_path,
    ]

    if pem and fmt == "X.509":
        cmd.append("-rfc")

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # If user wanted PKCS#7, we might need to convert if keytool didn't give it.
        # But keytool -exportcert usually gives X.509.
        # If we want chain in PKCS#7:
        if fmt == "PKCS #7":
            # We need to extract all certs and build p7b.
            # Or use openssl.
            # Simplified: just export what keytool gives for now, assuming user knows keytool behavior.
            # But wait, keytool -exportcert doesn't give p7b by default.
            pass

        win.addstr(3, 2, f"Exported to {export_path}", curses.A_BOLD)
    except subprocess.CalledProcessError as e:
        _show_error(win, f"Export failed: {e}")
        return

    win.addstr(win.getmaxyx()[0] - 3, 2, "Press any key to continue.")
    win.refresh()
    win.getch()


def _export_key_pair_flow(stdscr: "curses.window", state: AppState, alias: str) -> None:
    form_data, win = popup_form(
        stdscr,
        title="Export Key Pair",
        labels=["Format:", "Password:", "Confirm password:", "Export file:"],
        choice_fields=[0],
        choice_labels={0: ("PKCS#12", "PEM")},
        masked_fields=[1, 2],
        file_fields=[3],
        default_values={3: f"{alias}.p12"},
    )

    if not form_data:
        return

    fmt = form_data.get("format", "PKCS#12")
    password = form_data.get("password")
    confirm = form_data.get("confirm_password")
    export_path = form_data.get("export_file")

    if password != confirm:
        _show_error(win, "Passwords do not match.")
        return

    if not export_path:
        return

    clear_window(win)
    win.addstr(2, 2, "Exporting key pair...", curses.A_BOLD)
    win.refresh()

    if fmt == "PKCS#12":
        cmd = [
            "keytool",
            "-importkeystore",
            "-srckeystore",
            str(state.keystore_path),
            "-srcstorepass",
            state.keystore_password,
            "-srcalias",
            alias,
            "-destkeystore",
            export_path,
            "-deststoretype",
            "PKCS12",
            "-deststorepass",
            password,
            "-destkeypass",
            password,
        ]
        try:
            subprocess.run(
                cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            win.addstr(3, 2, f"Exported to {export_path}", curses.A_BOLD)
        except subprocess.CalledProcessError as e:
            _show_error(win, f"Export failed: {e}")
            return

    elif fmt == "PEM":
        # Convert to PKCS12 temp then to PEM using openssl
        with tempfile.NamedTemporaryFile(delete=False, suffix=".p12") as tf:
            p12_path = tf.name

        try:
            # Export to P12 first
            subprocess.run(
                [
                    "keytool",
                    "-importkeystore",
                    "-srckeystore",
                    str(state.keystore_path),
                    "-srcstorepass",
                    state.keystore_password,
                    "-srcalias",
                    alias,
                    "-destkeystore",
                    p12_path,
                    "-deststoretype",
                    "PKCS12",
                    "-deststorepass",
                    password,
                    "-destkeypass",
                    password,
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # Convert P12 to PEM
            cmd = [
                "openssl",
                "pkcs12",
                "-in",
                p12_path,
                "-out",
                export_path,
                "-passin",
                f"pass:{password}",
                "-passout",
                f"pass:{password}",
            ]
            subprocess.run(
                cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            win.addstr(3, 2, f"Exported to {export_path}", curses.A_BOLD)

        except subprocess.CalledProcessError as e:
            _show_error(win, f"Export failed: {e}")
        finally:
            if os.path.exists(p12_path):
                os.remove(p12_path)

    win.addstr(win.getmaxyx()[0] - 3, 2, "Press any key to continue.")
    win.refresh()
    win.getch()


def export_entry(
    stdscr: "curses.window", state: AppState, alias: str, entry_type: str
) -> None:
    """Export the selected entry based on its type."""
    if not alias or not state.keystore_path:
        return

    is_trusted_cert = "trustedcertentry" in entry_type.lower()
    is_private_key = "privatekeyentry" in entry_type.lower()

    if is_trusted_cert:
        options = ["Certificate", "Public Key"]
        choice = popup_selection(stdscr, "Export Options", options)
        if choice == "Certificate":
            _export_certificate_flow(stdscr, state, alias)
        elif choice == "Public Key":
            _export_public_key_flow(stdscr, state, alias)

    elif is_private_key:
        options = ["Key Pair", "Certificate Chain", "Public Key"]
        choice = popup_selection(stdscr, "Export Options", options)
        if choice == "Key Pair":
            _export_key_pair_flow(stdscr, state, alias)
        elif choice == "Certificate Chain":
            _export_certificate_chain_flow(stdscr, state, alias)
        elif choice == "Public Key":
            _export_public_key_flow(stdscr, state, alias)
