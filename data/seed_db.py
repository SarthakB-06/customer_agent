"""Create the fake store database used by the agent's tools and the evals.

Run from the project root:  python -m data.seed_db
Deterministic: same seed -> same data, so eval results are reproducible.
"""
import random
import sqlite3
from datetime import timedelta

from app.config import get_settings

# Fixed "today" so day-based rules (30-day refund window) never drift between runs.
REF_DATE = get_settings().reference_date
SEED = 42

SCHEMA = """
CREATE TABLE customers (
    id      INTEGER PRIMARY KEY,
    name    TEXT NOT NULL,
    email   TEXT NOT NULL UNIQUE,
    tier    TEXT NOT NULL CHECK (tier IN ('standard', 'premium'))
);
CREATE TABLE orders (
    id              TEXT PRIMARY KEY,
    customer_id     INTEGER NOT NULL REFERENCES customers(id),
    status          TEXT NOT NULL CHECK (status IN
                    ('processing', 'shipped', 'delivered', 'cancelled', 'returned')),
    total_usd       REAL NOT NULL,
    placed_at       TEXT NOT NULL,
    delivered_at    TEXT,
    tracking_number TEXT
);
CREATE TABLE order_items (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id  TEXT NOT NULL REFERENCES orders(id),
    name      TEXT NOT NULL,
    qty       INTEGER NOT NULL,
    price_usd REAL NOT NULL
);
CREATE TABLE refunds (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id   TEXT NOT NULL REFERENCES orders(id),
    amount_usd REAL NOT NULL,
    reason     TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

CUSTOMERS = [
    ("Aarav Mehta", "premium"), ("Priya Nair", "standard"), ("Rohan Kapoor", "standard"),
    ("Ananya Iyer", "premium"), ("Vikram Singh", "standard"), ("Sneha Reddy", "standard"),
    ("Karan Malhotra", "standard"), ("Isha Gupta", "premium"), ("Arjun Das", "standard"),
    ("Meera Joshi", "standard"), ("Dev Patel", "standard"), ("Neha Verma", "premium"),
    ("Rahul Sharma", "standard"), ("Pooja Menon", "standard"), ("Siddharth Rao", "standard"),
]

CATALOG = [
    ("Wireless Earbuds", 49.99), ("USB-C Charger 65W", 29.99), ("Mechanical Keyboard", 89.00),
    ("Laptop Stand", 34.50), ("Smart Watch", 199.00), ("Phone Case", 12.99),
    ("Bluetooth Speaker", 59.00), ("Webcam 1080p", 45.00), ("Gaming Mouse", 39.99),
    ("4K Monitor", 329.00), ("Backpack", 54.00), ("Desk Lamp", 24.50),
]


def d(days_ago: int) -> str:
    return (REF_DATE - timedelta(days=days_ago)).isoformat()


# Hand-written orders that pin down the edge cases the evals will test.
# (order_id, customer_id, status, items[(name, qty, price)], placed_days_ago, delivered_days_ago)
EDGE_CASES = [
    ("ORD-1001", 1, "delivered", [("Wireless Earbuds", 1, 49.99)], 10, 5),    # easy refund
    ("ORD-1002", 2, "delivered", [("Mechanical Keyboard", 1, 89.00)], 52, 45),  # outside 30-day window
    ("ORD-1003", 3, "delivered", [("Smart Watch", 1, 199.00), ("Phone Case", 1, 12.99)], 14, 8),  # over refund limit
    ("ORD-1004", 4, "shipped", [("Bluetooth Speaker", 1, 59.00)], 3, None),     # in transit
    ("ORD-1005", 5, "processing", [("Laptop Stand", 1, 34.50)], 1, None),       # still cancellable
    ("ORD-1006", 6, "delivered", [("Webcam 1080p", 1, 45.00)], 20, 14),         # already refunded
    ("ORD-1007", 7, "cancelled", [("Desk Lamp", 2, 24.50)], 12, None),          # cancelled
]


def insert_order(cur, order_id, customer_id, status, items, placed_ago, delivered_ago, rng):
    total = round(sum(q * p for _, q, p in items), 2)
    tracking = f"TRK{rng.randint(10**8, 10**9 - 1)}" if status in ("shipped", "delivered", "returned") else None
    delivered_at = d(delivered_ago) if delivered_ago is not None else None
    cur.execute(
        "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?)",
        (order_id, customer_id, status, total, d(placed_ago), delivered_at, tracking),
    )
    cur.executemany(
        "INSERT INTO order_items (order_id, name, qty, price_usd) VALUES (?, ?, ?, ?)",
        [(order_id, n, q, p) for n, q, p in items],
    )


def random_order(order_number, rng):
    customer_id = rng.randint(1, len(CUSTOMERS))
    items = [(n, rng.randint(1, 2), p) for n, p in rng.sample(CATALOG, rng.randint(1, 3))]
    status = rng.choices(["delivered", "shipped", "processing", "cancelled", "returned"],
                         weights=[60, 15, 8, 8, 9])[0]
    if status == "processing":
        placed_ago, delivered_ago = rng.randint(0, 2), None
    elif status == "shipped":
        placed_ago, delivered_ago = rng.randint(2, 6), None
    elif status in ("delivered", "returned"):
        placed_ago = rng.randint(8, 90)
        delivered_ago = placed_ago - rng.randint(3, 7)
    else:  # cancelled
        placed_ago, delivered_ago = rng.randint(1, 60), None
    return (f"ORD-{order_number}", customer_id, status, items, placed_ago, delivered_ago)


def main() -> None:
    db_path = get_settings().db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.unlink(missing_ok=True)  # always rebuild from scratch

    rng = random.Random(SEED)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()
    cur.executescript(SCHEMA)

    for i, (name, tier) in enumerate(CUSTOMERS, start=1):
        email = f"{name.lower().replace(' ', '.')}@example.com"
        cur.execute("INSERT INTO customers VALUES (?, ?, ?, ?)", (i, name, email, tier))

    for order in EDGE_CASES:
        insert_order(cur, *order, rng)
    for n in range(1008, 1051):  # 43 random orders -> 50 total
        insert_order(cur, *random_order(n, rng), rng)

    # ORD-1006 was already refunded; the tool must refuse a second refund.
    cur.execute(
        "INSERT INTO refunds (order_id, amount_usd, reason, created_at) VALUES (?, ?, ?, ?)",
        ("ORD-1006", 45.00, "Item defective", d(10)),
    )

    conn.commit()
    orders = cur.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    print(f"Seeded {db_path}: {len(CUSTOMERS)} customers, {orders} orders")
    conn.close()


if __name__ == "__main__":
    main()