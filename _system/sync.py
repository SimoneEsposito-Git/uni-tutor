#!/usr/bin/env python3
"""Daily Moodle sync: download new/changed course files, sort them, convert PDFs to .md.

Needs MOODLE_TOKEN (Moodle mobile web service token) in the environment.
Optional MOODLE_ICS_URL: saved to _system/calendar.ics for calendar subscription.
"""
import hashlib, json, os, re, sys
from pathlib import Path
import requests, yaml

HERE = Path(__file__).parent
if sys.platform == "win32":  # console/log default to a legacy code page there
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
CFG_F = HERE / "config.yaml"
if not CFG_F.exists():
    sys.exit("Missing _system/config.yaml. Copy _system/config.example.yaml to _system/config.yaml first.")
CFG = yaml.safe_load(CFG_F.read_text(encoding="utf-8"))
ROOT = Path(CFG.get("root_dir") or CFG.get("master_dir") or HERE.parent).expanduser().resolve()
STATE_F = HERE / "state.json"
STATE = json.loads(STATE_F.read_text(encoding="utf-8")) if STATE_F.exists() else {}
TOKEN = os.environ.get(CFG["token_env"], "")
BASE = CFG["moodle_url"].rstrip("/")


def api(fn, **params):
    r = requests.get(f"{BASE}/webservice/rest/server.php", timeout=60,
                     params={"wstoken": TOKEN, "wsfunction": fn, "moodlewsrestformat": "json", **params})
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and "exception" in data:
        sys.exit(f"Moodle error: {data.get('message')}")
    return data


def target_dir(course_dir: Path, section: str, name: str, modname: str) -> Path:
    s = f"{section} {name}".lower()
    if modname == "assign" or re.search(r"übung|exercise|sheet|blatt|homework|assignment", s):
        return course_dir / "exercises"
    if re.search(r"lecture|vorlesung|slides|folien", s):
        return course_dir / "lectures"
    return course_dir / "info"


def to_markdown(pdf: Path, tutor_dir: Path):
    import fitz  # PyMuPDF
    out = tutor_dir / "md" / (pdf.stem + ".md")
    out.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open(pdf) as doc:
        out.write_text("\n\n".join(f"<!-- page {i+1} -->\n{p.get_text()}" for i, p in enumerate(doc)), encoding="utf-8")


def sync_course(c):
    course_dir = ROOT / c["semester"] / c["name"]
    tutor_dir = course_dir / ".tutor"
    for d in ("lectures", "exercises", "info", "solutions", "generated"):
        (course_dir / d).mkdir(parents=True, exist_ok=True)
    tutor_dir.mkdir(exist_ok=True)
    prog = tutor_dir / "progress.md"
    if not prog.exists():
        prog.write_text("| Topic | Source | Status | Last seen | Due | Notes |\n|---|---|---|---|---|---|\n", encoding="utf-8")

    new = []
    for section in api("core_course_get_contents", courseid=c["id"]):
        for mod in section.get("modules", []):
            for f in mod.get("contents", []):
                if f.get("type") != "file":
                    continue
                key = f"{c['id']}:{f['fileurl']}"
                sig = f"{f.get('timemodified')}:{f.get('filesize')}"
                if STATE.get(key) == sig:
                    continue
                dest = target_dir(course_dir, section["name"], mod["name"], mod["modname"]) / f["filename"]
                r = requests.get(f["fileurl"], params={"token": TOKEN}, timeout=120)
                r.raise_for_status()
                if dest.exists():
                    dest.chmod(0o644)
                dest.write_bytes(r.content)
                dest.chmod(0o444)  # protect originals
                if dest.suffix.lower() == ".pdf":
                    to_markdown(dest, tutor_dir)
                STATE[key] = sig
                new.append(dest.name)
    print(f"{c['name']}: {len(new)} new/changed {new}")


def sync_ics():
    url = os.environ.get(CFG.get("ics_url_env", ""), "")
    if url:
        (HERE / "calendar.ics").write_bytes(requests.get(url, timeout=60).content)
        print("calendar.ics updated (subscribe/import it in your calendar app)")


if __name__ == "__main__":
    if not TOKEN:
        sys.exit("Set MOODLE_TOKEN first.")
    for c in CFG["courses"] or []:
        sync_course(c)
    sync_ics()
    STATE_F.write_text(json.dumps(STATE, indent=1), encoding="utf-8")
