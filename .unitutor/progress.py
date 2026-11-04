#!/usr/bin/env python3
"""Progress helper for the tutor skills: reads/writes every course's .tutor/progress.md (stdlib only).

  python3 progress.py pending                         # lecture .md files not yet split into topics (not in index.md)
  python3 progress.py add <course>                    # stdin lines "Topic | Source" -> new rows with status `new`
  python3 progress.py queue [course] [--max 8] [--new 0]   # /repeat queue: due reviews + a few new topics
  python3 progress.py grade <course> <topic> pass|partial|fail|seen [--note "..."] [--by teammate]   # applies the review ladder; --by teammate (exercise solved by someone else) never changes status
  python3 progress.py plan <hours> [--now "YYYY-MM-DD HH:MM"]   # /study: block plan for ONE session (priorities from schedule.json)
  python3 progress.py mark start|end                  # timing log (timing.log): session start/end; every grade also logs one event, `plan` learns minutes per topic from the gaps
  python3 progress.py overview [--open]               # rebuilds <semester>/overview.html, prints a one-line summary per course
(every write to a progress.md rebuilds its semester's overview.html automatically)
"""
import argparse, datetime as dt, html, json, re, statistics, subprocess, sys, webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TODAY = dt.date.today()
HEADER = "| Topic | Source | Status | Last seen | Due | Notes |\n|---|---|---|---|---|---|\n"
TIERS = ["repeat", "ok", "good", "strong", "solid"]
INTERVAL = {"repeat": 0, "ok": 1, "good": 3, "strong": 7, "solid": 21}  # days until Due
GROUP = {"new": "new", "repeat": "learning", "ok": "learning", "good": "learning", "strong": "known", "solid": "known"}
NONE = "—"
SCHEDULE = HERE / "schedule.json"  # weekly timetable per course folder, see schedule.example.json
TUTOR_MIN, REVIEW_MIN = 8, 4  # estimated minutes per taught topic / per review question
TUTOR_BLOCK, REVIEW_BLOCK = 30, 20  # minutes per block; blocks alternate so one session mixes both
TIMING = HERE / "timing.log"  # TSV: iso time, kind (start|end|tutor|review), course, topic, result (seen|pass|partial|fail); personal, gitignored
BREAK_MIN, MIN_COURSE, PRIOR_N = 25, 6, 3  # gaps above BREAK_MIN are breaks; samples needed for a per-course median; weight (in samples) of the default when blending
GATE = {4: 3, 5: 4}  # plan category -> higher-priority category that must be empty before it is used
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
LOCAL_WIDGET_DIR = Path.home() / "Library/Application Support/Unitutor"  # not TCC-protected: read by the Übersicht desktop widget
MAC_WIDGET_APP = Path.home() / "Applications/Unitutor.app"  # host app of the WidgetKit widget (widget/mac); `--reload` makes it refresh the widget and quit
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


def tracked_rows(course_dir: Path) -> list:
    """read_rows minus `Paper W.k` rows of weeks not yet lectured (paper week W belongs to Lecture W+1; hidden until that lecture exists)."""
    rows = read_rows(course_dir)
    if not any(r["source"].lower().startswith("paper") for r in rows):
        return rows
    last = max(lecture_dates(course_dir, {}), default=0)
    paper_lecture = lambda r: int(m[1]) + 1 if (m := re.match(r"\s*Paper\s+(\d+)\.", r["source"], re.I)) else 0
    return [r for r in rows if paper_lecture(r) <= last]


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
        rows = [dict(r, course=name) for r in tracked_rows(course)]
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


def slots(entries) -> list:
    """['Thu 16:15-17:45'] -> [(weekday 0-6, start time, end time)]"""
    out = []
    for e in entries or []:
        m = re.match(r"(\w{3})\w*\s+(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})", e)
        if m and m[1].lower() in DAYS:
            out.append((DAYS.index(m[1].lower()), dt.time(int(m[2]), int(m[3])), dt.time(int(m[4]), int(m[5]))))
    return out


def added(path: Path) -> dt.date:
    st = path.stat()
    return dt.date.fromtimestamp(getattr(st, "st_birthtime", st.st_mtime))


