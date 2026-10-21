#!/usr/bin/env python3
"""Push upcoming Moodle calendar deadlines (calendar.ics) to Todoist, once per event.

Secrets live in the macOS keychain, never in files:
  security add-generic-password -a "$USER" -s todoist-sync -w   # Todoist API token
  security add-generic-password -a "$USER" -s isis-ics -w       # Moodle calendar export URL
"""
import json, re, subprocess, sys
from datetime import date, datetime, timezone

import requests
from icalendar import Calendar

from sync import CFG, HERE

API = "https://api.todoist.com/api/v1"
STATE_F = HERE / "todoist_state.json"
STATE = json.loads(STATE_F.read_text()) if STATE_F.exists() else {}


def keychain(service: str) -> str:
    r = subprocess.run(["security", "find-generic-password", "-s", service, "-w"], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"No keychain entry '{service}'.")
    return r.stdout.strip()


def ics_url() -> str:
    url = keychain("isis-ics")
    if "preset_time" not in url:
        url += "&preset_what=all&preset_time=recentupcoming"  # default range is only the current week
    return url


def fetch_ics(ics: bytes | None = None) -> Calendar:
    """ISIS now redirects the export to SSO login, so isis_sync passes the body fetched with its session."""
    if ics is None:
        r = requests.get(ics_url(), timeout=60)
        r.raise_for_status()
        ics = r.content
    if not ics.lstrip().startswith(b"BEGIN:VCALENDAR"):
        sys.exit("Todoist: calendar export returned a login page, not a calendar (run via isis_sync.py).")
    (HERE / "calendar.ics").write_bytes(ics)
    return Calendar.from_ical(ics)


def label_of(ev) -> str | None:
    """'[WiSe 2026/27] DBT' -> 'DBT' (Todoist label names can't contain spaces)."""
    cats = ev.get("CATEGORIES")
    cat = str(cats.cats[0]) if cats and cats.cats else ""
    name = re.sub(r"^\[[^\]]*\]\s*", "", cat).strip()
    return re.sub(r"\s+", "_", name) or None


def task_fields(ev) -> dict:
    body = {"content": str(ev.get("SUMMARY")), "description": str(ev.get("DESCRIPTION", ""))[:500]}
    label = label_of(ev)
    if label:
        body["labels"] = [label]
    return body


def main(ics: bytes | None = None):
    h = {"Authorization": f"Bearer {keychain('todoist-sync')}"}
    now = datetime.now(timezone.utc)
    added = 0
    cal = fetch_ics(ics)
    if "--relabel" in sys.argv:  # one-off: rewrite title/label of tasks already created
        for ev in cal.walk("VEVENT"):
            tid = STATE.get(str(ev.get("UID")))
            if tid:
                f = task_fields(ev)
                requests.post(f"{API}/tasks/{tid}", headers=h, json={"content": f["content"], "labels": f.get("labels", [])}, timeout=30).raise_for_status()
        print("relabelled")
        return
    for ev in cal.walk("VEVENT"):
        uid = str(ev.get("UID"))
        start = ev.decoded("DTSTART")
        if uid in STATE:
            continue
        is_dt = isinstance(start, datetime)
        if (start if is_dt else datetime.combine(start, datetime.min.time(), timezone.utc)) < now:
            continue
        body = task_fields(ev)
        if is_dt:
            body["due_datetime"] = start.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            body["due_date"] = start.isoformat()
        r = requests.post(f"{API}/tasks", headers=h, json=body, timeout=30)
        r.raise_for_status()
        STATE[uid] = r.json()["id"]
        added += 1
    STATE_F.write_text(json.dumps(STATE, indent=1))
    print(f"Todoist: {added} new tasks")


if __name__ == "__main__":
    main()
