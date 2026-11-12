"""Run the eval suite.

  python -m evals.runner                      # full run against the real LLM
  python -m evals.runner --retrieval-only     # no LLM: just measure search_kb quality
  python -m evals.runner --category adversarial --limit 5 --sleep 4
  python -m evals.runner --fail-under 0.85    # exit code 1 if task success is lower (for CI)
"""
import argparse
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

from app.agent.graph import run_agent
from app.config import get_settings
from app.tools import search_kb
from app.tools.kb import _load_kb
from evals.metrics import aggregate, score_case

DATASET = Path(__file__).parent / "dataset.jsonl"
RESULTS_DIR = Path(__file__).parent / "results"


def load_dataset(path: Path = DATASET) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _db_state(db_path: str) -> tuple[set, int]:
    conn = sqlite3.connect(db_path)
    refunds = {r[0] for r in conn.execute("SELECT order_id FROM refunds")}
    try:
        esc = conn.execute("SELECT COUNT(*) FROM escalations").fetchone()[0]
    except sqlite3.OperationalError:  # table is created lazily by the first escalation
        esc = 0
    conn.close()
    return refunds, esc


def run_case(case: dict, template_db: str, llm=None, retries: int = 2) -> dict:
    """Run one case on its own private copy of the database, then score it."""
    workdir = tempfile.mkdtemp()
    db_copy = os.path.join(workdir, "case.db")
    shutil.copy(template_db, db_copy)
    os.environ["DB_PATH"] = db_copy
    get_settings.cache_clear()

    refunds_before, esc_before = _db_state(db_copy)
    out, started = None, time.perf_counter()
    for attempt in range(retries + 1):
        try:
            out = run_agent(case["message"], case["email"], llm=llm)
            break
        except Exception as e:  # API hiccups / rate limits: back off and retry
            out = {"reply": "", "tool_calls": [], "steps": 0, "cost_usd": 0.0,
                   "limit_hit": False, "error": f"{type(e).__name__}: {e}"}
            time.sleep(2 ** attempt * 2)
    latency = time.perf_counter() - started

    refunds_after, esc_after = _db_state(db_copy)
    state = {"new_refunds": sorted(refunds_after - refunds_before),
             "new_escalations": esc_after - esc_before}
    shutil.rmtree(workdir, ignore_errors=True)

    checks = score_case(case, out, state)
    return {"case": case, "checks": checks, "passed": all(checks.values()),
            "latency_s": round(latency, 2), "steps": out["steps"], "cost_usd": out["cost_usd"],
            "reply": out["reply"], "error": out.get("error"), "state": state,
            "tool_calls": [{"name": c["name"], "args": c["args"]} for c in out["tool_calls"]]}


def retrieval_eval(cases: list[dict], k: int = 3) -> dict:
    """Score search_kb alone (no LLM): is an expected article in the top k for the raw question?"""
    rows = []
    for c in (c for c in cases if "kb_slugs" in c):
        slugs = [r["slug"] for r in search_kb(c["message"], k=k)["results"]]
        hit = next((i for i, s in enumerate(slugs) if s in c["kb_slugs"]), None)
        rows.append({"id": c["id"], "query": c["message"], "expected": c["kb_slugs"],
                     "got": slugs, "hit": hit is not None, "rr": 1 / (hit + 1) if hit is not None else 0})
    return {"k": k, "n": len(rows),
            f"recall@{k}": round(sum(r["hit"] for r in rows) / len(rows), 3),
            "mrr": round(sum(r["rr"] for r in rows) / len(rows), 3),
            "misses": [r for r in rows if not r["hit"]]}


def print_scorecard(agg: dict, results: list[dict]) -> None:
    print(f"\n=== Scorecard ({agg['n_cases']} cases) ===")
    print(f"Task success: {agg['task_success']:.1%}")
    print("\n| Category | n | pass |\n|---|---|---|")
    for cat, v in agg["by_category"].items():
        print(f"| {cat} | {v['n']} | {v['pass_rate']:.0%} |")
    print("\n| Check | pass |\n|---|---|")
    for name, rate in agg["by_check"].items():
        print(f"| {name} | {rate:.0%} |")
    print(f"\nAvg steps {agg['avg_steps']} | cost/case ${agg['cost_per_case_usd']} "
          f"(total ${agg['total_cost_usd']}) | latency p50 {agg['latency_p50_s']}s, p95 {agg['latency_p95_s']}s")
    failures = [r for r in results if not r["passed"]]
    if failures:
        print(f"\nFailures ({len(failures)}):")
        for r in failures:
            bad = [k for k, v in r["checks"].items() if not v]
            print(f"  {r['case']['id']}: failed {bad}" + (f"  [{r['error']}]" if r["error"] else ""))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--category")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--sleep", type=float, default=0, help="seconds between cases (rate limits)")
    ap.add_argument("--label", default="run", help="name for the results file, e.g. 'baseline'")
    ap.add_argument("--retrieval-only", action="store_true")
    ap.add_argument("--fail-under", type=float)
    args = ap.parse_args()

    cases = load_dataset()
    if args.category:
        cases = [c for c in cases if c["category"] == args.category]
    if args.limit:
        cases = cases[: args.limit]

    # Fresh, deterministic database + KB for the whole run (each case then gets its own copy).
    from data import build_kb, seed_db
    template_dir = tempfile.mkdtemp()
    os.environ["DB_PATH"] = os.path.join(template_dir, "template.db")
    get_settings.cache_clear()
    seed_db.main()
    template_db = os.environ["DB_PATH"]
    if not any(get_settings().kb_dir.glob("*.md")):
        build_kb.main()
    _load_kb.cache_clear()

    if args.retrieval_only:
        r = retrieval_eval(cases)
        print(json.dumps({k: v for k, v in r.items() if k != "misses"}, indent=2))
        for m in r["misses"]:
            print(f"  MISS {m['id']}: {m['query']!r}\n       expected {m['expected']} got {m['got']}")
        return

    results = []
    for i, case in enumerate(cases, 1):
        res = run_case(case, template_db)
        results.append(res)
        print(f"[{i}/{len(cases)}] {case['id']:<14} {'PASS' if res['passed'] else 'FAIL'}", flush=True)
        if args.sleep:
            time.sleep(args.sleep)

    agg = aggregate(results)
    print_scorecard(agg, results)

    RESULTS_DIR.mkdir(exist_ok=True)
    path = RESULTS_DIR / f"{args.label}-{datetime.now():%Y%m%d-%H%M%S}.json"
    path.write_text(json.dumps({"summary": agg, "model": get_settings().llm_model,
                                "results": results}, indent=2), encoding="utf-8")
    print(f"\nSaved {path}")
    if args.fail_under is not None and (agg["task_success"] or 0) < args.fail_under:
        sys.exit(1)


if __name__ == "__main__":
    main()