# KI-Tutor & Automatischer Kurs-Sync für jede Uni mit Moodle

Dieses Projekt verwandelt deinen Studienordner in ein automatisiertes Lernsystem – für jede Hochschule mit **Moodle** (z. B. ISIS an der TU Berlin), auf **macOS, Windows und Linux**:
1. **Automatischer Kurs-Sync (`.unitutor/`)**: Lädt täglich neue Vorlesungsfolien, Übungsblätter, Vorlesungsvideos und Infos aus Moodle herunter – auch Dateien hinter Unterseiten (Textseiten, Links, Video-Sammlungen, Jupyter-Book-Übungen). Sortiert sie in die richtige Ordnerstruktur, schützt Originaldateien vor versehentlichem Überschreiben (schreibgeschützt) und wandelt PDFs und Notebooks in kompakte Markdown-Dateien (`.tutor/md/`) um, damit KI-Modelle sie token-sparend lesen können. Optional werden Abgabefristen nach **Todoist** synchronisiert. Funktioniert mit dem normalen Moodle-Login und mit Uni-SSO (Shibboleth o. Ä.).
2. **Sokratischer KI-Tutor & Aufgabengenerator**: Vorkonfigurierte Regeln ([AGENTS.md](../.unitutor/AGENTS.md)) und Slash-Befehle (`/setup`, `/tutor`, `/repeat`, `/solve`, `/anki`, `/make-exercises`, `/sync`) für **Claude Code**, **Google Antigravity** und **OpenAI Codex**. `/tutor` beantwortet deine Fragen zum Stoff mit exakten Folien-Zitaten, `/repeat` fragt dich wie Anki ab – aber pro Thema statt pro Karte, mit jedes Mal neu formulierten Fragen. `/sync` zerlegt neue Vorlesungen automatisch in einzelne Themen, Die Seite `Semester 1/overview.html` zeigt deinen Lernstand pro Kurs als Diagramm (rot = neu, blau = in Arbeit, grün = sitzt) und aktualisiert sich bei jedem Fortschritt automatisch. Lösungen von Übungsblättern werden nie direkt verraten; der Lernstand liegt in `.tutor/progress.md`.

---

## Easy Setup (empfohlen)

Du musst die Abschnitte weiter unten nicht lesen. Es genügen drei Schritte, den Rest erledigt `/setup`:

1. **Git installieren** (zum Klonen) und das Repository klonen:
   ```bash
   git clone https://github.com/SimoneEsposito-Git/uni-tutor.git
   ```
   *(Git fehlt noch? macOS: `xcode-select --install`, Windows: `winget install Git.Git`, Linux: `sudo apt install git`.)*
