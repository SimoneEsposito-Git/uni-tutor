Language: English only.

Terms: sheet = the whole exercise sheet, exercise = an Exercise inside it, task = one atomic question of an exercise (a), (b), ... (an exercise without lettered tasks is itself one task).

Arguments: `<sheet> [tasks]`, e.g. `sheet 2`, `sheet 2 1a 3`, `2 ex1b 2` (a bare exercise number = all its tasks). Course: from context, else ask.

## Paths
- Course folder: `*/<course>/` (contains `.tutor/`). Work dir: `<course>/generated/solve/<slug>/`, slug = `sheet02` (zero-padded sheet number).
- Tools: `.unitutor/solve/solve_build.py` (build), `.unitutor/solve/preamble.tex` (template). Do not edit `exercises/`, `lectures/`, `info/`, `solutions/`.
- Tablet exchange folder: read `tablet_folder` from `.unitutor/solve/settings.json` (personal, git-ignored; see First-time setup). Per course use `<tablet_folder>/<course>/`. The user's own sync tool (iCloud, OneDrive, Dropbox, Syncthing, ...) carries it to the tablet; never assume a specific one.

## Case A: work dir does not exist -> create
1. Find the sheet in `exercises/` (zip: unzip into the scratchpad, never into `exercises/`). Task text: `.tutor/md` if the sheet is there, else `pdftotext -layout` of the PDF; look at the PDF pages (Read) for figures/axes.
2. Write `meta.json` (course, sheet, slug, exercises[{n,title,points,tasks:[letters]}], `selected` {"n":[ids]}; omit `selected` for all tasks), `tasks/ex<n>.tex` (exercise intro before the tasks, may be empty) and `tasks/ex<n><x>.tex` per task (exercises without lettered tasks: only `ex<n>.tex`, solution `sol/<n>.tex`). Copy the task text faithfully, hints included; figures to draw on become blank space.
3. Run `python3 .unitutor/solve/solve_build.py <workdir>`. Output: `<slug>_worksheet.pdf` (one task per page, footer "Exercise n -- task (x)"), `<slug>_my_solutions.pdf`.
4. If `settings.json` is missing, run First-time setup now. Then, if `tablet_folder` is set, copy the worksheet there with `solve_build.py <workdir> --export "<tablet_folder>/<course>"` (re-run is cheap). Tell the user where the worksheet is; with a tablet: write on it, insert extra pages right after the task they belong to, and export the annotated PDF to the same folder. Without a tablet: the PDF is in the work dir (print it or open it in any PDF editor).

## First-time setup (only when `.unitutor/solve/settings.json` does not exist)
Ask these two questions, one at a time, in the user's own words, after the first worksheet is built:
1. "Do you want a shared folder to exchange PDFs with a tablet?" Options: `create` (create one for me) | `existing` (I already have a folder) | `none`.
2. `create`: ask where it should be located (suggest a folder inside a location that is already synced to their tablet; the project folder is fine if it is synced or they sync it manually), then create it. `existing`: ask for its path and check that it exists. `none`: skip.
Save `{"tablet_folder": "<absolute path>" | null, "mode": "create|existing|none"}` to `.unitutor/solve/settings.json` and use it from then on. Never ask again unless the user asks to change it (then overwrite the file). Do not commit this file.

## Case B: work dir exists -> never recreate
- Read `meta.json`; list status per task (solved = `sol/<id>.tex` exists, else open). New tasks requested: add them to `selected` + `tasks/`, rebuild, re-export.
- If `tablet_folder` is set, check `<tablet_folder>/<course>/` for a newer annotated PDF (name starting with the slug, not `_worksheet`/`_my_solutions` if it is identical to ours) -> ingest (below).
- Then start a tutor session on the open tasks (Case C).

## Ingest handwritten pages
1. Render: `pdftoppm -r 110 -png <pdf> <scratchpad>/pg`; Read the images. Page -> task via the footer marker; inserted pages belong to the task before them.
2. Transcribe the user's own work faithfully into `sol/<id>.tex` (body of a `solution` env; align/equation, `\pd`, `\R` available; sketches -> TikZ, or crop with `pdftoppm -x -y -W -H` into `sol/img/` and `\includegraphics`). Do not fix, complete or improve their maths. Mark unclear symbols `% CHECK: ...` and ask the user about them.
3. Rebuild; solved tasks collapse, open ones keep their page. Report which tasks changed.

## Case C: typing in chat
User gives answers in words/rough maths; typeset them into `sol/<id>.tex`, rebuild. Same rule: never supply content they did not give.

## Tutoring (rules in `.unitutor/AGENTS.md` apply)
- Never state a solution; one guiding question per reply; hint levels; cite sources.
- Feedback on a transcribed solution: compare with `solutions/` if present (read only), point at the faulty step with a question, do not correct it for them. Typeset the solution as the user wrote it; fixes go in only after the user gives them.
- Update `.tutor/progress.md` as usual after each topic (ladder in `AGENTS.md`).
