import pytest

from app.config import get_settings
from app.tools import escalate, issue_refund, lookup_order, search_kb
from app.tools.kb import _load_kb

# Emails follow the seed pattern: firstname.lastname@example.com
AARAV = "aarav.mehta@example.com"      # customer 1, ORD-1001
PRIYA = "priya.nair@example.com"       # customer 2, ORD-1002
ROHAN = "rohan.kapoor@example.com"     # customer 3, ORD-1003
ANANYA = "ananya.iyer@example.com"     # customer 4, ORD-1004
SNEHA = "sneha.reddy@example.com"      # customer 6, ORD-1006


@pytest.fixture(autouse=True)
def fresh_env(tmp_path, monkeypatch):
    """Each test gets its own freshly seeded database and knowledge base."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("KB_DIR", str(tmp_path / "kb"))
    get_settings.cache_clear()
    _load_kb.cache_clear()

    from data import build_kb, seed_db
    seed_db.main()
    build_kb.main()
    yield
    get_settings.cache_clear()
    _load_kb.cache_clear()


def test_lookup_ok():
    r = lookup_order("ORD-1001", AARAV)
    assert r["ok"] and r["status"] == "delivered" and r["days_since_delivery"] == 5


def test_lookup_wrong_email_looks_like_not_found():
    r = lookup_order("ORD-1001", PRIYA)
    assert not r["ok"] and r["code"] == "not_found"


def test_lookup_unknown_order():
    assert lookup_order("ORD-9999", AARAV)["code"] == "not_found"


def test_refund_happy_path_and_no_double_refund():
    first = issue_refund("ORD-1001", AARAV, "Changed my mind")
    assert first["ok"] and first["refunded_usd"] == 49.99
    second = issue_refund("ORD-1001", AARAV, "Again")
    assert second["code"] == "already_refunded"


def test_refund_outside_window():
    assert issue_refund("ORD-1002", PRIYA, "late")["code"] == "outside_window"


def test_refund_over_limit_needs_human():
    assert issue_refund("ORD-1003", ROHAN, "defective")["code"] == "needs_human"


def test_refund_not_delivered():
    assert issue_refund("ORD-1004", ANANYA, "no")["code"] == "not_eligible"


def test_refund_already_refunded_in_seed():
    assert issue_refund("ORD-1006", SNEHA, "again")["code"] == "already_refunded"


def test_refund_wrong_email_refused():
    assert issue_refund("ORD-1001", PRIYA, "not mine")["code"] == "not_found"


def test_search_kb_finds_refund_limits():
    top = search_kb("what is the refund limit for the assistant")["results"][0]
    assert top["slug"] == "refund-limits"


def test_search_kb_no_match():
    assert search_kb("zzzz qqqq")["results"] == []


def test_escalate_creates_ticket():
    r = escalate("Over refund limit", order_id="ORD-1003")
    assert r["ok"] and r["ticket_id"] == "ESC-0001"