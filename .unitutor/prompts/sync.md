Language: English only.

Manual course sync (Moodle) with a change summary, then new lecture topics go into `progress.md`. No tutoring.

1. Run `.unitutor/.venv/bin/python .unitutor/moodle_sync.py` (Windows: `.unitutor\.venv\Scripts\python.exe .unitutor\moodle_sync.py`) from the project root (headless; takes a minute or two, use a long timeout). Never pass `--login` unless step 3 applies.
2. Parse stdout. Per course the script prints `<course>: N new/changed [files]`; at the end `Todoist: N new tasks` (absent if Todoist is not configured).
3. If the output shows a login failure, expired session, or a Playwright/credentials error: report the error in one line and tell the user to run the same command with `--login` themselves (it needs a visible browser, possibly 2FA). Skip to step 5 (topics of files downloaded earlier by the daily sync still count).
4. For each course with changes, map the file names to their folders (`lectures/`, `exercises/`, `info/`) via `*/<course>/` and check whether the matching `.tutor/md/*.md` exists. Read only file names here.
5. Topics. Run `python3 .unitutor/progress.py pending` (Windows: `python .unitutor\progress.py pending`). It lists every lecture `.md` not yet in its course's `.tutor/index.md`, including ones the background daily sync fetched. For each listed file, and for each lecture from step 2 that was changed (already indexed):
   - Read that one `.md`. Decide whether it is an introduction lecture (only organisation/meta info). Intro: add only the index line, with "(intro, not tracked)", no topics. A mostly organisational lecture with a few content slides: track only those.
   - Add one line to `.tutor/index.md`: `` - `md/<file>`: Lecture N – <title> (<main topics>) ``. N = the number printed on the slides, else the chronological lecture order.
   - Split the content into topics: each one examinable unit (concept, model, algorithm, theorem, trade-off), usually 5-15 per lecture, short noun-phrase names, in slide order. No organisational slides. Do not duplicate topics already in `progress.md` (a changed lecture only adds topics that are missing).
   - Append them: pipe lines `Topic | Lecture N, slides a–b` into `python3 .unitutor/progress.py add "<course>"` (stdin, one per line). Status is set to `new`; never edit other rows.
6. Reply with a compact summary:
   - Table: Course | New/changed file | Folder | Markdown ready (yes/no) | Topics added
   - Todoist: N new tasks
   - Courses with no changes, in one line.
7. If no course changed and nothing was pending, say "No changes" plus the Todoist count. Suggest `/repeat` (or `/overview`) only if topics were added.
