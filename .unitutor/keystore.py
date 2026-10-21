#!/usr/bin/env python3
"""Secrets in the OS credential store, never in files.

macOS: login keychain (via `security`), Windows/Linux: Credential Manager / Secret Service (via `keyring`).
Entry names come from `secrets:` in config.yaml (see config.example.yaml).
  python keystore.py set password   # store/replace an entry, asks for the value (hidden)
  python keystore.py check          # show which entries exist
"""
import getpass, subprocess, sys

from sync import CFG

NAMES = {"password": "moodle-password", "ics": "moodle-ics", "todoist": "todoist-token"} | (CFG.get("secrets") or {})
ACCOUNT = "uni-tutor"


def get(key: str) -> str | None:
    service = NAMES[key]
    if sys.platform == "darwin":
        r = subprocess.run(["security", "find-generic-password", "-s", service, "-w"], capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else None
    import keyring
    return keyring.get_password(service, ACCOUNT)


def require(key: str) -> str:
    if (value := get(key)) is None:
        sys.exit(f"No stored secret '{NAMES[key]}'. Run: python .unitutor/keystore.py set {key}")
    return value


def set_(key: str):
    service = NAMES[key]
    if sys.platform == "darwin":  # `security` prompts for the value itself, so it never shows up in argv
        subprocess.run(["security", "add-generic-password", "-U", "-a", ACCOUNT, "-s", service, "-w"], check=True)
    else:
        import keyring
        keyring.set_password(service, ACCOUNT, getpass.getpass(f"Value for {service}: "))
    print(f"Stored '{service}'.")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "set" and sys.argv[2] in NAMES:
        set_(sys.argv[2])
    elif sys.argv[1:] == ["check"]:
        for k, service in NAMES.items():
            print(f"{k:9} {service:20} {'stored' if get(k) is not None else 'missing'}")
    else:
        sys.exit(f"Usage: keystore.py set {{{'|'.join(NAMES)}}}  |  keystore.py check")
