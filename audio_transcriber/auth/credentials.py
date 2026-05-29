"""Windows Credential Manager wrapper via keyring.

Keys stored under service name 'Audio_Transcriber'. On non-Windows
(dev on Mac), this still works via the OS keyring backend.
"""
import keyring

SERVICE = "Audio_Transcriber"


def get_secret(name: str) -> str | None:
    try:
        return keyring.get_password(SERVICE, name)
    except keyring.errors.KeyringError:
        return None


def set_secret(name: str, value: str) -> None:
    keyring.set_password(SERVICE, name, value)


def delete_secret(name: str) -> None:
    try:
        keyring.delete_password(SERVICE, name)
    except keyring.errors.PasswordDeleteError:
        pass
