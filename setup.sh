#!/usr/bin/env bash
set -euo pipefail

MASTER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SYS_DIR="$MASTER_DIR/_system"
VENV_DIR="$SYS_DIR/.venv"

echo "==> Master-Tutor & Sync Setup"
echo "    Projektordner: $MASTER_DIR"

# 1. Python 3 prüfen
if ! command -v python3 >/dev/null 2>&1; then
    echo "FEHLER: python3 wurde nicht gefunden. Bitte zuerst Python 3 installieren (siehe README.md)."
    exit 1
fi

# 2. Virtuelle Umgebung erstellen & Pakete installieren
if [ ! -d "$VENV_DIR" ]; then
    echo "==> Erstelle Python Virtual Environment in _system/.venv ..."
    python3 -m venv "$VENV_DIR"
fi

echo "==> Installiere Python-Abhängigkeiten ..."
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install -r "$SYS_DIR/requirements.txt" -q

echo "==> Installiere Playwright Chromium Browser ..."
"$VENV_DIR/bin/playwright" install chromium

# 3. config.yaml aus Vorlage erstellen, falls noch nicht vorhanden
if [ ! -f "$SYS_DIR/config.yaml" ]; then
    cp "$SYS_DIR/config.example.yaml" "$SYS_DIR/config.yaml"
    echo "==> _system/config.yaml wurde aus der Vorlage erstellt. Bitte anpassen!"
else
    echo "==> _system/config.yaml existiert bereits (wird nicht überschrieben)."
fi

# 4. LaunchAgent plist mit aktuellem Pfad generieren
if [ -f "$SYS_DIR/com.master.sync.plist.template" ]; then
    sed "s|__MASTER_DIR__|$MASTER_DIR|g" "$SYS_DIR/com.master.sync.plist.template" > "$SYS_DIR/com.master.sync.plist"
    echo "==> _system/com.master.sync.plist für deinen Pfad generiert."
fi

echo ""
echo "✅ Setup abgeschlossen! Nächste Schritte (Details in README.md):"
echo "   1. Passe '_system/config.yaml' an (Username & Kurs-IDs)."
echo "   2. Speichere dein ISIS-Passwort im macOS-Schlüsselbund:"
echo "      security add-generic-password -a \"\$USER\" -s isis-sync -w"
echo "   3. Führe den ersten interaktiven Login aus:"
echo "      $VENV_DIR/bin/python $SYS_DIR/isis_sync.py --login"
