"""Zone A only — the single place that talks to an LLM. Never imported by zone_b_chemistry (a test enforces it).

    client = get_client()          # anthropic client if the SDK is installed and ANTHROPIC_API_KEY is set, else None
    text = complete(client, system, user)   # returns "" on any failure — callers must have a non-LLM path (Rule 9)

Rules (CLAUDE.md "LLM RULES"): the LLM may interpret input, pick from the catalogue and write prose. It never
produces a quantity, a limit, a regulatory status or a reaction, and every catalogue choice it makes is validated
against the catalogue before use. If the API is down the button path still works.
"""
from __future__ import annotations

import os
from typing import Protocol

DEFAULT_MODEL = os.environ.get("PERFUME_LLM_MODEL", "claude-sonnet-5")


class LLMClient(Protocol):
    def complete(self, system: str, user: str, max_tokens: int = 800) -> str: ...


class AnthropicClient:
    def __init__(self, model: str = DEFAULT_MODEL):
        import anthropic  # imported lazily so the rest of the app never needs it
        self._client = anthropic.Anthropic()
        self.model = model

    def complete(self, system: str, user: str, max_tokens: int = 800) -> str:
        msg = self._client.messages.create(model=self.model, max_tokens=max_tokens, system=system,
                                           messages=[{"role": "user", "content": user}])
        return "".join(getattr(b, "text", "") for b in msg.content)


class FakeClient:
    """Deterministic stand-in for tests and offline demos: returns canned answers in order."""
    def __init__(self, answers: list[str]):
        self.answers = list(answers)
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str, max_tokens: int = 800) -> str:
        self.calls.append((system, user))
        return self.answers.pop(0) if self.answers else ""


def get_client() -> LLMClient | None:
    """An LLM client when one can be built, else None (graceful degradation — the button path must still work)."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        return AnthropicClient()
    except Exception:
        return None


def complete(client: LLMClient | None, system: str, user: str, max_tokens: int = 800) -> str:
    if client is None:
        return ""
    try:
        return client.complete(system, user, max_tokens) or ""
    except Exception:
        return ""
