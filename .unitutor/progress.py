#!/usr/bin/env python3
"""Progress helper for the tutor skills: reads/writes every course's .tutor/progress.md (stdlib only).

  python3 progress.py pending                         # lecture .md files not yet split into topics (not in index.md)
  python3 progress.py add <course>                    # stdin lines "Topic | Source" -> new rows with status `new`
  python3 progress.py queue [course] [--max 8] [--new 3]   # /repeat queue: due reviews + a few new topics
  python3 progress.py grade <course> <topic> pass|partial|fail|seen [--note "..."]   # applies the review ladder
  python3 progress.py overview [--open]               # rebuilds <semester>/overview.html, prints a one-line summary per course
(every write to a progress.md rebuilds its semester's overview.html automatically)
"""
import argparse, datetime as dt, html, json, re, sys, webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TODAY = dt.date.today()
HEADER = "| Topic | Source | Status | Last seen | Due | Notes |\n|---|---|---|---|---|---|\n"
TIERS = ["repeat", "ok", "good", "strong", "solid"]
INTERVAL = {"repeat": 0, "ok": 1, "good": 3, "strong": 7, "solid": 21}  # days until Due
GROUP = {"new": "new", "repeat": "learning", "ok": "learning", "good": "learning", "strong": "known", "solid": "known"}
NONE = "—"
LOCAL_WIDGET_DIR = Path.home() / "Library/Application Support/Unitutor"  # not TCC-protected: read by the Übersicht desktop widget
WIDGET_DIR = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/Unitutor"  # synced to the phone; read by widget/progress-widget.js


def courses() -> dict:
    """Course name -> course folder (every `<semester>/<course>/` with a `.tutor/`, unless it holds an `untracked` marker file)."""
    return {p.parent.name: p.parent for p in sorted(ROOT.glob("*/*/.tutor")) if p.is_dir() and not (p / "untracked").exists()}


def find_course(name: str) -> Path:
    cs, n = courses(), name.lower().strip()
    initials = {"".join(w[0] for w in c.split()).lower(): c for c in cs}  # "dbt", "dl", "mds"
    hits = [c for c in cs if c.lower() == n] or [c for c in cs if n in c.lower()] or ([initials[n]] if n in initials else [])
    if len(hits) != 1:
        sys.exit(f"Course '{name}' {'is ambiguous' if hits else 'not found'}. Courses: {', '.join(cs)}")
    return cs[hits[0]]


def read_rows(course_dir: Path) -> list:
    f = course_dir / ".tutor" / "progress.md"
    rows = []
    for line in f.read_text(encoding="utf-8").splitlines() if f.exists() else []:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 6 or cells[0] in ("Topic", "") or set(cells[0]) <= set("-: "):
            continue
        rows.append(dict(zip(["topic", "source", "status", "seen", "due", "notes"], cells[:5] + [" | ".join(cells[5:])])))
    return rows


def write_rows(course_dir: Path, rows: list):
    clean = lambda s: (s or NONE).replace("|", "/").replace("\n", " ")
    body = "".join(f"| {r['topic']} | {r['source']} | {r['status']} | {clean(r['seen'])} | {clean(r['due'])} | {clean(r['notes'])} |\n"
                   for r in rows)
    (course_dir / ".tutor" / "progress.md").write_text(HEADER + body, encoding="utf-8")
    render_overview(course_dir.parent)


def date(s: str):
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        return None


def cmd_pending(_):
    """Lecture files whose markdown exists but which index.md does not list yet."""
    found = False
    for name, course in courses().items():
        d = course / ".tutor"
        index = (d / "index.md").read_text(encoding="utf-8") if (d / "index.md").exists() else ""
        for src in sorted((course / "lectures").glob("*")):
            md = d / "md" / (src.stem + ".md")
            if src.suffix.lower() in (".pdf", ".ipynb") and md.exists() and md.name not in index:
                print(f"{name} | md/{md.name}")
                found = True
    if not found:
        print("No pending lectures.")


def cmd_add(a):
    course = find_course(a.course)
    rows = read_rows(course)
    known = {r["topic"].lower() for r in rows}
    added = 0
    for line in sys.stdin.read().splitlines():
        if "|" not in line:
            continue
        topic, source = (s.strip() for s in line.split("|", 1))
        if topic and topic.lower() not in known:
            rows.append({"topic": topic, "source": source, "status": "new", "seen": NONE, "due": NONE, "notes": NONE})
            known.add(topic.lower())
            added += 1
    write_rows(course, rows)
    print(f"{course.name}: {added} topics added as new ({len(rows)} total)")


