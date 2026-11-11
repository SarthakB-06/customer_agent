from datetime import datetime, timezone

from app.db import connect


def escalate(reason: str, order_id: str | None = None) -> dict:
    """Hand the case to a human specialist and record why."""
    with connect() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS escalations (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   order_id TEXT,
                   reason TEXT NOT NULL,
                   created_at TEXT NOT NULL)"""
        )
        cur = conn.execute(
            "INSERT INTO escalations (order_id, reason, created_at) VALUES (?, ?, ?)",
            (order_id, reason.strip()[:500], datetime.now(timezone.utc).isoformat()),
        )
        ticket = f"ESC-{cur.lastrowid:04d}"

    return {"ok": True, "ticket_id": ticket,
            "message": "A human specialist will contact the customer within 1 business day."}