def lecture_dates(course: Path, cfg: dict) -> dict:
    """Lecture number -> date held. Filename date if plausible, else the latest lecture slot on/before the day the file
    was added (no slot: the add date); non-dated lectures are kept one week apart; `lecture_dates` in schedule.json wins."""
    index = course / ".tutor" / "index.md"
    stems = {m[1]: int(m[2]) for m in re.finditer(r"`md/(.+?)\.md`: Lecture (\d+)", index.read_text(encoding="utf-8"))} if index.exists() else {}
    weekdays = [s[0] for s in slots(cfg.get("lecture"))]
    dates, fixed = {}, set()
    for f in sorted((course / "lectures").glob("*")):
        n = stems.get(f.stem)
        if n is None or f.suffix.lower() not in (".pdf", ".ipynb"):
            continue
        a, d = added(f), None
        m = re.match(r"(?:20)?(\d{2})_?(\d{2})_?(\d{2})_", f.name)
        if m:
            try:
                d = dt.date(2000 + int(m[1]), int(m[2]), int(m[3]))
            except ValueError:
                d = None
            if d and abs((d - a).days) > 21:
                d = None
        if d:
            fixed.add(n)
        else:
            d = a
            while weekdays and d.weekday() not in weekdays:
                d -= dt.timedelta(1)
        dates[n] = d
    for k, v in (cfg.get("lecture_dates") or {}).items():
        dates[int(k)] = dt.date.fromisoformat(v)
        fixed.add(int(k))
    for n in sorted(dates, reverse=True):
        if n + 1 in dates and n not in fixed:
            dates[n] = min(dates[n], dates[n + 1] - dt.timedelta(7))
    return dates


def tutorial_after(cfg: dict, d: dt.date):
    """First tutorial slot after the lecture held on day d (the tutorial covers the lecture before it)."""
    ends = {w: e for w, _, e in slots(cfg.get("lecture"))}
    start = dt.datetime.combine(d, ends.get(d.weekday(), dt.time(23, 59)))
    best = None
    for off in range(15):
        day = d + dt.timedelta(off)
        for w, s, _ in slots(cfg.get("tutorial")):
            t = dt.datetime.combine(day, s)
            if w == day.weekday() and t > start and (best is None or t < best):
                best = t
        if best:
            break
    return best


