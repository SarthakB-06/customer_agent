import re
from functools import lru_cache

from app.config import get_settings

STOPWORDS = {
    "a", "an", "the", "i", "my", "me", "is", "are", "was", "to", "of", "and", "or", "for",
    "it", "in", "on", "do", "does", "can", "how", "what", "when", "will", "you", "your",
    "be", "have", "has", "with", "this", "that", "not", "if", "at", "we", "our",
}


def _stem(word: str) -> str:
    """Crude suffix stripping so 'limits' matches 'limit' and 'refunded' matches 'refund'."""
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word


def _tokens(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9$]+", text.lower())
    return [_stem(w) for w in words if w not in STOPWORDS]


@lru_cache
def _load_kb() -> list[dict]:
    articles = []
    for path in sorted(get_settings().kb_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        title, _, body = text.partition("\n\n")
        articles.append({
            "slug": path.stem,
            "title": title.lstrip("# ").strip(),
            "text": body.strip(),
            "title_tokens": set(_tokens(title)),
            "body_tokens": set(_tokens(body)),
        })
    return articles


def search_kb(query: str, k: int = 3) -> dict:
    """Keyword search over help-center articles. (Phase 3 replaces this with hybrid search.)"""
    q = set(_tokens(query))
    scored = []
    for a in _load_kb():
        # Title matches count double: titles are the densest summary of an article.
        score = 2 * len(q & a["title_tokens"]) + len(q & a["body_tokens"])
        if score > 0:
            scored.append((score, a))
    scored.sort(key=lambda x: -x[0])

    return {"ok": True, "results": [
        {"slug": a["slug"], "title": a["title"], "text": a["text"], "score": s}
        for s, a in scored[:k]
    ]}