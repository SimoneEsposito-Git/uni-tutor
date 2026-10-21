#!/usr/bin/env python3
"""Build the blank worksheet and the clean solutions PDF for one /solve sheet.

Usage: solve_build.py <sheet_dir> [--export DIR]

<sheet_dir> (generated/solve/<slug>/) holds:
  meta.json          course, sheet, slug, exercises[{n,title,points,subtasks}], selected{n:[ids]}
  tasks/ex<n>.tex    statement before the subtasks (may be empty)
  tasks/ex<n><x>.tex statement of subtask x (exercises without subtasks: only ex<n>.tex)
  sol/<n><x>.tex     solution of subtask x (no subtasks: sol/<n>.tex), body of a solution env
Output: <slug>_worksheet.pdf (one exercise per page, blank space) and
        <slug>_my_solutions.pdf (solved exercises collapsed, unsolved keep a page).
"""
import json, shutil, subprocess, sys
from pathlib import Path

PREAMBLE = Path(__file__).with_name("preamble.tex")


def read(p):
    return p.read_text(encoding="utf-8").strip() if p.exists() else ""


def header(meta):
    return (
        "\\begin{center}\n"
        f"  {{\\LARGE\\bfseries {meta['course']}}}\\\\[0.6em]\n"
        f"  {{\\Large {meta['sheet']}}}\\\\[0.8em]\n"
        "  {\\normalsize Name: \\rule{5cm}{0.4pt}}\n"
        "\\end{center}\n"
    )


def build_doc(meta, d, solutions):
    out = [header(meta)]
    selected = meta.get("selected")
    for ex in meta["exercises"]:
        n = ex["n"]
        if selected is not None and str(n) not in selected:
            continue
        out.append(f"\\exercise{{{n}}}{{{ex['title']}}}{{{ex['points']}}}\n")
        out.append(read(d / f"tasks/ex{n}.tex") + "\n")
        if ex["subtasks"]:
            sel = (selected or {}).get(str(n), ex["subtasks"])
            sols = []
            for x in sel:
                out.append(f"\\subtask{{{x}}}" + read(d / f"tasks/ex{n}{x}.tex") + "\n")
                sol = read(d / f"sol/{n}{x}.tex")
                sols.append(bool(sol))
                if solutions and sol:
                    out.append(f"\\begin{{solution}}\n{sol}\n\\end{{solution}}\n")
            solved = all(sols)
        else:
            sol = read(d / f"sol/{n}.tex")
            solved = bool(sol)
            if solutions and sol:
                out.append(f"\\begin{{solution}}\n{sol}\n\\end{{solution}}\n")
        # worksheet: always one page per exercise; solutions: collapse once solved
        if not solutions or not solved:
            out.append("\\vspace*{\\fill}\n\\clearpage\n")
    return "\n".join(out)


def compile_pdf(tex, name, d):
    b = d / "build"
    b.mkdir(exist_ok=True)
    src = b / f"{name}.tex"
    src.write_text(tex, encoding="utf-8")
    r = subprocess.run(
        ["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", f"{name}.tex"],
        cwd=b, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-2500:] or r.stderr[-2500:])
        sys.exit(f"LaTeX failed for {name} (see {b / (name + '.log')})")
    shutil.copy(b / f"{name}.pdf", d / f"{name}.pdf")
    return d / f"{name}.pdf"


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)
    d = Path(args[0]).resolve()
    export = Path(args[args.index("--export") + 1]).expanduser() if "--export" in args else None
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    pre = PREAMBLE.read_text(encoding="utf-8")
    made = []
    for solutions, suffix in ((False, "worksheet"), (True, "my_solutions")):
        body = build_doc(meta, d, solutions)
        tex = f"{pre}\n\\begin{{document}}\n{body}\n\\end{{document}}\n"
        made.append(compile_pdf(tex, f"{meta['slug']}_{suffix}", d))
    if export:
        export.mkdir(parents=True, exist_ok=True)
        shutil.copy(made[0], export / made[0].name)
        print(f"exported {made[0].name} -> {export}")
    for p in made:
        print(p)


if __name__ == "__main__":
    main()
