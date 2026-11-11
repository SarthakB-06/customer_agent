"""Generate the help-center knowledge base as markdown files in data/kb/.

Run from the project root:  python -m data.build_kb
Policy numbers here MUST match the code/database rules (30-day window, $100 limit),
otherwise the groundedness evals will fail for the wrong reasons.
"""
from app.config import get_settings

ARTICLES = {
    # ---------- Returns & refunds ----------
    "return-policy": ("Return policy",
        "You can return most items within 30 days of the delivery date for a full refund. "
        "Items must be unused and in their original packaging. Returns requested after 30 days "
        "from delivery are not eligible for a refund."),
    "how-to-request-a-refund": ("How to request a refund",
        "Contact support with your order ID and the reason for the return. If the order is "
        "eligible, the refund is issued to your original payment method. Each order can be "
        "refunded only once."),
    "refund-timeline": ("When will I receive my refund?",
        "Approved refunds appear on your original payment method within 5-7 business days. "
        "Bank processing times can add a few extra days. We cannot speed up the bank's side."),
    "refund-limits": ("Refund approval limits",
        "Our support assistant can approve refunds up to $100 per order. Refunds above $100 "
        "require review by a human support specialist, who will contact you within 1 business day."),
    "already-refunded-orders": ("My order was already refunded",
        "Each order can be refunded only once. If you were refunded but have not seen the money, "
        "wait the full 5-7 business days and check with your bank. If it still has not arrived "
        "after that, contact a human specialist."),
    "partial-refunds": ("Partial refunds",
        "If only one item in a multi-item order is faulty or unwanted, you can request a refund "
        "for that item alone. The refund amount equals the price paid for that item. Shipping "
        "fees are refunded only if the whole order is returned."),
    "return-shipping": ("Who pays for return shipping?",
        "Return shipping is free for defective, damaged, or wrong items. For change-of-mind "
        "returns, a flat $4.99 return fee is deducted from your refund."),
    "returned-orders": ("Tracking a return",
        "Once we receive your returned item, it is inspected within 2 business days. You will "
        "get an email when the refund is approved. Orders with status 'returned' have already "
        "been received by us."),

    # ---------- Orders & cancellation ----------
    "cancel-an-order": ("Cancelling an order",
        "You can cancel an order only while its status is 'processing'. Once an order has "
        "shipped it cannot be cancelled; you can refuse delivery or return it after it arrives."),
    "order-statuses": ("Order status meanings",
        "Processing: we are preparing your order. Shipped: it is with the carrier and has a "
        "tracking number. Delivered: the carrier confirmed delivery. Cancelled: the order was "
        "cancelled and you were not charged or were refunded. Returned: we received your return."),
    "change-order-details": ("Changing an order",
        "Delivery address and items can be changed only while the order is 'processing'. After "
        "shipping, contact the carrier with your tracking number to redirect the package."),
    "order-not-received-email": ("I did not get an order confirmation email",
        "Check your spam folder first. Confirmation emails are sent within 15 minutes of payment "
        "to the email on your account. If you still cannot find it, support can look up the "
        "order with your account email."),

    # ---------- Shipping ----------
    "shipping-times": ("Shipping times and costs",
        "Standard shipping takes 5-7 business days. Express shipping takes 2-3 business days. "
        "Orders over $50 ship free with standard delivery; otherwise standard shipping is $4.99 "
        "and express is $12.99."),
    "track-your-package": ("Tracking your package",
        "When your order ships, you receive an email with a tracking number. Tracking updates "
        "can take up to 24 hours to appear after shipping. Orders in 'processing' status do not "
        "have a tracking number yet."),
    "lost-package": ("My package is lost or delayed",
        "If your tracking has not updated for 5 business days, or the package has not arrived "
        "10 business days after shipping, contact support. We will open a carrier investigation "
        "and, if the package is confirmed lost, send a replacement or refund."),
    "wrong-address": ("Package delivered to the wrong address",
        "If tracking shows delivered but you do not have the package, check with neighbors and "
        "your building reception, then wait 24 hours. If it is still missing, contact support "
        "and a human specialist will investigate with the carrier."),
    "international-shipping": ("International shipping",
        "We ship to 25 countries. International delivery takes 10-15 business days. Customs "
        "duties and import taxes are the customer's responsibility and are not refundable."),

    # ---------- Product issues ----------
    "damaged-item": ("Item arrived damaged",
        "If your item arrived damaged, contact us within 30 days of delivery with your order ID "
        "and a photo of the damage. We will offer a refund or replacement at no cost, including "
        "return shipping."),
    "wrong-item": ("I received the wrong item",
        "If you received an item different from what you ordered, contact us within 30 days of "
        "delivery with your order ID. We will send the correct item or refund you, and cover "
        "return shipping."),
    "warranty": ("Warranty coverage",
        "Electronics carry a 12-month warranty from the delivery date covering manufacturing "
        "defects. Premium members get 24 months. The warranty does not cover accidental damage, "
        "water damage, or wear and tear."),
    "defective-after-return-window": ("Defective after the 30-day return window",
        "If an item develops a manufacturing defect after 30 days but within the warranty "
        "period, you are not eligible for a standard return refund but you can claim a warranty "
        "repair or replacement. Contact support with your order ID."),

    # ---------- Payments ----------
    "payment-methods": ("Accepted payment methods",
        "We accept Visa, Mastercard, American Express, UPI, and PayPal. Cash on delivery is not "
        "available. Payment is charged when the order is placed."),
    "payment-failed": ("My payment failed",
        "Failed payments are usually caused by incorrect card details, insufficient funds, or "
        "bank security checks. Try another method or contact your bank. If money was deducted "
        "but no order was created, it is automatically returned within 5-7 business days."),
    "charged-twice": ("I was charged twice",
        "A duplicate charge is often a temporary authorization hold that disappears within "
        "3-5 business days. If both charges are still posted after 5 business days, contact "
        "support with your order ID so a specialist can review it."),
    "promo-codes": ("Promo codes and discounts",
        "Only one promo code can be applied per order, and codes cannot be added after the "
        "order is placed. If an item you bought goes on sale within 14 days, contact support "
        "for a price adjustment."),

    # ---------- Account & membership ----------
    "premium-membership": ("Premium membership benefits",
        "Premium members get free express shipping, a 24-month warranty on electronics, and "
        "priority support. Premium status applies to orders placed while you are a member."),
    "reset-password": ("Resetting your password",
        "Use 'Forgot password' on the login page and follow the emailed link, which expires "
        "after 1 hour. Support cannot see or reset passwords for you."),
    "update-account-email": ("Changing your account email",
        "You can change your email in Account Settings after verifying the new address with a "
        "confirmation link. Past orders stay linked to your account."),
    "delete-account": ("Deleting your account",
        "You can request account deletion in Account Settings. Open orders must be completed "
        "first. Your data is deleted within 30 days, except records we must keep for tax purposes."),

    # ---------- Support & escalation ----------
    "contact-human-support": ("Contacting a human agent",
        "Human specialists are available Monday-Saturday, 9am-6pm IST. Cases needing human "
        "review are answered within 1 business day. Ask for a human at any time and the "
        "assistant will escalate your case."),
    "data-privacy": ("Privacy and your data",
        "We never ask for full card numbers, passwords, or one-time codes over chat. We use "
        "your order and contact details only to resolve your request, and we do not sell "
        "personal data."),
}


def main() -> None:
    kb_dir = get_settings().kb_dir
    kb_dir.mkdir(parents=True, exist_ok=True)
    for old in kb_dir.glob("*.md"):  # rebuild cleanly so removed articles don't linger
        old.unlink()

    for slug, (title, body) in ARTICLES.items():
        (kb_dir / f"{slug}.md").write_text(f"# {title}\n\n{body}\n", encoding="utf-8")
    print(f"Wrote {len(ARTICLES)} articles to {kb_dir}")


if __name__ == "__main__":
    main()