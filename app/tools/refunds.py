from datetime import date

from app.config import get_settings
from app.db import connect
from app.tools.orders import get_verified_order


def issue_refund(order_id: str, customer_email: str, reason: str) -> dict:
    """Refund a full order. The model supplies WHICH order and WHY, never the amount:
    the amount comes from the database, and every policy rule is checked here in code.
    """
    settings = get_settings()

    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")  # lock so two concurrent calls can't double-refund

        order = get_verified_order(conn, order_id, customer_email)
        if order is None:
            return {"ok": False, "code": "not_found",
                    "error": "No order with that ID exists for that email."}

        if order["status"] != "delivered":
            return {"ok": False, "code": "not_eligible",
                    "error": f"Only delivered orders can be refunded. This order is '{order['status']}'."}

        if conn.execute("SELECT 1 FROM refunds WHERE order_id = ?", (order["id"],)).fetchone():
            return {"ok": False, "code": "already_refunded",
                    "error": "This order has already been refunded. Each order can be refunded once."}

        days = (settings.reference_date - date.fromisoformat(order["delivered_at"])).days
        if days > settings.return_window_days:
            return {"ok": False, "code": "outside_window",
                    "error": f"Delivered {days} days ago; the return window is "
                             f"{settings.return_window_days} days."}

        amount = order["total_usd"]
        if amount > settings.refund_limit_usd:
            return {"ok": False, "code": "needs_human",
                    "error": f"Refunds above ${settings.refund_limit_usd:.0f} need human review. "
                             "Escalate this case."}

        conn.execute(
            "INSERT INTO refunds (order_id, amount_usd, reason, created_at) VALUES (?, ?, ?, ?)",
            (order["id"], amount, reason.strip()[:500], settings.reference_date.isoformat()),
        )

    return {"ok": True, "order_id": order["id"], "refunded_usd": amount,
            "message": "Refund approved. It will reach the original payment method in 5-7 business days."}