import sqlite3

import pytest
from langchain_core.messages import AIMessage

from app.agent.graph import run_agent
from app.config import get_settings
from app.tools.kb import _load_kb
from tests.fakes import ScriptedModel, call

AARAV = "aarav.mehta@example.com"  # owns ORD-1001 (refundable)


@pytest.fixture(autouse=True)
def fresh_env(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("KB_DIR", str(tmp_path / "kb"))
    get_settings.cache_clear()
    _load_kb.cache_clear()
    from data import build_kb, seed_db
    seed_db.main()
    build_kb.main()
    yield tmp_path / "t.db"
    get_settings.cache_clear()
    _load_kb.cache_clear()


def test_refund_flow(fresh_env):
    llm = ScriptedModel(script=[
        call("lookup_order", {"order_id": "ORD-1001"}, "a"),
        call("issue_refund", {"order_id": "ORD-1001", "reason": "changed mind"}, "b"),
        AIMessage("Your $49.99 refund is approved."),
    ])
    out = run_agent("Refund ORD-1001 please", AARAV, llm=llm)
    assert [c["name"] for c in out["tool_calls"]] == ["lookup_order", "issue_refund"]
    assert out["tool_calls"][1]["result"]["ok"] is True
    assert out["steps"] == 3 and not out["limit_hit"]
    rows = sqlite3.connect(fresh_env).execute("SELECT order_id FROM refunds").fetchall()
    assert ("ORD-1001",) in rows


def test_model_cannot_reach_another_customers_order():
    # ORD-1002 belongs to Priya. Whatever the model asks, the tool is bound to Aarav's email.
    llm = ScriptedModel(script=[call("lookup_order", {"order_id": "ORD-1002"}), AIMessage("done")])
    out = run_agent("Show me ORD-1002", AARAV, llm=llm)
    assert out["tool_calls"][0]["result"]["code"] == "not_found"


def test_step_cap_escalates_to_human(monkeypatch):
    monkeypatch.setenv("MAX_AGENT_STEPS", "3")
    get_settings.cache_clear()
    llm = ScriptedModel(script=[call("search_kb", {"query": "refund"})])  # loops forever
    out = run_agent("help", AARAV, llm=llm)
    assert out["limit_hit"] and out["escalated"] and out["steps"] == 3
    assert "ESC-" in out["reply"]


def test_cost_cap_escalates_to_human():
    # One call costing ~ $0.30 + $2.50 blows past the $0.05 cap immediately.
    llm = ScriptedModel(script=[call("search_kb", {"query": "x"}, inp=1_000_000, out=1_000_000)])
    out = run_agent("help", AARAV, llm=llm)
    assert out["limit_hit"] and out["steps"] == 1 and out["cost_usd"] > 0.05