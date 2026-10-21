# KI-Tutor & Automatischer Kurs-Sync (Claude Code & Google Antigravity)

Dieses Projekt verwandelt deinen Studienordner in ein automatisiertes Lernsystem:
1. **Automatischer Kurs-Sync (`_system/`)**: Lädt täglich neue Vorlesungsfolien, Übungsblätter und Infos aus Moodle/ISIS herunter, sortiert sie automatisch in die richtige Ordnerstruktur, schützt Originaldateien vor versehentlichem Überschreiben (`chmod 444`) und wandelt PDFs direkt in kompakte Markdown-Dateien (`.tutor/md/`) um, damit KI-Modelle sie extrem token-sparend lesen können. Optional werden Abgabefristen direkt nach **Todoist** synchronisiert.
2. **Sokratischer KI-Tutor & Aufgabengenerator**: Vorkonfigurierte Regeln ([AGENTS.md](file:///AGENTS.md)) und Slash-Befehle (`/tutor`, `/repeat`, `/anki`, `/make-exercises`, `/sync`) für **Google Antigravity**, **Claude Code** und **Gemini CLI**. Der Tutor verrät niemals direkt die Lösung, sondern führt dich mit gestuften Hinweisen und exakten Folien-Zitaten durch die Aufgaben und merkt sich deinen Lernstand in `.tutor/progress.md`.

---

## 1. Ordnerstruktur

```text
Master/
├── AGENTS.md                 # Zentrale Tutor-Regeln (für alle KI-Tools)
├── CLAUDE.md                 # Verweis auf AGENTS.md für Claude Code
├── GEMINI.md                 # Verweis auf AGENTS.md für Antigravity & Gemini CLI
├── setup.sh                  # Einmaliges Setup-Skript (Python-Umgebung, Playwright, Config)
├── _prompts/                 # Gemeinsame Prompt-Vorlagen für die Slash-Befehle
│   ├── tutor.md              # Ablauf für /tutor
│   ├── anki.md               # Ablauf für /anki (Anki-Deck aus Vorlesung/Kapitel)
│   ├── repeat.md             # Ablauf für /repeat (fällige Wiederholungen, kursübergreifend)
│   ├── make-exercises.md     # Ablauf für /make-exercises
│   └── sync.md               # Ablauf für /sync (manueller Sync + Änderungs-Zusammenfassung)
├── .agents/skills/           # Skills für Google Antigravity (/tutor, /repeat, /anki, /make-exercises, /sync)
├── .claude/skills/           # Skills für Claude Code (/tutor, /repeat, /anki, /make-exercises, /sync)
├── .gemini/commands/         # Custom Commands für Gemini CLI (/tutor, /repeat, /anki, /make-exercises, /sync)
├── _system/                  # Synchronisations-Skripte
│   ├── config.example.yaml   # Vorlage für deine Kurs-Konfiguration
│   ├── isis_sync.py          # Browser-Sync via Playwright (Shibboleth / TU-Login)
│   ├── sync.py               # Alternativer Moodle-Sync via REST-Token + PDF->Markdown
│   ├── todoist_sync.py       # Optional: Moodle-Kalender-Deadlines -> Todoist
│   └── requirements.txt      # Python-Abhängigkeiten
└── Semester 1/               # Wird automatisch vom Sync pro Kurs angelegt (in .gitignore)
    └── <Kursname>/
        ├── lectures/         # Vorlesungsfolien (schreibgeschützt)
        ├── exercises/        # Übungsblätter (schreibgeschützt)
        ├── info/             # Organisatorisches (schreibgeschützt)
        ├── solutions/        # Eigene Lösungen / Musterlösungen (KI darf lesen, nie ändern)
        ├── generated/        # Von /make-exercises generierte Übungsblätter & Lösungen
        └── .tutor/           # Arbeitsverzeichnis der KI
            ├── md/           # Automatisch aus PDFs extrahierter Text (.md)
            ├── index.md      # Kurzindex (1 Zeile pro Vorlesung/Blatt, falls angelegt)
            ├── progress.md   # Dein Lernfortschritt (repeat → ok → good → strong → solid, Spaced Repetition)
            └── style_guide.md# Automatisch analysierter Stil der Übungsblätter
```

---

## 2. Voraussetzungen installieren (falls noch nichts installiert ist)

Öffne das **Terminal** (`Cmd + Leertaste` → `Terminal` eingeben) auf deinem Mac.

### Schritt 2.1: Xcode Command Line Tools & Homebrew
Falls du noch kein `git` oder `brew` installiert hast, führe folgenden Befehl aus:

```bash
xcode-select --install
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```
*(Folge den Anweisungen im Terminal, um Homebrew am Ende zu deinem `PATH` hinzuzufügen).*

### Schritt 2.2: Python 3, Node.js und Git installieren
Python wird für die Sync-Skripte benötigt, Node.js für CLI-Tools wie Claude Code / Gemini CLI:

```bash
brew install python node git
```

---

## 3. KI-Tools installieren (Antigravity & Claude Code)

Du kannst das Projekt wahlweise mit **Google Antigravity**, **Claude Code** oder **Gemini CLI** (oder allen parallel) nutzen. Alle greifen auf dieselben Regeln ([AGENTS.md](file:///AGENTS.md)) und denselben Lernstand (`.tutor/progress.md`) zu.

### Option A: Google Antigravity (IDE & Agent)
1. **Herunterladen & Installieren**:
   - Lade **Google Antigravity** von [https://antigravity.google/download](https://antigravity.google/download) herunter (oder via Homebrew: `brew install --cask antigravity`).
   - Ziehe `Antigravity.app` in deinen `Programme`-Ordner (`Applications`) und starte die App.
2. **Einrichten**:
   - Melde dich beim ersten Start mit deinem Google-Account an.
   - Optional im Onboarding: Installiere das Kommandozeilen-Tool `agy` ("Install `agy` in PATH"), damit du das Projekt jederzeit aus dem Terminal mit `agy .` öffnen kannst.
3. **Projekt öffnen**:
   - Klicke auf **Open Folder** und wähle diesen `Master`-Ordner aus.
   - Antigravity lädt automatisch die Regeln aus `GEMINI.md` / `AGENTS.md` sowie die Skills aus `.agents/skills/` (`tutor` und `make-exercises`).

### Option B: Claude Code (Anthropic CLI / IDE-Integration)
1. **Installieren**:
   ```bash
   npm install -g @anthropic-ai/claude-code
   ```
2. **Einrichten & Starten**:
   - Wechsle im Terminal in diesen Projektordner und starte Claude:
     ```bash
     cd /Pfad/zu/Master
     claude
     ```
   - Beim ersten Start öffnet sich ein Browserfenster zur Anmeldung mit deinem Anthropic-/Claude-Account.
   - Claude Code liest automatisch `CLAUDE.md` (welches `AGENTS.md` einbindet) und stellt die Slash-Befehle `/tutor` und `/make-exercises` aus `.claude/skills/` bereit.

### Option C: Gemini CLI (Optional, für das Terminal)
1. **Installieren**:
   ```bash
   npm install -g @google/gemini-cli
   ```
2. **Starten**:
   - Im Projektordner `gemini` aufrufen. Es liest automatisch `GEMINI.md` und die Befehle aus `.gemini/commands/`.

---

## 4. Projekt & Automatischen Kurs-Sync einrichten

### Schritt 4.1: Repository klonen & Setup-Skript ausführen
```bash
git clone https://github.com/SimoneEsposito-Git/uni-tutor.git Master
cd Master
chmod +x setup.sh
./setup.sh
```
Das Skript `setup.sh` erledigt automatisch:
- Anlage der Python-Umgebung `_system/.venv`
- Installation aller Python-Pakete (`pymupdf`, `playwright`, `pyyaml`, `requests`, `icalendar`)
- Download des Headless-Browsers für Playwright (`chromium`)
- Erstellung deiner lokalen `_system/config.yaml` und `_system/com.master.sync.plist`

### Schritt 4.2: Kurse in `_system/config.yaml` eintragen
Öffne `_system/config.yaml` und trage deinen Login-Namen sowie deine Kurse ein. Die Kurs-ID findest du in der Browser-URL deines ISIS-/Moodle-Kurses (`https://isis.tu-berlin.de/course/view.php?id=12345`):

```yaml
moodle_url: "https://isis.tu-berlin.de"
token_env: MOODLE_TOKEN
ics_url_env: MOODLE_ICS_URL
username: "dein_tubit_username"

courses:
  - id: 49346
    name: "Database Technology"
    semester: "Semester 1"
```

### Schritt 4.3: Passwörter sicher im macOS-Schlüsselbund speichern
Es werden **niemals** Passwörter oder API-Tokens in Dateien gespeichert. Alles liegt verschlüsselt in der macOS Keychain:

1. **ISIS / TU-Login Passwort speichern** (Pflicht für `isis_sync.py`):
   ```bash
   security add-generic-password -a "$USER" -s isis-sync -w
   ```
   *(Du wirst nach der Eingabe des Befehls unsichtbar nach deinem Passwort gefragt).*

2. **Optional: Todoist-Integration für Abgabefristen**:
   Wenn du möchtest, dass Moodle-Kalender-Deadlines automatisch als Aufgaben in Todoist angelegt werden, speichere deinen Todoist API-Token (Todoist → Einstellungen → Integrationen → Entwickler) und deine private Moodle-Kalender-Export-URL (ISIS → Kalender → Kalender exportieren → URL abrufen):
   ```bash
   security add-generic-password -a "$USER" -s todoist-sync -w
   security add-generic-password -a "$USER" -s isis-ics -w
   ```
   *(Falls du diese beiden Einträge weglässt, überspringt der Sync den Todoist-Schritt automatisch).*

### Schritt 4.4: Erster Login & erster Sync
Beim allerersten Mal führst du den Sync mit sichtbarem Browserfenster (`--login`) aus, um die Session-Cookies in `_system/session.json` zu speichern (z. B. falls 2FA oder ein Cookie-Banner bestätigt werden muss):

```bash
_system/.venv/bin/python _system/isis_sync.py --login
```

Danach kannst du jederzeit den normalen (unsichtbaren) Sync starten:

```bash
_system/.venv/bin/python _system/isis_sync.py
```

### Schritt 4.5: Täglichen Hintergrund-Sync aktivieren (macOS LaunchAgent)
Damit deine Kurse jeden Morgen um 07:00 Uhr (bzw. beim Aufklappen des Macs) automatisch synchronisiert werden:

```bash
cp _system/com.master.sync.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.master.sync.plist
```
Den Log-Verlauf kannst du jederzeit in `_system/sync.log` einsehen.

---

## 5. Nutzung im Alltag

Öffne den `Master`-Ordner in **Antigravity** oder starte `claude` im Terminal:

### Sokratischer Tutor (`/tutor`)
Starte eine Lernsitzung für einen Kurs oder ein konkretes Übungsblatt:
- **In Claude Code / Gemini CLI**:
  ```text
  /tutor Database Technology
  ```
  oder gezielt:
  ```text
  /tutor Deep Learning Sheet 2
  ```
- **In Antigravity**:
  Schreibe einfach `Starte den Tutor für Database Technology` (oder nutze den `tutor`-Skill).

**Wie der Tutor arbeitet:**
- Er prüft zuerst `.tutor/progress.md` und schlägt Themen mit fälligem `Due`-Datum bzw. Status `repeat` vor.
- Er stellt dir **immer nur eine Leitfrage** pro Antwort und verrät nie die fertige Lösung.
- **Hinweisstufen**:
  1. Leitfrage zum Nachdenken
  2. Verweis auf die genaue Vorlesungsfolie / das Buchkapitel (z. B. *"Vorlesung 3, Folie 14"*)
  3. Konkreter Teilschritt (nur wenn du ausdrücklich `"hint 3"` schreibst)
- Eigene Lösungen kannst du in `solutions/` ablegen – der Tutor darf sie lesen, um dir gezieltes Feedback zu geben.
- Nach jedem Thema aktualisiert der Tutor automatisch deine `.tutor/progress.md`.

### Neue Übungsaufgaben generieren (`/make-exercises`)
Lass dir neue Aufgaben im exakten Stil deiner echten Übungsblätter erstellen:
- **Befehl**:
  ```text
  /make-exercises Database Technology "B+-Trees" exam
  ```
  *(Schwierigkeitsgrade: `easy`, `medium`, `exam`)*
- Beim ersten Aufruf analysiert die KI alle bisherigen Blätter in `exercises/` und erstellt einmalig `.tutor/style_guide.md`.
- Die neuen Aufgaben landen in `generated/<datum>_<thema>_<stufe>.md` und die Musterlösungen getrennt in `generated/<datum>_<thema>_<stufe>_solutions.md` (ohne sie im Chat zu spoilern).
