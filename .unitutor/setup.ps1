# Setup für Windows (macOS/Linux: setup.sh)
# Ausführen in PowerShell:  powershell -ExecutionPolicy Bypass -File .unitutor\setup.ps1 [-Schedule]
#   -Schedule  registriert zusätzlich den täglichen Sync um 07:00 in der Aufgabenplanung
param([switch]$Schedule)
$ErrorActionPreference = "Stop"

$SysDir = $PSScriptRoot
$RootDir = Split-Path $SysDir -Parent
$VenvDir = Join-Path $SysDir ".venv"
$Py = Join-Path $VenvDir "Scripts\python.exe"

Write-Host "==> Uni-Tutor & Sync Setup"
Write-Host "    Projektordner: $RootDir"

# 1. Python 3 prüfen (Python-Launcher "py" oder "python")
$SysPy = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } elseif (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { $null }
if (-not $SysPy) {
    Write-Host "FEHLER: Python wurde nicht gefunden. Bitte zuerst Python 3.10+ installieren (siehe .github\README.md)."
    exit 1
}

# 2. Virtuelle Umgebung erstellen & Pakete installieren
if (-not (Test-Path $VenvDir)) {
    Write-Host "==> Erstelle Python Virtual Environment in .unitutor\.venv ..."
    & $SysPy -m venv $VenvDir
}
Write-Host "==> Installiere Python-Abhängigkeiten ..."
& $Py -m pip install --upgrade pip -q
& $Py -m pip install -r (Join-Path $SysDir "requirements.txt") -q

Write-Host "==> Installiere Playwright Chromium Browser ..."
& $Py -m playwright install chromium

# 3. config.yaml aus Vorlage erstellen, falls noch nicht vorhanden
$Cfg = Join-Path $SysDir "config.yaml"
if (-not (Test-Path $Cfg)) {
    Copy-Item (Join-Path $SysDir "config.example.yaml") $Cfg
    Write-Host "==> .unitutor\config.yaml wurde aus der Vorlage erstellt. Bitte anpassen!"
} else {
    Write-Host "==> .unitutor\config.yaml existiert bereits (wird nicht überschrieben)."
}

# 4. Tutor-Dateien im Projektordner ausblenden (im Explorer sind Ordner mit Punkt sonst sichtbar)
foreach ($Name in ".unitutor", ".claude", ".agents", ".github", ".gitignore", ".gitattributes") {
    $Item = Join-Path $RootDir $Name
    if (Test-Path $Item) { $I = Get-Item $Item -Force; $I.Attributes = $I.Attributes -bor [IO.FileAttributes]::Hidden }
}

# 5. Optional: täglicher Sync (holt verpasste Läufe nach, z. B. wenn der PC um 07:00 aus war)
if ($Schedule) {
    $Sync = Join-Path $SysDir "moodle_sync.py"
    $Log = Join-Path $SysDir "sync.log"
    $Action = New-ScheduledTaskAction -Execute "cmd.exe" -WorkingDirectory $SysDir `
        -Argument "/c `"`"$Py`" `"$Sync`" >> `"$Log`" 2>&1`""
    $Trigger = New-ScheduledTaskTrigger -Daily -At 07:00
    $Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable
    Register-ScheduledTask -TaskName "uni-tutor-sync" -Action $Action -Trigger $Trigger -Settings $Settings -Force | Out-Null
    Write-Host "==> Aufgabe 'uni-tutor-sync' registriert (täglich 07:00, Log: .unitutor\sync.log)."
}

Write-Host ""
Write-Host "Setup abgeschlossen! Nächste Schritte (Details in .github\README.md):"
Write-Host "   1. Passe die Konfiguration an (Moodle-URL, Login, Kurs-IDs):"
Write-Host "      notepad .unitutor\config.yaml"
Write-Host "   2. Speichere dein Moodle-/SSO-Passwort in der Windows-Anmeldeinformationsverwaltung:"
Write-Host "      & `"$Py`" .unitutor\keystore.py set password"
Write-Host "   3. Führe den ersten interaktiven Login aus:"
Write-Host "      & `"$Py`" .unitutor\moodle_sync.py --login"
if (-not $Schedule) {
    Write-Host "   4. Optional: täglichen Sync um 07:00 aktivieren:"
    Write-Host "      powershell -ExecutionPolicy Bypass -File .unitutor\setup.ps1 -Schedule"
}
