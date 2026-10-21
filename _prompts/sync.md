Language: English only.

Manual course sync (ISIS/Moodle) with a change summary. No tutoring.

1. Run `_system/.venv/bin/python _system/isis_sync.py` from the Master folder (headless; takes a minute or two, use a long timeout). Never pass `--login` unless step 3 applies.
2. Parse stdout. Per course the script prints `<course>: N new/changed [files]`; at the end `Todoist: N new tasks` (absent if Todoist is not configured).
3. If the output shows a login failure, expired session, or a Playwright/credentials error: report the error in one line and tell the user to run `_system/.venv/bin/python _system/isis_sync.py --login` themselves (it needs a visible browser, possibly 2FA). Stop.
4. For each course with changes, map the file names to their folders (`lectures/`, `exercises/`, `info/`) via `Semester*/<course>/` and check whether the matching `.tutor/md/*.md` exists. Read only file names, never contents.
5. Reply with a compact summary:
   - Table: Course | New/changed file | Folder | Markdown ready (yes/no)
   - Todoist: N new tasks
   - Courses with no changes, in one line.
6. If no course changed, say "No changes" plus the Todoist count. Do not edit `progress.md` or `index.md`; suggest `/tutor <course>` only for courses with new material.