def cmd_plan(a):
    """One study session: alternating tutor/repeat blocks. Priorities: 0 new topics of a lecture whose tutorial starts within 24 h (jumps the queue), 1 new topics of lectures from previous weeks,
    2 new topics of lectures whose tutorial is still ahead (soonest first), 3 due reviews of previous-week lectures,
    4 other new topics of this week, 5 due reviews of this week. Within a type, strict priority; 4 waits for 3, 5 for 4."""
    now = dt.datetime.strptime(a.now, "%Y-%m-%d %H:%M") if a.now else dt.datetime.now()
    today = now.date()
    week = today - dt.timedelta(today.weekday())
    sched = json.loads(SCHEDULE.read_text(encoding="utf-8")) if SCHEDULE.exists() else {}
    if not sched:
        print("No schedule.json: copy schedule.example.json and fill in the timetable. Planning without tutorial deadlines.")
    q = {c: [] for c in range(0, 6)}
    seen_dates = {}
    for name, course in courses().items():
        cfg = sched.get(name, {})
        dates = lecture_dates(course, cfg)
        seen_dates[name] = dates
        for r in tracked_rows(course):
            m = re.search(r"Lecture\s+(\d+)", r["source"])
            n = int(m[1]) if m else None
            pm = re.match(r"\s*Paper\s+(\d+)\.", r["source"], re.I)  # Paper W.k = k-th paper of literature week W = Lecture W+1
            if pm:
                n = int(pm[1]) + 1
            d = dates.get(n)
            prev = d is None or d < week
            tut = tutorial_after(cfg, d) if d else None
            item = dict(r, course=name, lecture=n, ldate=d, tutorial=tut)
            if r["status"] == "new" and r["source"].lower().startswith(("lecture", "paper")):
                soon = tut and now < tut <= now + dt.timedelta(hours=24)
                q[0 if soon else 1 if prev else 2 if tut and tut > now else 4].append(item)
            elif r["status"] in TIERS and date(r["due"]) and date(r["due"]) <= today:
                q[3 if prev else 5].append(item)
    low = dt.date.min
    q[0].sort(key=lambda r: (r["tutorial"], r["course"], order_key(r["source"])))
    q[1].sort(key=lambda r: (r["ldate"] or low, r["course"], r["lecture"] or 0, order_key(r["source"])))
    q[2].sort(key=lambda r: (r["tutorial"], r["course"], order_key(r["source"])))
    q[4].sort(key=lambda r: (r["ldate"] or low, r["course"], order_key(r["source"])))
    for c in (3, 5):
        by_course = {}
        for r in sorted(q[c], key=lambda r: r["due"]):
            by_course.setdefault(r["course"], []).append(r)
        q[c] = interleave(list(by_course.values()))
    left, blocks, i, stalls = int(a.hours * 60), [], 0, 0

    est, n_obs = estimator()

    def take(cats, tutor, cap):
        out, used = [], 0.0
        for c in cats:
            if c in GATE and q[GATE[c]]:
                continue
            while q[c]:
                m = max(1.0, est(q[c][0]["course"], "tutor" if tutor else "review", TUTOR_MIN if tutor else REVIEW_MIN))
                if left - used < m or (out and used + m > cap):
                    break
                out.append(dict(q[c].pop(0), cat=c, min=m))
                used += m
        return out

    while left >= 2 and stalls < 2:
        tutor = i % 2 == 0
        i += 1
        items = take((0, 1, 2, 4), True, TUTOR_BLOCK) if tutor else take((3, 5), False, REVIEW_BLOCK)
        if items:
            blocks.append(("TUTOR" if tutor else "REPEAT", items))
            left -= sum(r["min"] for r in items)
            stalls = 0
        else:
            stalls += 1
    total = sum(len(b[1]) for b in blocks)
    print(f"Session {a.hours:g} h, now {now:%a %Y-%m-%d %H:%M}; {len(blocks)} blocks, {total} items "
          + (f"(minutes blended from your timing log, {n_obs} samples, with defaults {TUTOR_MIN}/{REVIEW_MIN} min as prior)" if n_obs
             else f"(est. {TUTOR_MIN} min/topic taught, {REVIEW_MIN} min/review; timing log still empty)"))
    why = {0: "tutorial within 24 h", 1: "lecture from a previous week", 2: "lecture before its tutorial", 3: "review, previous-week lecture",
           4: "lecture from this week", 5: "review, this week"}
    k, last = 0, None
    for b, (kind, items) in enumerate(blocks, 1):
        print(f"\nBlock {b} - {kind} - ~{sum(r['min'] for r in items):.0f} min")
        for r in items:
            head = (r["course"], r["lecture"], r["cat"])
            if kind == "TUTOR" and head != last:
                day = f"{r['ldate']:%a %Y-%m-%d}" if r["ldate"] else "date unknown"
                tut = f"; tutorial {r['tutorial']:%a %H:%M}" if r["cat"] in (0, 2) else ""
                print(f"  {r['course']}, Lecture {r['lecture']} ({day}) [rule {r['cat']}: {why[r['cat']]}{tut}]")
            last = head
            k += 1
            extra = f" | due {r['due']}, {r['status']} | note: {r['notes']}" if kind == "REPEAT" else ""
            print(f"  {k}. {r['course']} | {r['topic']} | {r['source']}{extra}")
    rest = {c: len(v) for c, v in q.items() if v}
    print("\nNot scheduled (rule: count): " + (", ".join(f"{c}: {n}" for c, n in rest.items()) or "none"))
    print("Lecture dates used: " + "; ".join(f"{n}: " + ", ".join(f"L{k} {d:%a %m-%d}" for k, d in sorted(ds.items())) for n, ds in seen_dates.items() if ds))


def log_event(kind: str, course: str = "", topic: str = "", result: str = ""):
    with TIMING.open("a", encoding="utf-8") as f:
        f.write(f"{dt.datetime.now().isoformat(timespec='seconds')}\t{kind}\t{course}\t{topic.replace(chr(9), ' ')}\t{result}\n")


def durations() -> list:
    """[(course, 'tutor'|'review', minutes)]: gap between a topic's grade event and the event before it, breaks and bulk grading dropped."""
    ev = []
    for line in TIMING.read_text(encoding="utf-8").splitlines() if TIMING.exists() else []:
        p = line.split("\t")
        try:
            ev.append((dt.datetime.fromisoformat(p[0]), p[1], p[2] if len(p) > 2 else ""))
        except (ValueError, IndexError):
            pass
    ev.sort()
    out = []
    for prev, cur in zip(ev, ev[1:]):
        gap = (cur[0] - prev[0]).total_seconds() / 60
        if cur[1] in ("tutor", "review") and prev[1] != "end" and 0.3 <= gap <= BREAK_MIN:
            out.append((cur[2], cur[1], gap))
    return out