def interleave(groups: list) -> list:
    """Round-robin over lists (one per course) so no course forms a long block."""
    out = []
    while any(groups):
        for g in groups:
            if g:
                out.append(g.pop(0))
    return out


def cmd_queue(a):
    cs = {find_course(a.course).name: find_course(a.course)} if a.course else courses()
    due, new, upcoming = [], [], []
    for name, course in cs.items():
        rows = [dict(r, course=name) for r in read_rows(course)]
        d = sorted((r for r in rows if r["status"] in TIERS and date(r["due"]) and date(r["due"]) <= TODAY),
                   key=lambda r: r["due"])
        due.append(d)
        new.append(sorted((r for r in rows if r["status"] == "new"), key=lambda r: order_key(r["source"])))
        upcoming += [r for r in rows if r["status"] in TIERS and date(r["due"]) and date(r["due"]) > TODAY]
    n_due, n_new = sum(map(len, due)), sum(map(len, new))
    oldest = sorted((r for d in due for r in d), key=lambda r: r["due"])[: a.max]
    reviews = interleave([[r for r in oldest if r["course"] == n] for n in cs])
    fresh = interleave(new)[: a.new]
    # spread new topics evenly between the reviews
    queue, step = list(reviews), max(1, len(reviews) // (len(fresh) + 1)) if fresh else 0
    for i, r in enumerate(fresh):
        queue.insert(min(len(queue), (i + 1) * step + i), r)
    print(f"Due: {n_due} (showing {len(reviews)}) | New: {n_new} available (showing {len(fresh)})")
    for i, r in enumerate(queue, 1):
        kind = "new" if r["status"] == "new" else f"review {r['status']}, due {r['due']}"
        print(f"{i}. [{kind}] {r['course']} | {r['topic']} | {r['source']} | note: {r['notes']}")
    if not queue:
        nxt = min(upcoming, key=lambda r: r["due"], default=None)
        print(f"Nothing due. Next: {nxt['course']} | {nxt['topic']} on {nxt['due']}" if nxt else "Nothing due and no topics tracked.")


def find_topic(rows: list, topic: str) -> dict:
    t = topic.lower().strip()
    hits = [r for r in rows if r["topic"].lower() == t] or [r for r in rows if t in r["topic"].lower()]
    if len(hits) != 1:
        sys.exit(f"Topic '{topic}' {'is ambiguous: ' + '; '.join(r['topic'] for r in hits) if hits else 'not found'}")
    return hits[0]


def cmd_grade(a):
    """Review ladder from AGENTS.md. pass promotes (only on/after Due; first-time learning caps at ok), partial = one tier down (new/repeat -> ok), fail = repeat."""
    course = find_course(a.course)
    rows = read_rows(course)
    r = find_topic(rows, a.topic)
    old = r["status"] if r["status"] in TIERS + ["new"] else "repeat"
    due = date(r["due"])
    on_time = due is None or due <= TODAY
    if a.result == "seen":  # explained by /tutor, not assessed
        if old == "new":
            r["status"], r["due"] = "repeat", TODAY.isoformat()
    elif a.result == "pass":
        if old == "new":
            r["status"] = "ok"
        elif on_time:
            r["status"] = TIERS[min(TIERS.index(old) + 1, len(TIERS) - 1)]
        if old == "new" or on_time:
            r["due"] = (TODAY + dt.timedelta(INTERVAL[r["status"]])).isoformat()
    elif a.result == "partial":  # needed one small hint/nudge: one tier down; new/repeat -> ok (repeat = retry later this session only)
        r["status"] = "ok" if old in ("new", "repeat") else TIERS[TIERS.index(old) - 1]
        r["due"] = (TODAY + dt.timedelta(max(1, INTERVAL[r["status"]]))).isoformat()
    else:  # fail: several follow-ups, slides/notes needed, or wrong: back to repeat
        r["status"] = "repeat"
        r["due"] = TODAY.isoformat()
    r["seen"] = TODAY.isoformat()
    if a.note:
        r["notes"] = a.note
    write_rows(course, rows)
    print(f"{course.name} | {r['topic']}: {old} -> {r['status']}, due {r['due']}")


def order_key(source: str) -> tuple:
    """(kind, lecture/sheet number, first slide) so topics follow the course order, lectures first."""
    kind = next((i for i, k in enumerate(("lecture", "book", "sheet")) if source.lower().startswith(k)), 3)
    nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", source)[:2]]
    return (kind, *nums, *[1e9] * (2 - len(nums)))


def lecture_of(source: str) -> str:
    m = re.match(r"\s*((?:Lecture|Sheet|Book ch\.?)\s*[\d.]+)", source, re.I)
    return m.group(1) if m else "Other"


def bar(counts: dict, total: int, cls: str = "bar") -> str:
    segs = "".join(f'<span class="seg {g}" style="flex:{counts[g]}" title="{g}: {counts[g]}"></span>'
                   for g in ("known", "learning", "new") if counts[g])
    return f'<div class="{cls}">{segs or EMPTY}</div>'


def donut(c: dict, n: int, big: bool = False) -> str:
    """CSS donut (conic-gradient): green known, blue learning, red new; centre shows % known."""
    if not n:
        return f'<div class="donut{" big" if big else ""}" style="background:var(--empty)"><span>–</span></div>'
    a, b = 100 * c["known"] / n, 100 * (c["known"] + c["learning"]) / n
    bg = f"conic-gradient(var(--known) 0 {a:.2f}%,var(--learning) {a:.2f}% {b:.2f}%,var(--new) {b:.2f}% 100%)"
    return f'<div class="donut{" big" if big else ""}" style="background:{bg}"><span>{round(a)}%</span></div>'


EMPTY = '<span class="seg empty" style="flex:1"></span>'


def count(rows: list) -> dict:
    c = {"new": 0, "learning": 0, "known": 0}
    for r in rows:
        c[GROUP.get(r["status"], "learning")] += 1
    return c


def render_overview(semester: Path) -> list:
    """Writes <semester>/overview.html from the progress.md of every course in that semester; returns summary lines."""
    cards, lines, total, due_all, data = [], [], {"new": 0, "learning": 0, "known": 0}, 0, []
    for name, d in courses().items():
        if d.parent != semester:
            continue
        rows = read_rows(d)
        c, n = count(rows), len(rows)
        due = sum(1 for r in rows if r["status"] in TIERS and date(r["due"]) and date(r["due"]) <= TODAY)
        due_all += due
        groups = {}
        for r in sorted(rows, key=lambda r: order_key(r["source"])):
            groups.setdefault(lecture_of(r["source"]), []).append(r)
        data.append({"course": name, "topics": n, "due": due, **c, "lectures": [
            {"name": g, "topics": len(rs), "due": sum(1 for r in rs if r["status"] in TIERS and date(r["due"]) and date(r["due"]) <= TODAY),
             **count(rs)} for g, rs in groups.items()]})
        for g in total:
            total[g] += c[g]
        lines.append(f"{name}: {n} topics | new {c['new']} · learning {c['learning']} · known {c['known']}"
                     + (f" ({round(100 * c['known'] / n)}% known)" if n else ""))
        body = ""
        for g, rs in groups.items():
            items = "".join(
                f'<li><span class="chip {GROUP.get(r["status"], "learning")}">{html.escape(r["status"])}</span>'
                f'<span class="topic">{html.escape(r["topic"])}</span>'
                f'<span class="meta">{html.escape(r["source"])}{" · due " + html.escape(r["due"]) if date(r["due"]) else ""}</span></li>'
                for r in rs)
            body += f'<div class="lec"><div class="lechead"><b>{html.escape(g)}</b>{bar(count(rs), len(rs), "bar small")}</div><ul>{items}</ul></div>'
        legend = "".join(f'<span class="item"><span class="dot {g}"></span>{g} {c[g]}</span>' for g in ("new", "learning", "known"))
        due_txt = f' · <b class="due">{due} due</b>' if due else ""
        cards.append(f'<details class="card"><summary><div class="row">{donut(c, n)}<div class="info"><div class="head"><h2>{html.escape(name)}</h2>'
                     f'<span class="count">{n} topics{due_txt}</span></div><div class="legend">{legend}</div></div></div></summary>'
                     f'{body or "<p class=meta>No topics yet. Run /sync to extract them from the lectures.</p>"}</details>')
    n_all = sum(total.values())
    pct = f"{round(100 * total['known'] / n_all)}% known" if n_all else "no topics yet"
    tl = "".join(f'<span class="item"><span class="dot {g}"></span>{g} {total[g]}</span>' for g in ("new", "learning", "known"))
    summary = (f'<div class="card total"><div class="row">{donut(total, n_all, True)}<div class="info"><div class="head"><h2>All courses</h2><span class="count">{n_all} topics · {pct}'
               + (f' · <b class="due">{due_all} due</b>' if due_all else "") + f'</span></div><div class="legend">{tl}</div></div></div></div>')
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    (semester / "overview.html").write_text(
        PAGE.replace("{DATE}", now).replace("{CARDS}", summary + "\n" + "\n".join(cards)), encoding="utf-8")
    payload = json.dumps({"updated": now, "due": due_all, **total, "courses": data}, ensure_ascii=False)
    targets = [WIDGET_DIR] if WIDGET_DIR.parent.is_dir() else []  # iCloud Drive present: feed the phone widget
    if sys.platform == "darwin":
        targets.append(LOCAL_WIDGET_DIR)
    for t in targets:
        t.mkdir(parents=True, exist_ok=True)
        (t / "progress.json").write_text(payload, encoding="utf-8")
    return lines


def cmd_overview(a):
    sems = sorted({d.parent for d in courses().values()})
    for sem in sems:
        print("\n".join(render_overview(sem)))
        print(f"Chart: {sem / 'overview.html'}")
    if a.open and sems:
        webbrowser.open((sems[0] / "overview.html").as_uri())


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="60"><title>Study Progress</title><style>
:root{--bg:#f6f7f9;--card:#fff;--fg:#1d2330;--muted:#6b7280;--line:#e5e7eb;--new:#dc2626;--learning:#2563eb;--known:#16a34a;--empty:#e5e7eb}
@media (prefers-color-scheme:dark){:root{--bg:#111318;--card:#1b1e25;--fg:#e8eaee;--muted:#9aa1ad;--line:#2c313a;--new:#ef4444;--learning:#3b82f6;--known:#22c55e;--empty:#2c313a}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:860px;margin:0 auto;padding:28px 16px}h1{font-size:22px;margin:0 0 4px}.sub{color:var(--muted);margin:0 0 20px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin-bottom:14px}
summary{cursor:pointer;list-style:none}summary::-webkit-details-marker{display:none}
.head{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:baseline;gap:2px 12px}h2{font-size:17px;margin:0}.count{color:var(--muted);font-size:13px}
.bar{display:flex;height:14px;border-radius:7px;overflow:hidden;margin:10px 0 8px;gap:2px;background:var(--empty)}
.bar.small{height:8px;margin:0;flex:1;max-width:260px}.seg.new{background:var(--new)}.seg.learning{background:var(--learning)}.seg.known{background:var(--known)}.seg.empty{background:var(--empty)}
.legend{font-size:13px;color:var(--muted);display:flex;flex-wrap:wrap;gap:4px 14px}.item{white-space:nowrap}.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px}
.dot.new{background:var(--new)}.dot.learning{background:var(--learning)}.dot.known{background:var(--known)}
details[open] summary{border-bottom:1px solid var(--line);padding-bottom:10px;margin-bottom:6px}
.lec{margin-top:12px}.lechead{display:flex;align-items:center;gap:12px;margin-bottom:4px}.lechead b{min-width:90px}
ul{list-style:none;margin:0;padding:0}li{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 10px;padding:5px 0;border-top:1px solid var(--line)}
.chip{font-size:12px;font-weight:600;padding:1px 8px;border-radius:9px;color:#fff;min-width:46px;text-align:center}
.chip.new{background:var(--new)}.chip.learning{background:var(--learning)}.chip.known{background:var(--known)}
.row{display:flex;align-items:center;gap:16px}.info{flex:1;min-width:0}.info .legend{margin-top:6px}
.donut{--s:60px;width:var(--s);height:var(--s);border-radius:50%;display:grid;place-items:center;flex:none}.donut.big{--s:96px}
.donut::before{content:"";grid-area:1/1;width:72%;height:72%;border-radius:50%;background:var(--card)}
.donut span{grid-area:1/1;font-size:13px;font-weight:700}.donut.big span{font-size:20px}
.due{color:var(--new)}.total{border-width:2px}
.topic{flex:1;min-width:200px}.meta{color:var(--muted);font-size:12.5px}
</style></head><body><main><h1>Study progress</h1><p class="sub">Updated {DATE} · reloads every minute · red = new, blue = learning (repeat/ok/good), green = known (strong/solid). Click a course to expand.</p>
{CARDS}
</main></body></html>
"""


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("pending")
    s = sub.add_parser("add"); s.add_argument("course")
    s = sub.add_parser("queue"); s.add_argument("course", nargs="?"); s.add_argument("--max", type=int, default=8); s.add_argument("--new", type=int, default=3)
    s = sub.add_parser("grade"); s.add_argument("course"); s.add_argument("topic"); s.add_argument("result", choices=["pass", "partial", "fail", "seen"]); s.add_argument("--note")
    s = sub.add_parser("overview"); s.add_argument("--open", action="store_true")
    a = p.parse_args()
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    globals()["cmd_" + a.cmd](a)


if __name__ == "__main__":
    main()
