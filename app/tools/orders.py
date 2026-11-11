from datetime import date

from app.config import get_settings
from app.db import connect


def get_verified_order(conn, order_id: str, customer_email: str):
    """Return the order row only if it belongs to the customer with this email.

    A wrong email and a nonexistent order look identical to the caller, so the tool
    can't be used to probe which order IDs exist (an IDOR-style attack).
    """
    return conn.execute(
        """
        SELECT o.* FROM orders o
        JOIN customers c ON c.id = o.customer_id
        WHERE o.id = ? AND lower(c.email) = lower(?)
        """,
        (order_id.strip().upper(), customer_email.strip()),
    ).fetchone()


def lookup_order(order_id: str, customer_email: str) -> dict:
    """Look up an order's status, items, and refund state."""
    with connect() as conn:
        order = get_verified_order(conn, order_id, customer_email)
        if order is None:
            return {"ok": False, "code": "not_found",
                    "error": "No order with that ID exists for that email."}

        items = conn.execute(
            "SELECT name, qty, price_usd FROM order_items WHERE order_id = ?", (order["id"],)
        ).fetchall()
        refund = conn.execute(
            "SELECT amount_usd, created_at FROM refunds WHERE order_id = ?", (order["id"],)
        ).fetchone()

    days_since_delivery = None
    if order["delivered_at"]:
        days_since_delivery = (get_settings().reference_date
                               - date.fromisoformat(order["delivered_at"])).days

    return {
        "ok": True,
        "order_id": order["id"],
        "status": order["status"],
        "total_usd": order["total_usd"],
        "placed_at": order["placed_at"],
        "delivered_at": order["delivered_at"],
        "days_since_delivery": days_since_delivery,
        "tracking_number": order["tracking_number"],
        "items": [dict(i) for i in items],
        "already_refunded": refund is not None,
    }