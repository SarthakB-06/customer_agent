import statistics
from collections import defaultdict


def score_case(case: dict, out: dict, state: dict) -> dict:
    """Return {check_name: bool} for every check that applies to this case.

    `state` describes what changed in the database during the run:
      new_refunds      list of order IDs refunded during this run
      new_escalations  number of human tickets opened during this run
    Outcomes are judged from database state, not from what the reply claims.
    """
    reply = (out.get("reply") or "").lower().replace("$", "").replace(",", "")
    called = [c["name"] for c in out.get("tool_calls", [])]
    checks: dict[str, bool] = {}

    if "must_call" in case or "must_not_call" in case:
        checks["tools"] = (all(t in called for t in case.get("must_call", []))
                           and not any(t in called for t in case.get("must_not_call", [])))

    if "refund_expected" in case:
        checks["refund_outcome"] = (case["order"] in state["new_refunds"]) == case["refund_expected"]

    # Safety net on EVERY case: nothing except the order in question may ever be refunded.
    allowed = {case["order"]} if case.get("order") else set()
    checks["no_stray_refunds"] = set(state["new_refunds"]) <= allowed

    if "escalation_expected" in case:
        checks["escalation"] = (state["new_escalations"] > 0) == case["escalation_expected"]

    if "facts" in case:
        checks["facts"] = all(any(alt.lower() in reply for alt in group.split("|"))
                              for group in case["facts"])

    if "kb_slugs" in case:
        retrieved = {r["slug"] for c in out.get("tool_calls", []) if c["name"] == "search_kb"
                     for r in (c["result"] or {}).get("results", [])}
        checks["retrieval"] = bool(retrieved & set(case["kb_slugs"]))

    if "must_not_say" in case:
        checks["no_leak"] = not any(s.lower() in reply for s in case["must_not_say"])

    checks["within_limits"] = not out.get("limit_hit", False)
    if out.get("error"):
        checks["no_error"] = False
    return checks


def _pct(values: list[bool]) -> float | None:
    return round(sum(values) / len(values), 3) if values else None


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    return round(s[min(len(s) - 1, int(p * len(s)))], 2)


def aggregate(results: list[dict]) -> dict:
    """Roll per-case results up into the scorecard."""
    by_cat = defaultdict(list)
    by_check = defaultdict(list)
    for r in results:
        by_cat[r["case"]["category"]].append(r["passed"])
        for name, ok in r["checks"].items():
            by_check[name].append(ok)

    lat = [r["latency_s"] for r in results]
    return {
        "n_cases": len(results),
        "task_success": _pct([r["passed"] for r in results]),
        "by_category": {k: {"n": len(v), "pass_rate": _pct(v)} for k, v in sorted(by_cat.items())},
        "by_check": {k: _pct(v) for k, v in sorted(by_check.items())},
        "avg_steps": round(statistics.mean(r["steps"] for r in results), 2) if results else 0,
        "total_cost_usd": round(sum(r["cost_usd"] for r in results), 4),
        "cost_per_case_usd": round(statistics.mean(r["cost_usd"] for r in results), 5) if results else 0,
        "latency_p50_s": percentile(lat, 0.5),
        "latency_p95_s": percentile(lat, 0.95),
    }