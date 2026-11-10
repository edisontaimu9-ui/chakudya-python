"""Read-only smoke test: calls every GET route that has no path parameter.
Usage:  CHAKUDYA_KEY="cnr_..." python examples/smoke.py"""
import os
import sys
import time

from chakudya import ChakudyaApiError, ChakudyaClient
from chakudya.client import _snake, _safe
from chakudya.routes import GENERATED_ROUTES

key = os.environ.get("CHAKUDYA_KEY")
if not key:
    sys.exit("Set CHAKUDYA_KEY first.")
cnr = ChakudyaClient(api_key=key)

jobs = [
    ("foods.list", lambda: cnr.foods.list()),
    ("foods.categories", lambda: cnr.foods.categories()),
    ("foods.search", lambda: cnr.foods.search(q="maize")),
    ("dri.list", lambda: cnr.dri.list(life_stage="female_19_30")),
    ("growth.assess", lambda: cnr.growth.assess(sex="female", age_months=12, weight_kg=9)),
]
done = {n for n, _ in jobs}
for ns, methods in GENERATED_ROUTES.items():
    for name, route in methods.items():
        if route.startswith("GET ") and "{" not in route and f"{ns}.{name}" not in done:
            attr = _safe(_snake(name))
            jobs.append((f"{ns}.{name}", lambda ns=ns, attr=attr: getattr(getattr(cnr, _safe(_snake(ns))), attr)()))

tally = dict(ok=0, needs_params=0, auth=0, skipped=0, bad=0)
for label, fn in jobs:
    try:
        fn()
        tally["ok"] += 1
    except ChakudyaApiError as e:
        if e.status in (400, 422):
            tally["needs_params"] += 1
        elif e.status in (401, 403):
            tally["auth"] += 1
            print("LOCK", label, e.status)
        elif e.status in (502, 503) and "openmrs" in label.lower():
            tally["skipped"] += 1
            print("SKIP", label, e.status, "(OpenMRS not reachable)")
        else:
            tally["bad"] += 1
            print("FAIL", label, e.status, e.message[:70])
    time.sleep(0.15)
print(f"\n{len(jobs)} routes: ok {tally['ok']} | needs params {tally['needs_params']} | "
      f"auth {tally['auth']} | skipped {tally['skipped']} | FAIL {tally['bad']}")
sys.exit(1 if tally["bad"] else 0)
