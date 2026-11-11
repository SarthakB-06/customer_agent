from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import get_settings


def get_llm() -> BaseChatModel:
    s = get_settings()
    if not s.google_api_key:
        raise RuntimeError("GOOGLE_API_KEY is not set. Copy .env.example to .env and add your key.")
    # temperature=0: support answers should be as repeatable as possible, which also
    # makes eval runs less noisy.
    return ChatGoogleGenerativeAI(model=s.llm_model, google_api_key=s.google_api_key, temperature=0)