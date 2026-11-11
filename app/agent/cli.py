"""Chat with the agent in the terminal:  python -m app.agent.cli aarav.mehta@example.com"""
import sys

from app.agent.graph import run_agent


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: python -m app.agent.cli <customer_email>")
    email, history = sys.argv[1], []
    print(f"Signed in as {email}. Type 'quit' to exit.\n")
    while (text := input("you> ").strip()) not in ("quit", "exit"):
        out = run_agent(text, email, history=history)
        history = out["messages"]
        for c in out["tool_calls"][-3:]:
            print(f"  [tool] {c['name']}({c['args']})")
        print(f"bot> {out['reply']}\n   (steps={out['steps']}, cost=${out['cost_usd']})\n")


if __name__ == "__main__":
    main()