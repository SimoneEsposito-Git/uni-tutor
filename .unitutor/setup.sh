#!/usr/bin/env bash
# Setup für macOS und Linux (Windows: setup.ps1)
set -euo pipefail

SYS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SYS_DIR")"
VENV_DIR="$SYS_DIR/.venv"
PY="$VENV_DIR/bin/python"

echo "==> Uni-Tutor & Sync Setup"
echo "    Projektordner: $ROOT_DIR"

# 1. Python 3 prüfen
if ! command -v python3 >/dev/null 2>&1; then
    echo "FEHLER: python3 wurde nicht gefunden. Bitte zuerst Python 3.10+ installieren (siehe .github/README.md)."
    exit 1
fi

# 2. Virtuelle Umgebung erstellen & Pakete installieren
if [ ! -d "$VENV_DIR" ]; then
    echo "==> Erstelle Python Virtual Environment in .unitutor/.venv ..."
    python3 -m venv "$VENV_DIR"
fi

echo "==> Installiere Python-Abhängigkeiten ..."
"$PY" -m pip install --upgrade pip -q
"$PY" -m pip install -r "$SYS_DIR/requirements.txt" -q

echo "==> Installiere Playwright Chromium Browser ..."
"$PY" -m playwright install chromium

# 3. config.yaml aus Vorlage erstellen, falls noch nicht vorhanden
if [ ! -f "$SYS_DIR/config.yaml" ]; then
    cp "$SYS_DIR/config.example.yaml" "$SYS_DIR/config.yaml"
    echo "==> .unitutor/config.yaml wurde aus der Vorlage erstellt. Bitte anpassen!"
else
    echo "==> .unitutor/config.yaml existiert bereits (wird nicht überschrieben)."
fi

# 4. Täglichen Sync vorbereiten
if [ "$(uname)" = "Darwin" ]; then
    sed "s|__ROOT_DIR__|$ROOT_DIR|g" "$SYS_DIR/com.unitutor.sync.plist.template" > "$SYS_DIR/com.unitutor.sync.plist"
    SCHEDULE="cp .unitutor/com.unitutor.sync.plist ~/Library/LaunchAgents/ && launchctl load ~/Library/LaunchAgents/com.unitutor.sync.plist"
else
    SCHEDULE="(crontab -l 2>/dev/null; echo '0 7 * * * \"$PY\" \"$SYS_DIR/moodle_sync.py\" >> \"$SYS_DIR/sync.log\" 2>&1') | crontab -"
fi

echo ""
echo "✅ Setup abgeschlossen! Nächste Schritte (Details in .github/README.md):"
echo "   1. Passe die Konfiguration an (Moodle-URL, Login, Kurs-IDs):"
echo "      open -e .unitutor/config.yaml    # Linux: xdg-open .unitutor/config.yaml"
echo "   2. Speichere dein Moodle-/SSO-Passwort im Passwort-Speicher des Systems:"
echo "      $PY .unitutor/keystore.py set password"
echo "   3. Führe den ersten interaktiven Login aus:"
echo "      $PY .unitutor/moodle_sync.py --login"
echo "   4. Optional: täglichen Sync um 07:00 aktivieren:"
echo "      $SCHEDULE"
