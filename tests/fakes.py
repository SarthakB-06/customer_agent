from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class ScriptedModel(BaseChatModel):
    """A fake LLM that replays scripted replies, so agent logic is tested without an API.
    When the script runs out it repeats the last reply (handy for testing loop caps)."""

    script: list[AIMessage]
    calls: int = 0

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        # Real LLMs return a brand-new message every call. Copy and re-id so a repeated
        # scripted reply isn't de-duplicated by LangGraph's message reducer.
        msg = self.script[min(self.calls, len(self.script) - 1)].model_copy(deep=True)
        msg.id = None
        for tc in msg.tool_calls:
            tc["id"] = f"{tc['id']}-{self.calls}"
        self.calls += 1
        return ChatResult(generations=[ChatGeneration(message=msg)])


def call(name: str, args: dict, id: str = "c1", **usage) -> AIMessage:
    msg = AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": id}])
    if usage:
        msg.usage_metadata = {"input_tokens": usage.get("inp", 0), "output_tokens": usage.get("out", 0),
                              "total_tokens": usage.get("inp", 0) + usage.get("out", 0)}
    return msg