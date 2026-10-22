Language: English only.

Progress overview across all courses. No tutoring, no questions.

1. Run `python3 .unitutor/progress.py overview --open` from the project root (Windows: `python .unitutor\progress.py overview --open`). It reads every `progress.md`, writes `.unitutor/overview.html` (one stacked bar per course: red = new, blue = learning (repeat/ok/good), green = known (strong/solid); click a course to expand it into its topics with the exact status) and opens it in the browser. Do not read `progress.md` yourself.
2. Run `python3 .unitutor/progress.py pending`. If it lists lectures, add one line: "N lectures are not split into topics yet, run /sync".
3. Reply with the script's per-course lines as a compact table (Course | Topics | New | Learning | Known) and the chart path. Nothing else.
