"""Seat watcher: checks UIUC Course Explorer and notifies when a watched section opens.

Only reads the public schedule page. It never logs in or registers.
Edit WATCH to change what is watched.
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

WATCH = [
    {"term": "2027/spring", "subject": "STAT", "number": "426", "crn": "72119"},
]
REMIND_EVERY = 30 * 60  # while still open, notify again at most this often (seconds)

HERE = Path(__file__).resolve().parent
STATE = HERE / "state.json"
LOG = HERE / "logs" / "watch.log"


def log(msg):
    LOG.parent.mkdir(exist_ok=True)
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + msg
    with LOG.open("a") as f:
        f.write(line + "\n")
    print(line)


def fetch_status(term, subject, number):
    url = f"https://courses.illinois.edu/schedule/{term}/{subject}/{number}"
    req = urllib.request.Request(url, headers={"User-Agent": "seatwatch (personal, every 5 min)"})
    html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
    out = {}
    for row in re.split(r"<tr[\s>]", html):
        crn = re.search(r"<div>(\d{5})</div>", row)
        av = re.search(r"Availability:</dt>\s*<dd>([^<]+)</dd>", row)
        if crn and av:
            out[crn.group(1)] = av.group(1).strip()
    return out, url


NTFY_TOPIC_FILE = HERE / "ntfy_topic.txt"  # phone push via the ntfy app (or NTFY_TOPIC env in GitHub Actions)


def push_phone(title, text):
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic and NTFY_TOPIC_FILE.exists():
        topic = NTFY_TOPIC_FILE.read_text().strip()
    if not topic:
        return
    req = urllib.request.Request(
        f"https://ntfy.sh/{topic}",
        data=text.encode(),
        headers={"Title": title, "Priority": "urgent", "Tags": "rotating_light"},
    )
    try:
        urllib.request.urlopen(req, timeout=15)
    except Exception as e:
        log(f"phone push failed: {e!r}")


def notify(title, text):
    script = f'display notification {json.dumps(text)} with title {json.dumps(title)} sound name "Glass"'
    if sys.platform == "darwin":
        subprocess.run(["osascript", "-e", script], check=False)
    push_phone(title, text)


def main():
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    pages = {}
    for w in WATCH:
        key = (w["term"], w["subject"], w["number"])
        if key not in pages:
            pages[key] = fetch_status(*key)
        statuses, url = pages[key]
        crn = w["crn"]
        status = statuses.get(crn)
        if status is None:
            log(f"{w['subject']} {w['number']} CRN {crn}: not found on page (layout changed?)")
            continue
        is_open = "Open" in status
        prev = state.get(crn, {})
        now = time.time()
        should_notify = is_open and (not prev.get("open") or now - prev.get("notified", 0) >= REMIND_EVERY)
        if should_notify:
            notify(f"{w['subject']} {w['number']} is open", f"CRN {crn}: {status}. Add it now.")
            prev["notified"] = now
        if status != prev.get("status"):
            log(f"{w['subject']} {w['number']} CRN {crn}: {prev.get('status')} -> {status}")
        prev.update({"status": status, "open": is_open, "checked": now})
        state[crn] = prev
    STATE.write_text(json.dumps(state, indent=2))


if __name__ == "__main__":
    if "--test-notify" in sys.argv:
        notify("seatwatch test", "Notifications work.")
    else:
        try:
            main()
        except Exception as e:  # keep the job alive; the next run retries
            log(f"error: {e!r}")
