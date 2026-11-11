import json
from typing import Annotated, TypedDict

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from app.agent.llm import get_llm
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.tools import make_tools
from app.config import get_settings
from app.tools import escalate as escalate_ticket


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    steps: int          # number of LLM calls so far this run
    cost_usd: float     # estimated spend so far this run
    limit_hit: bool


def _call_cost(msg: AIMessage) -> float:
    s = get_settings()
    usage = msg.usage_metadata or {}
    return (usage.get("input_tokens", 0) * s.price_in_per_mtok
            + usage.get("output_tokens", 0) * s.price_out_per_mtok) / 1_000_000


def build_graph(customer_email: str, llm: BaseChatModel | None = None):
    settings = get_settings()
    tools = make_tools(customer_email)
    model = (llm or get_llm()).bind_tools(tools)

    def agent_node(state: AgentState) -> dict:
        reply = model.invoke([SystemMessage(SYSTEM_PROMPT), *state["messages"]])
        return {
            "messages": [reply],
            "steps": state["steps"] + 1,
            "cost_usd": state["cost_usd"] + _call_cost(reply),
        }

    def route(state: AgentState) -> str:
        last = state["messages"][-1]
        if not getattr(last, "tool_calls", None):
            return "end"
        if state["steps"] >= settings.max_agent_steps or state["cost_usd"] >= settings.max_cost_per_run_usd:
            return "limit"
        return "tools"

    def limit_node(state: AgentState) -> dict:
        """Fail safe: when a cap is hit, stop acting and hand the case to a human."""
        ticket = escalate_ticket("Agent hit its step or cost limit before finishing.")
        text = (f"I wasn't able to finish this on my own, so I've passed your case to a human "
                f"specialist (ticket {ticket['ticket_id']}). They'll contact you within 1 business day.")
        return {"messages": [AIMessage(text)], "limit_hit": True}

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(tools))
    graph.add_node("limit", limit_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", route, {"tools": "tools", "limit": "limit", "end": END})
    graph.add_edge("tools", "agent")
    graph.add_edge("limit", END)
    return graph.compile()


def run_agent(message: str, customer_email: str, llm: BaseChatModel | None = None,
              history: list[BaseMessage] | None = None) -> dict:
    """Run one customer turn and return the reply plus a full trace for evals and logging."""
    settings = get_settings()
    graph = build_graph(customer_email, llm)
    start = len(history or [])
    final = graph.invoke(
        {"messages": [*(history or []), HumanMessage(message)], "steps": 0, "cost_usd": 0.0,
         "limit_hit": False},
        config={"recursion_limit": settings.max_agent_steps * 2 + 5},
    )

    msgs = final["messages"]
    results = {m.tool_call_id: m.content for m in msgs if isinstance(m, ToolMessage)}
    calls = []
    for m in msgs[start:]:
        for tc in getattr(m, "tool_calls", None) or []:
            raw = results.get(tc["id"])
            try:
                result = json.loads(raw) if raw else None
            except (TypeError, json.JSONDecodeError):
                result = raw
            calls.append({"name": tc["name"], "args": tc["args"], "result": result})

    reply = msgs[-1].content
    return {
        "reply": reply if isinstance(reply, str) else str(reply),
        "tool_calls": calls,
        "steps": final["steps"],
        "cost_usd": round(final["cost_usd"], 6),
        "limit_hit": final["limit_hit"],
        "escalated": final["limit_hit"] or any(c["name"] == "escalate" for c in calls),
        "messages": msgs,
    }