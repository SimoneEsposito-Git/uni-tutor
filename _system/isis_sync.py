#!/usr/bin/env python3
"""Daily ISIS sync via browser session (no Moodle token needed).

Password comes from the macOS login keychain (entry "isis-sync"), never from a file:
  security add-generic-password -a "<user>" -s isis-sync -w
Session cookies are cached in session.json; a fresh login only happens when they expire.
  python3 isis_sync.py --login   # visible browser, for the first run or if login fails headless
  python3 isis_sync.py           # daily run (headless)
"""
import hashlib, json, re, subprocess, sys
from pathlib import Path
from urllib.parse import unquote

from playwright.sync_api import sync_playwright

from sync import CFG, MASTER, HERE, target_dir, to_markdown

BASE = CFG["moodle_url"].rstrip("/")
SESSION = HERE / "session.json"
STATE_F = HERE / "isis_state.json"
STATE = json.loads(STATE_F.read_text()) if STATE_F.exists() else {}
USER = CFG.get("username", "")


def password() -> str:
    r = subprocess.run(["security", "find-generic-password", "-s", "isis-sync", "-w"],
                       capture_output=True, text=True)
    if r.returncode:
        sys.exit("No keychain entry 'isis-sync'. Run: security add-generic-password -a \"$USER\" -s isis-sync -w")
    return r.stdout.strip()


def logged_in(page) -> bool:
    page.goto(f"{BASE}/my/", wait_until="domcontentloaded")
    return page.url.startswith(BASE) and page.locator("input[type=password]").count() == 0


def login(page, interactive: bool):
    page.goto(f"{BASE}/login/index.php", wait_until="domcontentloaded")
    # cookie/terms banner ("Fortsetzen"), then the "TU-Login" button leading to Shibboleth
    try:
        page.get_by_text("Fortsetzen", exact=True).locator("visible=true").first.click(timeout=3000)
    except Exception:
        pass  # banner not shown or already accepted
    page.get_by_role("link", name="TU-Login").or_(page.get_by_role("button", name="TU-Login")).first.click(timeout=15_000, force=True)
    page.wait_for_url(re.compile(r"shibboleth\.tubit\.tu-berlin\.de"), timeout=30_000)
    page.fill("input[type=text]", USER)
    page.fill("input[type=password]", password())
    page.keyboard.press("Enter")
    if interactive:
        print("Credentials entered; if the login doesn't finish, complete it in the window (5 min)...")
    page.wait_for_url(re.compile("^" + re.escape(BASE)), timeout=300_000 if interactive else 60_000)


def filename_of(resp, url: str) -> str:
    cd = resp.headers.get("content-disposition", "")
    m = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", cd)
    return unquote(m.group(1)) if m else unquote(url.split("?")[0].rsplit("/", 1)[-1])


def fetch(ctx, url: str, course_dir: Path, section: str, label: str, new: list):
    resp = ctx.request.get(url)
    if not resp.ok or "text/html" in resp.headers.get("content-type", ""):
        return  # page without a file (e.g. URL, label)
    body = resp.body()
    digest = hashlib.sha256(body).hexdigest()
    if STATE.get(url) == digest:
        return
    dest = target_dir(course_dir, section, label, "") / filename_of(resp, url)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.chmod(0o644)
    dest.write_bytes(body)
    dest.chmod(0o444)
    if dest.suffix.lower() == ".pdf":
        to_markdown(dest, course_dir / ".tutor")
    STATE[url] = digest
    new.append(dest.name)


def sync_course(page, ctx, c):
    course_dir = MASTER / c["semester"] / c["name"]
    for d in ("lectures", "exercises", "info", "solutions", "generated", ".tutor"):
        (course_dir / d).mkdir(parents=True, exist_ok=True)
    prog = course_dir / ".tutor" / "progress.md"
    if not prog.exists():
        prog.write_text("| Topic | Source | Status | Last seen | Notes |\n|---|---|---|---|---|\n")

    page.goto(f"{BASE}/course/view.php?id={c['id']}", wait_until="domcontentloaded")
    items = page.eval_on_selector_all(
        "li.section", """els => els.map(s => ({
            section: (s.querySelector('.sectionname, h3')||{}).innerText || '',
            links: [...s.querySelectorAll('a[href*="/mod/resource/"], a[href*="/mod/folder/"], a[href*="/mod/assign/"], a[href*="pluginfile.php"]')]
                     .map(a => ({href: a.href, text: a.innerText}))
        }))""")
    new = []
    for it in items:
        for l in it["links"]:
            href, label = l["href"], l["text"]
            if "/mod/folder/" in href or "/mod/assign/" in href:
                page.goto(href, wait_until="domcontentloaded")
                for f in page.eval_on_selector_all("a[href*='pluginfile.php']", "e => e.map(a => a.href)"):
                    fetch(ctx, f, course_dir, it["section"], label, new)
            else:
                fetch(ctx, href, course_dir, it["section"], label, new)
    print(f"{c['name']}: {len(new)} new/changed {new}")


def main():
    interactive = "--login" in sys.argv
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not interactive)
        ctx = browser.new_context(storage_state=str(SESSION) if SESSION.exists() else None)
        page = ctx.new_page()
        if not logged_in(page):
            login(page, interactive)
            ctx.storage_state(path=str(SESSION))
            SESSION.chmod(0o600)
        if not interactive:
            for c in CFG["courses"] or []:
                sync_course(page, ctx, c)
        browser.close()
    STATE_F.write_text(json.dumps(STATE, indent=1))
    if not interactive:
        has_todoist = subprocess.run(
            ["security", "find-generic-password", "-s", "todoist-sync", "-w"],
            capture_output=True
        ).returncode == 0
        if has_todoist:
            import todoist_sync
            todoist_sync.main()


if __name__ == "__main__":
    main()
