#!/usr/bin/env python3
"""Daily Moodle sync via browser session (no Moodle token needed). Works with plain Moodle logins and SSO.

The password comes from the OS credential store, never from a file (python keystore.py set password).
Session cookies are cached in session.json; a fresh login only happens when they expire.
  python moodle_sync.py --login   # visible browser, for the first run or if login fails headless
  python moodle_sync.py           # daily run (headless)
"""
import hashlib, json, re, shutil, subprocess, sys
from pathlib import Path
from urllib.parse import unquote, urljoin

import requests
from playwright.sync_api import sync_playwright

import keystore
from sync import CFG, ROOT, HERE, target_dir, to_markdown

BASE = CFG["moodle_url"].rstrip("/")
LOGIN = CFG.get("login") or {}
SESSION = HERE / "session.json"
STATE_F = HERE / "moodle_state.json"
if not STATE_F.exists() and (HERE / "isis_state.json").exists():  # pre-rename name
    (HERE / "isis_state.json").rename(STATE_F)
STATE = json.loads(STATE_F.read_text(encoding="utf-8")) if STATE_F.exists() else {}
USER = CFG.get("username", "")


def safe_name(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", name).strip().rstrip(".")  # also valid on Windows


def logged_in(page) -> bool:
    page.goto(f"{BASE}/my/", wait_until="domcontentloaded")
    return page.url.startswith(BASE) and page.locator("input[type=password]").count() == 0


def leave_login_page(page):
    """On Moodle's login page: accept the consent banner, then follow the SSO button if configured."""
    if LOGIN.get("consent_button"):  # cookie/terms banner
        try:
            page.get_by_text(LOGIN["consent_button"], exact=True).locator("visible=true").first.click(timeout=3000)
        except Exception:
            pass  # banner not shown or already accepted
    if LOGIN.get("sso_button"):  # button on the Moodle login page leading to the university SSO
        name = LOGIN["sso_button"]
        page.get_by_role("link", name=name).or_(page.get_by_role("button", name=name)).first.click(timeout=15_000, force=True)


def login(page, interactive: bool):
    on_moodle_page = lambda u: u.startswith(BASE) and "/login/" not in u
    page.goto(f"{BASE}/login/index.php", wait_until="load")
    if page.url.startswith(BASE):  # some sites redirect straight to the identity provider
        leave_login_page(page)
        if LOGIN.get("sso_button"):
            page.wait_for_url(lambda u: not u.startswith(BASE), timeout=30_000)
    # works for Moodle's own form and typical SSO forms: first visible text/email field + password field.
    # Wait for it first: identity providers often pass through interstitial redirect pages.
    pw = page.locator("input[type=password]:visible").first
    pw.wait_for(timeout=30_000)
    page.locator("input[type=text]:visible, input[type=email]:visible, input:not([type]):visible").first.fill(USER)
    pw.fill(keystore.require("password"))
    page.keyboard.press("Enter")
    if interactive:
        print("Credentials entered; if the login doesn't finish, complete it in the window (5 min)...")
    timeout = 300_000 if interactive else 60_000
    page.wait_for_url(re.compile("^" + re.escape(BASE)), timeout=timeout)
    if not on_moodle_page(page.url):
        # Back on the login page: with SSO, Moodle may first want its consent banner accepted;
        # the identity provider session now exists, so the second SSO round trip needs no password.
        if not LOGIN.get("sso_button") and not interactive:
            sys.exit("Login failed: still on the Moodle login page (wrong username or password?).")
        page.wait_for_load_state("load")
        leave_login_page(page)
        page.wait_for_url(on_moodle_page, timeout=timeout)


def filename_of(resp, url: str) -> str:
    cd = resp.headers.get("content-disposition", "")
    m = re.search(r"filename\*?=(?:UTF-8'')?\"?([^\";]+)", cd)
    return safe_name(unquote(m.group(1)) if m else unquote(url.split("?")[0].rsplit("/", 1)[-1]))


def fetch(ctx, url: str, course_dir: Path, section: str, label: str, new: list):
    resp = ctx.request.get(url)
    if not resp.ok or "text/html" in resp.headers.get("content-type", ""):
        return  # page without a file (e.g. URL, label)
    body = resp.body()
    digest = hashlib.sha256(body).hexdigest()
    if STATE.get(url) == digest:
        return
    fname = filename_of(resp, url)
    dest = target_dir(course_dir, section, label, "", fname) / fname
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.chmod(0o644)
    dest.write_bytes(body)
    dest.chmod(0o444)
    if dest.suffix.lower() == ".pdf":
        to_markdown(dest, course_dir / ".tutor")
    elif dest.suffix.lower() == ".ipynb":
        ipynb_to_markdown(dest, course_dir / ".tutor")
    STATE[url] = digest
    new.append(dest.name)


def ipynb_to_markdown(nb: Path, tutor_dir: Path):
    cells = json.loads(nb.read_text(encoding="utf-8"))["cells"]
    out = tutor_dir / "md" / (nb.stem + ".md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n\n".join(
        "".join(c["source"]) if c["cell_type"] != "code" else "```python\n" + "".join(c["source"]) + "\n```"
        for c in cells), encoding="utf-8")


def fetch_videos(page, ctx, cmid: str, course_dir: Path, section: str, label: str, new: list):
    """All videos of a videoservice collection (Moodle plugin used e.g. by TU Berlin's ISIS). Their URLs are content hashes, so a known URL is unchanged."""
    resp = ctx.request.post(
        f"{BASE}/lib/ajax/service.php?sesskey={page.evaluate('M.cfg.sesskey')}&info=mod_videoservice_get_videos",
        data=json.dumps([{"index": 0, "methodname": "mod_videoservice_get_videos",
                          "args": {"coursemoduleid": cmid, "courseid": 0}}]),
        headers={"Content-Type": "application/json"})
    res = resp.json()[0]
    if res.get("error"):
        print(f"  videos {cmid}: {res.get('exception', {}).get('message', 'error')}")
        return
    cookies = {c["name"]: c["value"] for c in ctx.cookies(BASE)}
    for v in res["data"]["videos"]:
        if v["url"] in STATE:
            continue
        # recordings are lectures, whatever the collection is called
        dest = course_dir / "lectures" / safe_name(v["title"] + v["fileext"])
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(dest.name + ".part")
        with requests.get(v["url"], cookies=cookies, stream=True, timeout=120) as r:  # streamed: files are large
            r.raise_for_status()
            with open(part, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        if dest.exists():
            dest.chmod(0o644)
        part.replace(dest)
        dest.chmod(0o444)
        STATE[v["url"]] = "video"
        new.append(dest.name)


def fetch_jupyter_book(ctx, start: str, course_dir: Path, section: str, label: str, new: list):
    """Crawl a Jupyter Book site (e.g. DBT exercises) and download each chapter's source (.ipynb/.md)."""
    root = start.rsplit("/", 1)[0] + "/"
    todo, seen, sources = [start], set(), set()
    while todo and len(seen) < 200:
        url = todo.pop()
        if url in seen:
            continue
        seen.add(url)
        resp = ctx.request.get(url)
        if not resp.ok or "text/html" not in resp.headers.get("content-type", ""):
            continue
        for href in re.findall(r'href="([^"#]+)', resp.text()):
            link = urljoin(url, href)
            if not link.startswith(root):
                continue
            if "/_sources/" in link and link not in sources:
                sources.add(link)
                fetch(ctx, link, course_dir, section, label, new)
            elif link.endswith(".html"):
                todo.append(link)


def follow_url(page, ctx, href: str, course_dir: Path, section: str, label: str, new: list, done: set):
    """mod/url: resolve the target and handle it if it holds files we know how to get."""
    resp = ctx.request.get(href, max_redirects=0)
    target = resp.headers.get("location")
    if not target:  # embedded/framed display: link is in the page body
        m = re.search(r'class="urlworkaround".*?href="([^"]+)"', resp.text(), re.S)
        target = m and m.group(1).replace("&amp;", "&")
    if not target or target in done:
        return
    done.add(target)
    if m := re.search(r"/mod/videoservice/view\.php/cm/(\d+)", target):
        if m.group(1) not in done:
            done.add(m.group(1))
            fetch_videos(page, ctx, m.group(1), course_dir, section, label, new)
    elif target.startswith(BASE):
        if "pluginfile.php" in target:
            fetch(ctx, target, course_dir, section, label, new)
    else:
        resp = ctx.request.get(target)
        if m := re.search(r'http-equiv="refresh"[^>]*url=([^"\'>]+)', resp.text(), re.I):  # HTML redirect
            resp = ctx.request.get(urljoin(resp.url, m.group(1).strip()))
        if resp.ok and 'href="_sources/' in resp.text():
            fetch_jupyter_book(ctx, resp.url, course_dir, section, label, new)


def sync_course(page, ctx, c):
    course_dir = ROOT / c["semester"] / c["name"]
    for d in ("lectures", "exercises", "info", "solutions", "generated", ".tutor"):
        (course_dir / d).mkdir(parents=True, exist_ok=True)
    prog = course_dir / ".tutor" / "progress.md"
    if not prog.exists() and not (prog.parent / "untracked").exists():
        prog.write_text("| Topic | Source | Status | Last seen | Due | Notes |\n|---|---|---|---|---|---|\n", encoding="utf-8")

    page.goto(f"{BASE}/course/view.php?id={c['id']}", wait_until="domcontentloaded")
    items = page.eval_on_selector_all(
        "li.section", """els => els.map(s => ({
            section: (s.querySelector('.sectionname, h3')||{}).innerText || '',
            links: [...s.querySelectorAll('a[href*="/mod/resource/"], a[href*="/mod/folder/"], a[href*="/mod/assign/"], a[href*="/mod/page/"], a[href*="/mod/url/"], a[href*="/mod/videoservice/"], a[href*="pluginfile.php"]')]
                     .map(a => ({href: a.href, text: a.innerText}))
        }))""")
    new, done = [], set()
    skip = c.get("skip_folders")  # per-course regex on folder labels that are organised by hand (e.g. literature/)
    for it in items:
        for l in it["links"]:
            href, label = l["href"], l["text"]
            if skip and "/mod/folder/" in href and re.search(skip, label, re.I):
                continue
            if "/mod/url/" in href:
                if href not in done:
                    done.add(href)
                    follow_url(page, ctx, href, course_dir, it["section"], label, new, done)
            elif m := re.search(r"/mod/videoservice/view\.php\?id=(\d+)", href):
                if m.group(1) not in done:
                    done.add(m.group(1))
                    fetch_videos(page, ctx, m.group(1), course_dir, it["section"], label, new)
            elif "/mod/folder/" in href or "/mod/assign/" in href or "/mod/page/" in href:
                page.goto(href, wait_until="domcontentloaded")
                for f in page.eval_on_selector_all("a[href*='pluginfile.php']", "e => e.map(a => a.href)"):
                    fetch(ctx, f, course_dir, it["section"], label, new)
            else:
                fetch(ctx, href, course_dir, it["section"], label, new)
    print(f"{c['name']}: {len(new)} new/changed {new}")
    return new


def notify(msg: str):
    """Desktop notification; silently skipped where no notifier is available."""
    if sys.platform == "darwin":
        msg = msg.replace("\\", "\\\\").replace('"', '\\"')
        subprocess.run(["osascript", "-e", f'display notification "{msg}" with title "Uni sync"'])
    elif sys.platform == "win32":
        msg = msg.replace("'", "''")
        ps = ("[Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime]>$null;"
              "$t=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(1);"  # ToastText02
              "$x=$t.GetElementsByTagName('text');$x[0].InnerText='Uni sync';"
              f"$x[1].InnerText='{msg}';"
              "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("
              "'{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\\WindowsPowerShell\\v1.0\\powershell.exe')"
              ".Show([Windows.UI.Notifications.ToastNotification]::new($t))")
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True)
    elif shutil.which("notify-send"):
        subprocess.run(["notify-send", "Uni sync", msg])


def hide_tool_files():
    """Explorer shows dot folders, unlike Finder; re-applied each run so it also covers fresh clones."""
    root = HERE.parent
    if sys.platform == "win32":
        for n in [".unitutor", ".claude", ".agents", ".github", ".gitignore", ".gitattributes"]:
            # attrib takes one path per call
            if (root / n).exists():
                subprocess.run(["attrib", "+h", str(root / n)], capture_output=True)


def main():
    hide_tool_files()
    interactive = "--login" in sys.argv
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not interactive)
        ctx = browser.new_context(storage_state=str(SESSION) if SESSION.exists() else None)
        page = ctx.new_page()
        if not logged_in(page):
            login(page, interactive)
            ctx.storage_state(path=str(SESSION))
            SESSION.chmod(0o600)
        has_todoist = keystore.get("todoist") is not None
        ics = None
        if not interactive:
            added = {}
            for c in CFG["courses"] or []:
                if new := sync_course(page, ctx, c):
                    added[c["name"]] = new
            if has_todoist:
                import todoist_sync
                ics = ctx.request.get(todoist_sync.ics_url()).body()  # some sites need the Moodle session
        browser.close()
    STATE_F.write_text(json.dumps(STATE, indent=1), encoding="utf-8")
    if not interactive and added:
        notify("; ".join(f"{k}: {', '.join(v[:3])}" + (f" +{len(v) - 3}" if len(v) > 3 else "") for k, v in added.items()))
    if ics is not None:
        todoist_sync.main(ics)


if __name__ == "__main__":
    main()
