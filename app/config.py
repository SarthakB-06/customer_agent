from functools import lru_cache
from pathlib import Path
from datetime import date
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    google_api_key: str = ""
    llm_model: str = "gemini-2.5-flash"

    price_in_per_mtok: float = 0.30
    price_out_per_mtok: float = 2.50

    # Safety limits: enforced in code, so a jailbroken prompt can't raise them
    max_agent_steps: int = 8
    max_cost_per_run_usd: float = 0.05
    refund_limit_usd: float = 100.0

    return_window_days: int = 30

    # Fixed "today" so day-based rules are reproducible in evals. Change for production.
    reference_date: date = date(2026, 11, 1)

    # Paths
    db_path: Path = ROOT_DIR / "data" / "orders.db"
    kb_dir: Path = ROOT_DIR / "data" / "kb"


@lru_cache
def get_settings() -> Settings:
    return Settings()