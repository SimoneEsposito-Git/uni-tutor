Language: English only.

Arguments: `<sheet> [subtasks]`, e.g. `sheet 2`, `sheet 2 1a 3`, `2 ex1b 2` (a bare exercise number = all its subtasks). Course: from context, else ask.

## Paths
- Course folder: `*/<course>/` (contains `.tutor/`). Work dir: `<course>/generated/solve/<slug>/`, slug = `sheet02` (zero-padded sheet number).
- Tools: `.unitutor/solve/solve_build.py` (build), `.unitutor/solve/preamble.tex` (template). Do not edit `exercises/`, `lectures/`, `info/`, `solutions/`.
- iPad exchange folder: `~/Library/Mobile Documents/com~apple~CloudDocs/Handwritten/<course>/` (iPad: iCloud Drive > Handwritten > <course>). Master itself stays outside iCloud.

## Case A: work dir does not exist -> create
1. Find the sheet in `exercises/` (zip: unzip into the scratchpad, never into `exercises/`). Task text: `.tutor/md` if the sheet is there, else `pdftotext -layout` of the PDF; look at the PDF pages (Read) for figures/axes.
2. Write `meta.json` (course, sheet, slug, exercises[{n,title,points,subtasks}], `selected` {"n":[ids]}; omit `selected` for all tasks), `tasks/ex<n>.tex` (statement before the subtasks, may be empty) and `tasks/ex<n><x>.tex` per subtask (exercises without subtasks: only `ex<n>.tex`, solution `sol/<n>.tex`). Copy the task text faithfully, hints included; figures to draw on become blank space.
3. Run `python3 .unitutor/solve/solve_build.py <workdir> --export "<iCloud exchange folder>"`. Output: `<slug>_worksheet.pdf` (one exercise per page, footer "Exercise n"), `<slug>_my_solutions.pdf`.
4. Tell the user: worksheet is in iCloud `Handwritten/<course>/`; write on it in GoodNotes/Notability, insert extra pages right after the exercise they belong to, and let the app auto-export to the same folder.

## Case B: work dir exists -> never recreate
- Read `meta.json`; list status per subtask (solved = `sol/<id>.tex` exists, else open). New subtasks requested: add them to `selected` + `tasks/`, rebuild, re-export.
- Check the exchange folder for a newer annotated PDF (name starting with the slug, not `_worksheet`/`_my_solutions` if it is identical to ours) -> ingest (below).
- Then start a tutor session on the open subtasks (Case C).

## Ingest handwritten pages
1. Render: `pdftoppm -r 110 -png <pdf> <scratchpad>/pg`; Read the images. Page -> exercise via the footer marker; inserted pages belong to the exercise before them.
2. Transcribe the user's own work faithfully into `sol/<id>.tex` (body of a `solution` env; align/equation, `\pd`, `\R` available; sketches -> TikZ, or crop with `pdftoppm -x -y -W -H` into `sol/img/` and `\includegraphics`). Do not fix, complete or improve their maths. Mark unclear symbols `% CHECK: ...` and ask the user about them.
3. Rebuild; solved exercises collapse, open ones keep their page. Report which subtasks changed.

## Case C: typing in chat
User gives answers in words/rough maths; typeset them into `sol/<id>.tex`, rebuild. Same rule: never supply content they did not give.

## Tutoring (rules in `.unitutor/AGENTS.md` apply)
- Never state a solution; one guiding question per reply; hint levels; cite sources.
- Feedback on a transcribed solution: compare with `solutions/` if present (read only), point at the faulty step with a question, do not correct it for them. Typeset the solution as the user wrote it; fixes go in only after the user gives them.
- Update `.tutor/progress.md` as usual after each topic (ladder in `AGENTS.md`).