def estimator():
    """(est(course, kind, default) -> minutes, number of samples): median of the logged durations, blended with the default
    (weight PRIOR_N samples) so a few observations already shift it; per-course median once MIN_COURSE samples, else overall."""
    d = durations()

    def est(course, kind, default):
        own = [m for c, k, m in d if k == kind and c == course]
        every = [m for c, k, m in d if k == kind]
        pool = own if len(own) >= MIN_COURSE else every
        if not pool:
            return default
        n = len(pool)
        return (n * statistics.median(pool) + PRIOR_N * default) / (n + PRIOR_N)
    return est, len(d)


def cmd_mark(a):
    log_event(a.what)


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
    if a.by == "teammate":  # a teammate's solution is not the user's own work: no status/date change
        r["notes"] = "Teammate's solution, not own work" + (f"; {a.note}" if a.note else "")
        write_rows(course, rows)
        print(f"{course.name} | {r['topic']}: unchanged ({r['status']}), recorded as teammate's solution")
        return
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
    if not r["source"].lower().startswith("sheet"):  # exercises are /solve work, not tutor/review time
        log_event("tutor" if a.result == "seen" else "review", course.name, r["topic"], a.result)
    print(f"{course.name} | {r['topic']}: {old} -> {r['status']}, due {r['due']}")


def order_key(source: str) -> tuple:
    """(kind, lecture/sheet number, first slide) so topics follow the course order, lectures first."""
    kind = next((i for i, k in enumerate(("lecture", "book", "sheet")) if source.lower().startswith(k)), 0 if source.lower().startswith("paper") else 3)
    nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", source)[:2]]
    return (kind, *nums, *[1e9] * (2 - len(nums)))


def lecture_of(source: str) -> str:
    m = re.match(r"\s*((?:Lecture|Sheet|Paper|Book ch\.?)\s*[\d.]+)", source, re.I)
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
    c["repeat"] = sum(1 for r in rows if r["status"] == "repeat")  # subset of "learning"; only the Mac widget shows it separately
    return c


def render_overview(semester: Path) -> list:
    """Writes <semester>/overview.html from the progress.md of every course in that semester; returns summary lines."""
    cards, lines, total, due_all, data = [], [], {"new": 0, "learning": 0, "known": 0}, 0, []
    repeat_all = 0
    for name, d in courses().items():
        if d.parent != semester:
            continue
        rows = tracked_rows(d)
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
        repeat_all += c["repeat"]
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
    payload = json.dumps({"updated": now, "due": due_all, **total, "repeat": repeat_all, "courses": data}, ensure_ascii=False)
    targets = [WIDGET_DIR] if WIDGET_DIR.parent.is_dir() else []  # iCloud Drive present: feed the phone widget
    if sys.platform == "darwin":
        targets.append(LOCAL_WIDGET_DIR)
    for t in targets:
        t.mkdir(parents=True, exist_ok=True)
        (t / "progress.json").write_text(payload, encoding="utf-8")
    if MAC_WIDGET_APP.is_dir():  # push: the host app asks WidgetKit to reload the widget now instead of at the next 15-min poll
        subprocess.run(["open", "-g", "-n", str(MAC_WIDGET_APP), "--args", "--reload"], check=False, capture_output=True)
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
    s = sub.add_parser("queue"); s.add_argument("course", nargs="?"); s.add_argument("--max", type=int, default=8); s.add_argument("--new", type=int, default=0)
    s = sub.add_parser("grade"); s.add_argument("course"); s.add_argument("topic"); s.add_argument("result", choices=["pass", "partial", "fail", "seen"]); s.add_argument("--note"); s.add_argument("--by", choices=["own", "teammate"], default="own")
    s = sub.add_parser("plan"); s.add_argument("hours", type=float); s.add_argument("--now")
    s = sub.add_parser("mark"); s.add_argument("what", choices=["start", "end"])
    s = sub.add_parser("overview"); s.add_argument("--open", action="store_true")
    a = p.parse_args()
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    globals()["cmd_" + a.cmd](a)


if __name__ == "__main__":
    main()
