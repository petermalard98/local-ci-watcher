"""Local CI Watcher: live view of the self-hosted GitHub Actions runner in WSL.

Run inside WSL as the runner user:
    python3 watcher.py --runner-dir /home/runner/actions-runner [--port 8765]
"""
import argparse
import collections
import glob
import json
import os
import re
import threading
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

MAX_RUNS = 20
TAIL_LINES = 50
CONTEXT_KEYS = ("repository", "sha", "ref", "run_id", "run_number", "workflow")

STEP = re.compile(r"Processing step: DisplayName='(.*)'")
STEP_RESULT = re.compile(r"current step result '(\w+)'")
JOB_RESULT = re.compile(r"Job result after all job steps finish: (\w+)")
JOB_NAME = re.compile(r'"jobDisplayName": "(.*)"')
CTX_K = re.compile(r'"k": "(\w+)"')
CTX_V = re.compile(r'"v": "(.*)"')


def new_job(log_name):
    return {"id": log_name, "name": "", "status": "running", "steps": [], "tail": [],
            "started": time.time()}


def parse_lines(job, lines, state):
    """Feed worker-log lines into job. state carries the pending context key across calls."""
    for line in lines:
        if m := STEP.search(line):
            job["steps"].append({"name": m[1], "result": "running"})
        elif m := STEP_RESULT.search(line):
            if job["steps"]:
                job["steps"][-1]["result"] = m[1].lower()
        elif m := JOB_RESULT.search(line):
            job["status"] = m[1].lower()
        elif not job["name"] and (m := JOB_NAME.search(line)):
            job["name"] = m[1]
        elif m := CTX_K.search(line):
            state["k"] = m[1]
            continue
        elif (k := state.get("k")) in CONTEXT_KEYS and k not in job and (m := CTX_V.search(line)):
            job[k] = m[1]
        state["k"] = None
    if "repository" in job and "run_id" in job:
        job["url"] = f"https://github.com/{job['repository']}/actions/runs/{job['run_id']}"


class Watcher:
    def __init__(self, runner_dir):
        self.diag = os.path.join(runner_dir, "_diag")
        self.runs = collections.OrderedDict()
        self.version = 0
        self.cond = threading.Condition()
        self._log = None  # (path, offset, state)
        self._page = None  # (path, offset)

    def poll(self):
        changed = False
        logs = sorted(glob.glob(os.path.join(self.diag, "Worker_*.log")))
        if not self._log:  # first poll: load recent history
            for path in logs[-MAX_RUNS:-1]:
                job = self.runs[path] = new_job(os.path.basename(path))
                with open(path, encoding="utf-8", errors="replace") as f:
                    parse_lines(job, f.read().splitlines(), {})
                if job["status"] == "running":
                    job["status"] = "unknown"  # worker died before finishing
        if logs and (not self._log or self._log[0] != logs[-1]):
            path = logs[-1]
            self._log = [path, 0, {}]
            self.runs[path] = new_job(os.path.basename(path))
            while len(self.runs) > MAX_RUNS:
                self.runs.popitem(last=False)
        if self._log:
            path, offset, state = self._log
            job = self.runs[path]
            with open(path, encoding="utf-8", errors="replace") as f:
                f.seek(offset)
                data = f.read()
                self._log[1] = f.tell()
            if data:
                parse_lines(job, data.splitlines(), state)
                changed = True
            changed |= self._tail_page(job)
        if changed:
            with self.cond:
                self.version += 1
                self.cond.notify_all()

    def _tail_page(self, job):
        # Live step output sits in _diag/pages/*.log until uploaded.
        # ponytail: whole-line reads, a line split mid-write may show cut; fine for a live tail
        if job["status"] != "running":
            return False
        pages = glob.glob(os.path.join(self.diag, "pages", "*.log"))
        if not pages:
            return False
        path = max(pages, key=os.path.getmtime)
        if not self._page or self._page[0] != path:
            self._page = [path, 0]
        try:
            with open(path, encoding="utf-8-sig", errors="replace") as f:
                f.seek(self._page[1])
                data = f.read()
                self._page[1] = f.tell()
        except FileNotFoundError:
            return False
        if not data:
            return False
        job["tail"] = (job["tail"] + data.splitlines())[-TAIL_LINES:]
        return True

    def snapshot(self):
        return json.dumps(list(reversed(self.runs.values())))

    def loop(self):
        while True:
            try:
                self.poll()
            except OSError as e:
                print("poll error:", e)
            time.sleep(1)


def make_handler(watcher):
    page = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html"), "rb").read()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path == "/":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(page)
            elif self.path == "/events":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                seen = -1
                try:
                    while True:
                        with watcher.cond:
                            watcher.cond.wait_for(lambda: watcher.version != seen, timeout=15)
                            seen = watcher.version
                            body = watcher.snapshot()
                        self.wfile.write(f"data: {body}\n\n".encode())
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    pass
            else:
                self.send_error(404)

    return Handler


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--runner-dir", default="/home/runner/actions-runner")
    p.add_argument("--port", type=int, default=8765)
    a = p.parse_args()
    w = Watcher(a.runner_dir)
    threading.Thread(target=w.loop, daemon=True).start()
    print(f"Local CI Watcher on http://127.0.0.1:{a.port}")
    ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(w)).serve_forever()


if __name__ == "__main__":
    main()
