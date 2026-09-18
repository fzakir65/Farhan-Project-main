"""Task 5 — match Preferences to perfumes in dataset1 (Zone A).

    matches = match(prefs, data, top_k=5)                     # deterministic scoring: the button path
    matches = match(prefs, data, top_k=5, client=get_client())  # LLM re-ranks the deterministic shortlist

Grounding (Rule 11): the LLM only ever sees the shortlist the scorer produced, is told "Only recommend from this
list", and its answer is accepted only if every ID it returns is in that list. A bad answer falls back to the
deterministic order. Nothing here touches quantities.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

import pandas as pd

from .input_handler import Preferences
from .llm_client import LLMClient, complete

WEIGHTS = {"accord": 3.0, "position": 1.0, "family": 2.0, "gender": 1.5, "season": 1.0, "strength": 0.5, "avoid": -4.0}

SYSTEM_PROMPT = """You are a perfume consultant. You will be given a customer's preferences and a numbered SHORTLIST
of perfumes from our catalogue. Rank the shortlist for this customer. Only recommend from this list — never
name a perfume that is not on it. Answer with JSON: {"ranking": [<Perfume_ID>, ...], "why": "<one sentence>"}.
Do not mention ingredients quantities, safety or regulations."""


@dataclass
class Match:
    perfume_id: str
    name: str
    brand: str
    score: float
    reasons: list[str] = field(default_factory=list)
    accords: list[str] = field(default_factory=list)
    rank_source: str = "deterministic"      # deterministic | llm


def _terms(cell) -> list[str]:
    from load_data import normalize_name
    return [normalize_name(t) for t in re.split(r"[;,]", str(cell or "")) if t.strip()]


def score_perfume(row: pd.Series, prefs: Preferences) -> tuple[float, list[str]]:
    """Deterministic, explainable score. Higher is better; every contribution is listed."""
    score, why = 0.0, []
    accords = _terms(row["Main_Accords"])
    for want in prefs.accords:
        if want in accords:
            pos = accords.index(want)
            s = WEIGHTS["accord"] + WEIGHTS["position"] * max(0.0, 1.0 - pos / max(len(accords), 1))
            score += s
            why.append(f"+{s:.1f} has '{want}' (accord #{pos + 1})")
    for no in prefs.avoid:
        if no in accords:
            score += WEIGHTS["avoid"]
            why.append(f"{WEIGHTS['avoid']:.1f} contains avoided '{no}'")
    if prefs.family and str(row.get("Fragrance_Family", "")).strip().casefold() == prefs.family.casefold():
        score += WEIGHTS["family"]
        why.append(f"+{WEIGHTS['family']:.1f} family {prefs.family}")
    g = str(row.get("Gender", "")).strip()
    if prefs.gender and g:
        if g == prefs.gender or g == "Unisex":
            score += WEIGHTS["gender"]
            why.append(f"+{WEIGHTS['gender']:.1f} gender {g}")
        else:
            score -= WEIGHTS["gender"]
            why.append(f"-{WEIGHTS['gender']:.1f} gender {g}")
    if prefs.season:
        seasons = [s.strip().casefold() for s in re.split(r"[;,/]", str(row.get("Season", "")))]
        if prefs.season.casefold() in seasons or "all seasons" in seasons:
            score += WEIGHTS["season"]
            why.append(f"+{WEIGHTS['season']:.1f} season {prefs.season}")
    if prefs.strength and "Longevity_Score" in row.index and pd.notna(row["Longevity_Score"]):
        gap = abs(float(row["Longevity_Score"]) - prefs.strength)
        s = WEIGHTS["strength"] * (1 - gap / 4)
        score += s
        why.append(f"{s:+.1f} longevity {row['Longevity_Score']:g} vs wanted {prefs.strength}")
    return round(score, 3), why


def shortlist(prefs: Preferences, data, top_k: int = 5) -> list[Match]:
    """Deterministic ranking of the whole catalogue; ties broken by Perfume_ID so the order is stable."""
    rows = []
    for _, r in data.perfumes.iterrows():
        s, why = score_perfume(r, prefs)
        rows.append((s, str(r["Perfume_ID"]), r, why))
    rows.sort(key=lambda t: (-t[0], t[1]))
    out = []
    for s, pid, r, why in rows[:top_k]:
        out.append(Match(pid, str(r["Perfume_Name"]), str(r["Brand"]), s, why, _terms(r["Main_Accords"])))
    return out


def match(prefs: Preferences, data, top_k: int = 5, client: LLMClient | None = None, shortlist_size: int = 12) -> list[Match]:
    """Button path: the deterministic shortlist. With an LLM: re-rank that shortlist, accepting the answer only when
    every returned ID is on it (grounding). Anything else -> the deterministic order, with the reason recorded."""
    cands = shortlist(prefs, data, top_k=max(top_k, shortlist_size))
    if client is None or not cands:
        return cands[:top_k]
    listing = "\n".join(f"{i + 1}. {m.perfume_id} — {m.name} by {m.brand}: {', '.join(m.accords)}" for i, m in enumerate(cands))
    user = (f"Customer preferences: accords={prefs.accords}, avoid={prefs.avoid}, family={prefs.family}, "
            f"gender={prefs.gender}, season={prefs.season}, strength={prefs.strength}\n\nSHORTLIST:\n{listing}")
    answer = complete(client, SYSTEM_PROMPT, user, max_tokens=300)
    m = re.search(r"\{.*\}", answer, re.S)
    by_id = {c.perfume_id: c for c in cands}
    if m:
        try:
            raw = json.loads(m.group(0))
            ranking = [str(x) for x in raw.get("ranking", [])]
            if ranking and all(x in by_id for x in ranking):
                seen, out = set(), []
                for pid in ranking:
                    if pid not in seen:
                        c = by_id[pid]
                        c.rank_source = "llm"
                        c.reasons = c.reasons + [f"LLM: {raw.get('why', '')}".strip()]
                        out.append(c)
                        seen.add(pid)
                out += [c for c in cands if c.perfume_id not in seen]
                return out[:top_k]
        except (json.JSONDecodeError, AttributeError, TypeError):
            pass
    for c in cands:
        c.reasons = c.reasons + ["LLM re-rank unavailable or ungrounded — deterministic order kept"]
    return cands[:top_k]


__all__ = ["Match", "match", "shortlist", "score_perfume"]
