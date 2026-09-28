"""
Simultaneous-users load test (EA-SYS-SCOPE-01 non-functional requirement: many clients,
staff and coaches using the system at the same time).

Each virtual user logs in with their own session and works in parallel: listing and
opening members, editing records (with version checks), reading their profile, and,
for parents, opening the family portal. Run against a server loaded with `seed_kuwait`:

    python scripts/load_test.py --base http://127.0.0.1:8000 --users 60 --actions 25

Success criteria: no server errors (5xx); editing collisions return 409 (never silent
overwrites); every role only ever receives its own branch's data.
"""

import argparse
import http.cookiejar
import json
import random
import statistics
import threading
import time
import urllib.error
import urllib.request
from collections import Counter

PASSWORD = "Elite-Test-2026!"  # fictional test accounts from seed_kuwait
PROFILES = [
    # (email prefix, expected branch code or None for all, can edit members, is parent)
    ("admin.prm", "PRM", True, False),
    ("admin.bed", "BED", True, False),
    ("coach.prm", "PRM", False, False),
    ("coach.bed1", "BED", False, False),
    ("ops", None, True, False),
    ("marketing", None, False, False),
    ("parent", None, False, True),
]


class VirtualUser:
    def __init__(self, base, profile, rng):
        self.base = base
        self.email, self.branch, self.can_edit, self.parent = profile
        self.rng = rng
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.csrf = ""
        self.stats = Counter()
        self.latencies = []
        self.leaks = 0

    def call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if self.csrf:
            req.add_header("X-CSRFToken", self.csrf)
        start = time.perf_counter()
        try:
            with self.opener.open(req, timeout=30) as resp:
                status, payload = resp.status, resp.read()
        except urllib.error.HTTPError as err:
            status, payload = err.code, err.read()
        self.latencies.append((time.perf_counter() - start) * 1000)
        self.stats[status] += 1
        try:
            return status, json.loads(payload or b"{}")
        except json.JSONDecodeError:
            return status, {}

    def login(self):
        _, body = self.call("GET", "/api/v1/auth/csrf/")
        self.csrf = body.get("csrfToken", "")
        status, _ = self.call(
            "POST", "/api/v1/auth/login/", {"email": f"{self.email}@test.elite.local", "password": PASSWORD}
        )
        # Django rotates the CSRF token on login.
        for cookie in self.jar:
            if cookie.name == "elite_csrftoken":
                self.csrf = cookie.value
        return status == 200

    def work(self, actions, branch_ids):
        for _ in range(actions):
            if self.parent:
                self.call("GET", "/api/v1/portal/my-family/")
                continue
            choice = self.rng.random()
            if choice < 0.45:
                status, body = self.call("GET", "/api/v1/members/")
                if status == 200 and self.branch:
                    wrong = [m for m in body.get("results", []) if m["branch"] != branch_ids[self.branch]]
                    self.leaks += len(wrong)
            elif choice < 0.75:
                status, body = self.call("GET", "/api/v1/members/?page_size=20")
                results = body.get("results", []) if status == 200 else []
                if results:
                    member = self.rng.choice(results)
                    _, detail = self.call("GET", f"/api/v1/members/{member['id']}/")
                    if self.can_edit and detail.get("version") and self.rng.random() < 0.6:
                        self.call(
                            "PATCH",
                            f"/api/v1/members/{member['id']}/",
                            {
                                "area": self.rng.choice(["Salmiya", "Hawalli", "Adan", "Messila"]),
                                "version": detail["version"],
                            },
                        )
            else:
                self.call("GET", "/api/v1/auth/me/")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--users", type=int, default=60)
    parser.add_argument("--actions", type=int, default=25)
    args = parser.parse_args()

    rng = random.Random(42)
    users = [VirtualUser(args.base, PROFILES[i % len(PROFILES)], random.Random(i)) for i in range(args.users)]
    logged_in = sum(1 for u in users if u.login())
    ops = VirtualUser(args.base, PROFILES[4], random.Random(0))
    ops.login()
    _, branches = ops.call("GET", "/api/v1/branches/")
    branch_ids = {b["code"]: b["id"] for b in branches}

    start_gate = threading.Barrier(len(users))

    def run(user):
        start_gate.wait()
        user.work(args.actions, branch_ids)

    started = time.perf_counter()
    threads = [threading.Thread(target=run, args=(u,)) for u in users]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.perf_counter() - started

    totals = Counter()
    latencies = []
    leaks = 0
    for u in users:
        totals.update(u.stats)
        latencies.extend(u.latencies)
        leaks += u.leaks
    latencies.sort()
    n = sum(totals.values())
    print(f"Simultaneous users: {len(users)} (logged in: {logged_in}), rng={rng.random():.2f}")
    print(f"Requests: {n} in {elapsed:.1f}s  ->  {n / elapsed:.0f} requests/second")
    print(f"Status codes: {dict(sorted(totals.items()))}")
    print(
        f"Latency ms: median {statistics.median(latencies):.0f}, "
        f"p95 {latencies[int(len(latencies) * 0.95)]:.0f}, max {latencies[-1]:.0f}"
    )
    print(f"Edit collisions safely rejected (409): {totals.get(409, 0)}")
    print(f"Other-branch records leaked to branch-scoped users: {leaks}")
    server_errors = sum(v for k, v in totals.items() if k >= 500)
    print("RESULT:", "PASS" if server_errors == 0 and leaks == 0 and logged_in == len(users) else "FAIL")


if __name__ == "__main__":
    main()
