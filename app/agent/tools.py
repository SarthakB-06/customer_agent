import json

from langchain_core.tools import tool

from app import tools as core


def make_tools(customer_email: str) -> list:
    """Build the tools the model can call, bound to ONE authenticated customer.

    The email is captured here in a closure and is NOT a parameter the model can set.
    Even a fully jailbroken model can only ever act on this customer's own orders.
    Every tool returns JSON text so the model (and the evals) can parse it.
    """

    @tool
    def lookup_order(order_id: str) -> str:
        """Look up the customer's order by ID (like ORD-1001): status, items, total, delivery
        date, tracking number, and whether it was already refunded."""
        return json.dumps(core.lookup_order(order_id, customer_email))

    @tool
    def issue_refund(order_id: str, reason: str) -> str:
        """Refund a full order. Only call this after lookup_order shows the order is delivered
        and the customer asked for a refund. The system checks all policy rules itself and
        will refuse if the order is not eligible."""
        return json.dumps(core.issue_refund(order_id, customer_email, reason))

    @tool
    def search_kb(query: str) -> str:
        """Search the help-center articles for policy and how-to information (returns,
        shipping, warranty, payments, accounts). Use this before answering any policy question."""
        return json.dumps(core.search_kb(query))

    @tool
    def escalate(reason: str, order_id: str | None = None) -> str:
        """Hand the case to a human specialist. Use when a refund needs human review, the
        customer asks for a human, or the problem is outside what you can resolve."""
        return json.dumps(core.escalate(reason, order_id))

    return [lookup_order, issue_refund, search_kb, escalate]