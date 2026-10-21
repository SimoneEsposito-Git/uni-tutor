Language: English only.

First-time setup after cloning. Goal: from a fresh clone to a working sync, scheduled run and tutor. One step at a time; ask only what that step needs. Do not tutor.

`PY` = `.unitutor/.venv/bin/python` (Windows: `.unitutor\.venv\Scripts\python.exe`). Run everything from the project root.

## Rules
- Resumable: run Step 0 first and skip every step that is already done. Re-running `/setup` may only fill gaps or change what the user asks to change.
- Never ask for, read, echo or store passwords, tokens or calendar URLs. The user enters them in their own terminal (`keystore.py` prompts hidden). Never write secrets into `config.yaml`.
- Never overwrite an existing `.unitutor/config.yaml` or `.unitutor/solve/settings.json` without asking; show the diff first. Do not commit either (git-ignored).
- Commands that install software or change system scheduling (setup script, `launchctl`, `crontab`, `winget`/`brew`/`apt`): state what they do, run only after a yes. If a command fails, show the error in one line, fix the cause or give the user the exact command. Never retry blindly.
- Steps that need the user's own terminal or browser (password entry, `--login`): give the exact command in its own code block, wait for "done", then verify.
- Keep replies short: one question or one instruction per message, with a progress marker ("Step 3/8").

## Step 0: Detect state
Silently check and summarise in one compact table (Item | Status):
- OS (`uname`, Windows if PowerShell) and Python >= 3.10, git
- `.unitutor/.venv` exists and has playwright (`PY -c "import playwright, fitz, yaml, keyring"`; on macOS keyring is not needed)
- `.unitutor/config.yaml` exists; which fields are still placeholders (`example-uni`, `dein_login_name`, `12345`)
- `PY .unitutor/keystore.py check` (only if the venv works)
- `.unitutor/session.json` exists
- course folders under `<semester>/<course>/`
- scheduler installed (macOS: `~/Library/LaunchAgents/com.unitutor.sync.plist`; Windows: task `uni-tutor-sync`; Linux: `crontab -l`)
- `.unitutor/solve/settings.json`, `latexmk`/`pdflatex` on PATH
Then continue with the first unfinished step.

## Step 1: Prerequisites
Missing Python 3.10+, git or Node.js: offer the install command for their OS (macOS `brew install python node git`; Windows `winget install Python.Python.3.12 Git.Git OpenJS.NodeJS.LTS`, then a new terminal; Linux `sudo apt install python3 python3-venv git nodejs npm`). On macOS without Homebrew, point to `.github/README.md` section 2. Node is only needed for the Codex CLI, skip it if the user does not use that.

## Step 2: Environment
Ask for a yes, then run the setup script: macOS/Linux `./.unitutor/setup.sh`, Windows `powershell -ExecutionPolicy Bypass -File .unitutor\setup.ps1`. It creates `.venv`, installs packages and Chromium, and copies `config.example.yaml` to `config.yaml`. Takes a few minutes: long timeout. Ignore its printed "next steps"; this skill replaces them. Verify with the import check from Step 0.