2. **Ein KI-Tool installieren und den Ordner `uni-tutor` darin öffnen** (eines reicht, Details in [Abschnitt 3](#3-ki-tools-installieren-claude-code-antigravity-codex)):
   - **Claude Code**: Desktop-App von [claude.ai/download](https://claude.ai/download) → Tab *Code* → Ordner öffnen. Oder CLI: `npm install -g @anthropic-ai/claude-code`, dann `cd uni-tutor && claude`.
   - **Google Antigravity**: [antigravity.google/download](https://antigravity.google/download) → *Open Folder*.
   - **OpenAI Codex**: `npm install -g @openai/codex`, dann `cd uni-tutor && codex`.
3. **`/setup` ausführen** (in Codex: `$setup`). Der Assistent führt dich Schritt für Schritt von null bis zum fertigen System:
   - prüft dein System und installiert fehlende Voraussetzungen (Python usw.) und die Umgebung
   - fragt nach Uni, Moodle-URL, Login-Art und Kurs-IDs und schreibt die `config.yaml`
   - lässt dich dein Passwort selbst sicher im Passwort-Speicher ablegen (der Assistent sieht es nie)
   - startet den ersten Login und Sync, richtet optional Todoist, den Tablet-Ordner für `/solve` und den täglichen Sync um 07:00 ein

`/setup` kann jederzeit erneut gestartet werden (z. B. für neue Kurse) und überspringt, was schon erledigt ist. Danach geht es weiter mit [Abschnitt 5](#5-nutzung-im-alltag). Die Abschnitte 2–4 sind die manuelle Variante und dienen als Nachschlagewerk.

---

## 1. Ordnerstruktur

```text
<Projektordner>/              # Sichtbar sind nur deine Kurse und eigenen Ordner
├── <Semester>/               # Wird automatisch vom Sync pro Kurs angelegt (nie committet)
│   └── <Kursname>/
│       ├── lectures/         # Vorlesungsfolien & -videos (schreibgeschützt)
│       ├── exercises/        # Übungsblätter (schreibgeschützt)
│       ├── info/             # Organisatorisches (schreibgeschützt)
│       ├── solutions/        # Eigene Lösungen / Musterlösungen (KI darf lesen, nie ändern)
│       ├── generated/        # Von /make-exercises generierte Übungsblätter & Lösungen
│       └── .tutor/           # Arbeitsverzeichnis der KI
│           ├── md/           # Automatisch aus PDFs/Notebooks extrahierter Text (.md)
│           ├── index.md      # Kurzindex (1 Zeile pro Vorlesung/Blatt, falls angelegt)
│           ├── progress.md   # Dein Lernfortschritt pro Thema (new → repeat → ok → good → strong → solid)
│           └── style_guide.md# Automatisch analysierter Stil der Übungsblätter
│
│   --- ausgeblendet (Ordner mit Punkt) ---
├── .claude/                  # CLAUDE.md (bindet AGENTS.md ein) + Skills für Claude Code
├── .agents/                  # rules/ (Antigravity) + skills/ (Antigravity & Codex)
├── .github/README.md         # Diese Anleitung
└── .unitutor/                # Das Tool selbst
    ├── AGENTS.md             # Zentrale Tutor-Regeln (für alle KI-Tools)
    ├── setup.sh / setup.ps1  # Einmaliges Setup (macOS & Linux / Windows)
    ├── config.yaml           # Deine Konfiguration (aus config.example.yaml)
    ├── moodle_sync.py        # Browser-Sync via Playwright (Moodle-Login oder SSO)
    ├── keystore.py           # Passwörter/Tokens im Passwort-Speicher des Systems ablegen
    ├── todoist_sync.py       # Optional: Moodle-Kalender-Deadlines -> Todoist
    ├── sync.py               # Alternativer Moodle-Sync via REST-Token
    ├── progress.py           # Lernstand: Abfrage-Warteschlange, Wiederholungsstufen, Übersichtsdiagramm
    └── prompts/              # Gemeinsame Abläufe der Slash-Befehle (/tutor, /repeat, /anki, ...)
```

Ordner mit Punkt sind auf macOS/Linux unsichtbar; unter Windows blenden Setup und Sync sie im Explorer aus. Einblenden: `Cmd + Shift + .` im Finder bzw. *Ansicht → Ausgeblendete Elemente* im Explorer.

Alles außer den Dateien des Tools selbst (Kursordner, eigene Dokumente, Konfiguration, Sessions) ist per `.gitignore` vom Repository ausgeschlossen.

---

## 2. Voraussetzungen installieren

Benötigt werden **Python 3.10+**, **Git** und (für die CLI-Tools) **Node.js**.

### macOS
Öffne das **Terminal** (`Cmd + Leertaste` → `Terminal`):
```bash
xcode-select --install
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install python node git
```
*(Folge den Anweisungen im Terminal, um Homebrew zu deinem `PATH` hinzuzufügen).*

### Windows
Öffne **PowerShell** (Startmenü → `PowerShell`):
```powershell
winget install Python.Python.3.12 Git.Git OpenJS.NodeJS.LTS
```
Danach PowerShell neu öffnen, damit `python`, `git` und `npm` gefunden werden.

### Linux
Über den Paketmanager deiner Distribution, z. B. `sudo apt install python3 python3-venv git nodejs npm`.

---

## 3. KI-Tools installieren (Claude Code, Antigravity, Codex)

Du kannst das Projekt wahlweise mit **Claude Code**, **Google Antigravity** oder **OpenAI Codex** (oder allen parallel) nutzen. Alle greifen auf dieselben Regeln ([AGENTS.md](../.unitutor/AGENTS.md)) und denselben Lernstand (`.tutor/progress.md`) zu.

| Tool | Regeln (`.unitutor/AGENTS.md`) | Befehle |
|---|---|---|
| Claude Code | immer, über `.claude/CLAUDE.md` | `/setup`, `/tutor`, `/repeat`, `/solve`, `/anki`, `/make-exercises`, `/sync`, `/end` aus `.claude/skills/` |
| Antigravity | immer, über `.agents/rules/` | Skills aus `.agents/skills/` |
| Codex | nur beim Aufruf eines Skills* | `$tutor`, `$repeat`, … aus `.agents/skills/` |

\* Codex liest Regeln sonst nur aus einer `AGENTS.md` direkt im Projektordner. Damit dieser sauber bleibt, laden die Skills die Regeln selbst; im freien Chat ohne Skill gelten sie nicht.

### Option A: Claude Code (Desktop-App, CLI oder IDE)
- **Desktop-App**: [claude.ai/download](https://claude.ai/download) → Tab *Code* → diesen Projektordner öffnen.
- **CLI**:
  ```bash
  npm install -g @anthropic-ai/claude-code
  cd /Pfad/zum/Projektordner
  claude
  ```

### Option B: Google Antigravity (IDE & Agent)
1. **Herunterladen & Installieren**: [antigravity.google/download](https://antigravity.google/download) (macOS & Windows), mit dem Google-Account anmelden.
2. **Projekt öffnen**: **Open Folder** → diesen Projektordner wählen.

### Option C: OpenAI Codex (CLI, IDE-Erweiterung oder App)
```bash
npm install -g @openai/codex
cd /Pfad/zum/Projektordner
codex
```
Beim ersten Start mit dem ChatGPT-Account anmelden und den Ordner als vertrauenswürdig bestätigen.

### Testen, ob die Regeln geladen sind
Stelle in einem **neuen** Chat im Projektordner diese Frage. Richtig ist: *Stufe 3 (nur auf "hint 3")* und *+7 Tage*.
```text
Which hint level do you only give on explicit request, and what is the next review interval for status "strong"? Answer from your instructions only.
```
- **Claude Code**: Zusätzlich zeigt `/memory`, dass `.claude/CLAUDE.md` geladen ist; `/tutor Database Technology` startet den Tutor.
- **Antigravity**: Unter *Customizations → Rules* sollte die Workspace-Regel `tutor` erscheinen. Danach im Chat: `Starte den Tutor für Database Technology`.
- **Codex**: Die Frage im freien Chat beantwortet Codex *nicht* aus den Regeln (siehe oben). Teste stattdessen `/skills` (listet `tutor`, `repeat`, …) und `$tutor Database Technology` – Codex sollte zuerst `.unitutor/AGENTS.md` lesen.

---

## 4. Projekt & Automatischen Kurs-Sync einrichten

In den Befehlen unten steht `PY` für den Python-Interpreter der Projektumgebung:
- **macOS / Linux**: `.unitutor/.venv/bin/python`
- **Windows**: `.unitutor\.venv\Scripts\python.exe`

### Schritt 4.1: Repository klonen & Setup-Skript ausführen
**macOS / Linux:**
```bash
git clone https://github.com/SimoneEsposito-Git/uni-tutor.git
cd uni-tutor
./.unitutor/setup.sh
```
**Windows (PowerShell):**
```powershell
git clone https://github.com/SimoneEsposito-Git/uni-tutor.git
cd uni-tutor
powershell -ExecutionPolicy Bypass -File .unitutor\setup.ps1
```
Das Setup legt die Python-Umgebung `.unitutor/.venv` an, installiert alle Pakete und den Headless-Browser (Chromium) und erstellt deine lokale `.unitutor/config.yaml`.

### Schritt 4.2: `.unitutor/config.yaml` anpassen
Öffnen mit `open -e .unitutor/config.yaml` (macOS), `notepad .unitutor\config.yaml` (Windows) oder `xdg-open .unitutor/config.yaml` (Linux).

Trage die Adresse deiner Moodle-Instanz, deinen Login-Namen und deine Kurse ein. Die Kurs-ID steht in der Browser-URL des Kurses (`.../course/view.php?id=12345`):

```yaml
moodle_url: "https://moodle.example-uni.de"
username: "dein_login_name"

login:                       # weglassen, wenn sich dein Moodle mit dem normalen Formular anmeldet
  sso_button: "Uni-Login"    # Text des SSO-Buttons auf der Moodle-Login-Seite
  consent_button: "Fortsetzen"  # optional: Cookie-Banner, das vorher bestätigt werden muss

courses:
  - id: 12345
    name: "Database Technology"
    semester: "Semester 1"   # beliebiger Ordnername, z. B. "WiSe 26-27"
```
*Beispiel TU Berlin (ISIS):* `moodle_url: "https://isis.tu-berlin.de"`, `sso_button: "TU-Login"`, `consent_button: "Fortsetzen"`.

### Schritt 4.3: Passwörter sicher speichern
Es werden **niemals** Passwörter oder API-Tokens in Dateien gespeichert. Sie liegen im Passwort-Speicher deines Systems (macOS-Schlüsselbund, Windows-Anmeldeinformationsverwaltung, Linux Secret Service):

1. **Moodle-/SSO-Passwort** (Pflicht):
   ```bash
   PY .unitutor/keystore.py set password
   ```
   *(Du wirst unsichtbar nach dem Passwort gefragt).*

2. **Optional: Todoist-Integration für Abgabefristen** – Moodle-Kalender-Deadlines werden automatisch als Todoist-Aufgaben angelegt. Benötigt deinen Todoist API-Token (Todoist → Einstellungen → Integrationen → Entwickler) und deine private Kalender-Export-URL (Moodle → Kalender → Kalender exportieren → URL abrufen):
   ```bash
   PY .unitutor/keystore.py set todoist
   PY .unitutor/keystore.py set ics
   ```
   *(Ohne diese Einträge überspringt der Sync den Todoist-Schritt automatisch.)*

Mit `PY .unitutor/keystore.py check` siehst du, welche Einträge vorhanden sind. Die Eintragsnamen lassen sich unter `secrets:` in der `config.yaml` ändern.

### Schritt 4.4: Erster Login & erster Sync
Beim ersten Mal mit sichtbarem Browserfenster (`--login`), um die Session in `.unitutor/session.json` zu speichern (z. B. falls 2FA oder ein Cookie-Banner bestätigt werden muss):
```bash
PY .unitutor/moodle_sync.py --login
```
Danach jederzeit den normalen (unsichtbaren) Sync starten – oder `/sync` im KI-Tool verwenden:
```bash
PY .unitutor/moodle_sync.py
```

### Schritt 4.5: Täglichen Hintergrund-Sync aktivieren (07:00 Uhr)
**macOS** (LaunchAgent, läuft auch nach dem Aufwachen nach):
```bash
cp .unitutor/com.unitutor.sync.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.unitutor.sync.plist
```
**Windows** (Aufgabenplanung, holt verpasste Läufe nach):
```powershell
powershell -ExecutionPolicy Bypass -File .unitutor\setup.ps1 -Schedule
```
**Linux**: `.unitutor/setup.sh` gibt am Ende eine passende `crontab`-Zeile aus.

Den Log-Verlauf findest du in `.unitutor/sync.log`.

---

## 5. Nutzung im Alltag

Öffne den Projektordner in **Claude Code**, **Antigravity** oder **Codex**:

### Sokratischer Tutor (`/tutor`)
Starte eine Lernsitzung für einen Kurs oder ein konkretes Übungsblatt:
- **In Claude Code** (in Codex `$tutor` statt `/tutor`):
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

---

## 6. Optional: Fortschritts-Widget

`progress.py` schreibt bei jedem Fortschritt eine `progress.json` (Lernstand pro Kurs). Daraus zeigen Widgets Donut-Diagramme (grün = sitzt, blau = in Arbeit, rot = neu). Es gibt drei Varianten, alle in `.unitutor/widget/`; eine reicht:

| Variante | Plattform | Quelle | Datenpfad |
|---|---|---|---|
| macOS-Widget (WidgetKit) | macOS 14+ | `widget/mac/` | `~/Library/Application Support/Unitutor/progress.json` |
| Übersicht-Widget | macOS | `widget/unitutor.widget/` | dieselbe Datei |
| Scriptable-Widget | iPhone/iPad | `widget/progress-widget.js`, `progress-widget-loader.js` | iCloud Drive, Ordner `Unitutor` |

Die Datei entsteht nach dem ersten Lernfortschritt (z. B. nach `/sync` oder `/repeat`). Mit `PY .unitutor/progress.py overview` kannst du sie sofort erzeugen lassen.

### macOS-Widget (WidgetKit)
Benötigt Xcode (aus dem App Store) und [XcodeGen](https://github.com/yonaskolb/XcodeGen).
```bash
brew install xcodegen
cd .unitutor/widget/mac
xcodegen generate
open Unitutor.xcodeproj
```
1. In Xcode bei beiden Targets (`Unitutor` und `UnitutorWidget`) unter *Signing & Capabilities* dein **Team** wählen (oder `DEVELOPMENT_TEAM` in `project.yml` eintragen und erneut `xcodegen generate` ausführen).
2. **Release-Build nach `~/Applications` installieren.** Das Widget muss aus dort laufen, nicht aus Xcodes DerivedData-Ordner, sonst verliert macOS die Registrierung und das Widget bleibt auf einem alten Stand stehen:
   ```bash
   cd .unitutor/widget/mac
   xcodebuild -scheme Unitutor -configuration Release -derivedDataPath build
   mkdir -p ~/Applications
   ditto build/Build/Products/Release/Unitutor.app ~/Applications/Unitutor.app
   open ~/Applications/Unitutor.app
   ```
3. Rechtsklick auf den Desktop (oder Benachrichtigungszentrale) → *Widgets bearbeiten* → **Unitutor** hinzufügen.

`progress.py` stößt nach jedem Fortschritt automatisch ein Neuladen an, sobald `~/Applications/Unitutor.app` existiert; ohne Push aktualisiert sich das Widget alle ca. 15 Minuten.

**Widget zeigt alte Daten?** Prüfe, ob die Erweiterung registriert ist, und registriere sie sonst neu:
```bash
pluginkit -mAvvv -i com.unitutor.progress.widget
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f -R ~/Applications/Unitutor.app
pluginkit -a ~/Applications/Unitutor.app/Contents/PlugIns/UnitutorWidget.appex
open -g ~/Applications/Unitutor.app
killall chronod
```

### Übersicht-Widget (ohne Xcode)
1. [Übersicht](https://tracesof.net/uebersicht/) installieren.
2. Den Ordner `.unitutor/widget/unitutor.widget` in den Widget-Ordner von Übersicht kopieren (*Menüleiste → Open Widgets Folder*).
3. Optional in `index.jsx` die Konstante `COURSE` auf einen Kursnamen oder dessen Initialen setzen (leer = alle Kurse). Für ein Widget pro Kurs den Ordner duplizieren und `COURSE` sowie die Position anpassen.

### Scriptable-Widget (iPhone/iPad)
Setzt iCloud Drive auf dem Mac voraus: `progress.py` legt dann automatisch den Ordner `Unitutor` mit der `progress.json` an.
1. **Scriptable** aus dem App Store installieren.
2. `progress-widget.js` in den iCloud-Ordner `Unitutor` kopieren (Dateien-App → iCloud Drive → Unitutor).
3. In Scriptable: *Settings → File Bookmarks* → den iCloud-Ordner `Unitutor` unter dem Namen `Unitutor` hinzufügen.
4. Neues Script anlegen und den Inhalt von `progress-widget-loader.js` einfügen. Spätere Updates von `progress-widget.js` brauchen so kein erneutes Kopieren.
5. Scriptable-Widget auf den Home-Bildschirm legen und das Script wählen. Ohne *Parameter* werden alle Kurse gezeigt; mit Kursname oder Initialen (z. B. `dl`) nur dieser Kurs.