## Step 3: University and login (writes `config.yaml`)
Ask, one at a time:
1. University and Moodle URL (e.g. `https://isis.tu-berlin.de`). If the user names only the university, look up the Moodle URL and confirm it with them. If the university does not use Moodle, say so plainly: the sync cannot work, but the tutor still can (user puts PDFs into `lectures/`, `exercises/`; skip Steps 3-6 and 8's scheduling; `.tutor/md` must then be created manually, offer to convert PDFs with `PY` + PyMuPDF).
2. Login name (the one typed on the login page).
3. Login type: "On the Moodle login page, do you type username/password directly, or do you click a button like 'Uni-Login' / 'TU-Login' first?" If a button: ask for its exact text -> `login.sso_button`. Ask whether a cookie/terms banner appears before login and its button text -> `login.consent_button`. Remove the `login` block entirely for a plain form login.
4. Names for the keychain entries: keep the defaults (`moodle-password`, `moodle-ics`, `todoist-token`) unless entries already exist under other names (`secrets:` block).
Edit `config.yaml` in place with the answers (keep the commented structure of the example; remove placeholder lines such as `token_env`/`ics_url_env`, which only the unused REST variant `sync.py` needs, and the placeholder courses).

## Step 4: Courses
Ask for the semester folder name (any name, e.g. "Semester 1", "WiSe 26-27"). Then per course: course name (becomes the folder name; avoid `/ \ : * ? " < > |`) and its Moodle course ID. Explain: open the course in Moodle; the ID is the number in the URL `.../course/view.php?id=12345`. Accept pasted URLs and extract the ID yourself. The user can list all courses first, then give IDs; offer to add more later via `/setup`. Write them to `courses:`. Validate: ids are integers, no duplicate ids or names. Courses of different semesters can use different `semester` values.

## Step 5: Password
Tell the user to run this in their own terminal (hidden prompt; macOS may ask to allow the keychain):
```bash
PY .unitutor/keystore.py set password
```
Wait for "done", then verify with `keystore.py check` that `password` is `stored`. Never ask for the value.

## Step 6: First login and first sync
1. Tell the user to run `PY .unitutor/moodle_sync.py --login` themselves (visible browser; they handle 2FA, cookie banners, SSO prompts). Wait for "done", check that `.unitutor/session.json` exists.
2. If login failed: ask what the browser showed. Typical causes: wrong `sso_button`/`consent_button` text (fix in `config.yaml`), wrong login name, 2FA. Retry.
3. Ask for a yes, then run `PY .unitutor/moodle_sync.py` (headless, long timeout). Report per course the number of new files. Check that `<semester>/<course>/{lectures,exercises,info}` and `.tutor/md/` exist and list the file counts. A course with 0 files: wrong ID or no access, ask the user to check the URL.
If the course folders are fresh, offer to build `.tutor/index.md` (one line per lecture/sheet, from `.tutor/md/`) for each course now or later via `/tutor`.

## Step 7: Optional integrations (ask each, default no)
- **Todoist deadlines**: needs a Todoist API token (Todoist -> Settings -> Integrations -> Developer) and the private Moodle calendar export URL (Moodle -> Calendar -> Export calendar -> Get URL). The user enters both themselves:
  ```bash
  PY .unitutor/keystore.py set todoist
  PY .unitutor/keystore.py set ics
  ```
  Verify with `keystore.py check`; the next sync creates the tasks.
- **Tablet for `/solve`** (handwritten solutions): ask the three First-time-setup questions of `.unitutor/prompts/solve.md` now and write `.unitutor/solve/settings.json`, so `/solve` does not ask later. Also check for LaTeX (`latexmk --version`); if missing, name the install (macOS `brew install --cask mactex-no-gui` or `basictex`, Windows MiKTeX, Linux `sudo apt install texlive-full latexmk`) and note that only `/solve` needs it.

## Step 8: Daily sync (optional)
Ask: "Run the sync automatically every day at 07:00?" If yes, with confirmation:
- macOS: `setup.sh` already wrote `.unitutor/com.unitutor.sync.plist` with the project path. Run `cp .unitutor/com.unitutor.sync.plist ~/Library/LaunchAgents/ && launchctl load ~/Library/LaunchAgents/com.unitutor.sync.plist`. If the project folder is moved later, re-run setup and reload.
- Windows: `powershell -ExecutionPolicy Bypass -File .unitutor\setup.ps1 -Schedule`.
- Linux: add the crontab line `setup.sh` printed (`0 7 * * * "PY" ".unitutor/moodle_sync.py" >> ".unitutor/sync.log" 2>&1`, absolute paths) after showing it.
Mention the log: `.unitutor/sync.log`. The scheduled run needs the saved session; if it expires, `/sync` reports it and the user re-runs `--login`.

## Step 9: Verify and hand over
1. Ask the rules check question from `.github/README.md` ("Which hint level do you only give on explicit request, and what is the next review interval for status 'strong'?") only if the user uses a tool other than Claude Code; in Claude Code the rules are loaded via `.claude/CLAUDE.md`.
2. Print a final checklist (Item | Status) mirroring Step 0 and anything skipped, with how to do it later.
3. Show the daily commands: `/sync`, `/tutor <course>`, `/repeat`, `/solve <sheet>`, `/make-exercises <course> <topic> <level>`, `/anki <course> <lecture>`, `/end`. Suggest starting with `/tutor <first course>`.
