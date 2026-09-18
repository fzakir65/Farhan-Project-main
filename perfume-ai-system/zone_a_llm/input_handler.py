"""Task 5 — user input -> button-equivalent Preferences (Zone A).

    prefs = Preferences(accords=["woody", "citrus"], gender="Men", season="Summer")     # the button path
    prefs = interpret("something fresh and woody for summer evenings", data)            # free text, no LLM needed
    prefs = interpret(text, data, client=get_client())                                  # LLM helps, result validated

The vocabulary is always the catalogue's own (dataset1 accord terms / families / genders / seasons): free text is
reduced to those values, by keyword matching (deterministic) and optionally by the LLM — whose JSON answer is
validated against the same vocabulary and clamped. The LLM can never introduce a term the catalogue lacks.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from .llm_client import LLMClient, complete

GENDERS = {"men": "Men", "male": "Men", "masculine": "Men", "him": "Men", "women": "Women", "female": "Women",
           "feminine": "Women", "her": "Women", "unisex": "Unisex", "anyone": "Unisex", "shared": "Unisex"}
SEASONS = {"spring": "Spring", "summer": "Summer", "autumn": "Fall", "fall": "Fall", "winter": "Winter",
           "hot": "Summer", "cold": "Winter", "warm weather": "Summer"}
STRENGTH_WORDS = {"strong": 5, "powerful": 5, "long lasting": 5, "loud": 4, "moderate": 3, "soft": 2, "light": 2,
                  "subtle": 2, "skin scent": 1, "close to the skin": 1}
AVOID_PATTERNS = (r"\b(?:no|not|without|avoid|hate|dislike|can't stand|allergic to)\s+([a-z][a-z \-]{2,30})",)

SYSTEM_PROMPT = """You convert a customer's perfume wish into JSON. Use ONLY values from the lists given.
Return JSON with keys: accords (list of terms from ACCORD_TERMS), family (one of FAMILIES or null),
gender (Men/Women/Unisex or null), season (Spring/Summer/Fall/Winter or null), avoid (list of terms from ACCORD_TERMS),
strength (1-5 or null). Never invent terms. Never mention quantities or safety. Output JSON only."""


@dataclass
class Preferences:
    accords: list[str] = field(default_factory=list)      # dataset1 Main_Accords terms, normalised
    family: str | None = None                             # dataset1 Fragrance_Family
    gender: str | None = None                             # Men / Women / Unisex
    season: str | None = None                             # Spring / Summer / Fall / Winter
    avoid: list[str] = field(default_factory=list)
    strength: int | None = None                           # 1..5 (Longevity_Score / Sillage_Score scale)
    source: str = "buttons"                               # buttons | keywords | llm
    notes: list[str] = field(default_factory=list)        # what the interpreter did / could not do

    def is_empty(self) -> bool:
        return not (self.accords or self.family or self.gender or self.season or self.avoid or self.strength)


def vocabulary(data) -> dict[str, list[str]]:
    """The catalogue's own vocabulary — the only values a preference may take."""
    from load_data import normalize_name
    terms = sorted({normalize_name(t) for cell in data.perfumes["Main_Accords"] for t in re.split(r"[;,]", str(cell)) if t.strip()})
    fams = sorted({str(f).strip() for f in data.perfumes["Fragrance_Family"] if str(f).strip()})
    return {"accords": terms, "families": fams, "genders": ["Men", "Women", "Unisex"], "seasons": ["Spring", "Summer", "Fall", "Winter"]}


def _keyword_prefs(text: str, vocab: dict[str, list[str]]) -> Preferences:
    t = " " + re.sub(r"\s+", " ", text.casefold()) + " "
    prefs = Preferences(source="keywords")
    avoid_spans = []
    for pat in AVOID_PATTERNS:
        for m in re.finditer(pat, t):
            avoid_spans.append(m.group(1).strip())
    for term in sorted(vocab["accords"], key=len, reverse=True):      # longest first so 'fresh spicy' beats 'fresh'
        if re.search(rf"\b{re.escape(term)}\b", t):
            if any(term in span for span in avoid_spans):
                prefs.avoid.append(term)
            else:
                prefs.accords.append(term)
    # a term found inside a longer matched term is a duplicate hit ('fresh' inside 'fresh spicy')
    prefs.accords = [a for a in prefs.accords if not any(a != b and re.search(rf"\b{re.escape(a)}\b", b) for b in prefs.accords)]
    for fam in sorted(vocab["families"], key=len, reverse=True):
        if fam.casefold() in t:
            prefs.family = fam
            break
    for k, v in GENDERS.items():
        if re.search(rf"\b{k}\b", t):
            prefs.gender = v
            break
    for k, v in SEASONS.items():
        if re.search(rf"\b{k}\b", t):
            prefs.season = v
            break
    for k, v in sorted(STRENGTH_WORDS.items(), key=lambda kv: -len(kv[0])):
        if k in t:
            prefs.strength = v
            break
    if prefs.is_empty():
        prefs.notes.append("no catalogue vocabulary found in the text")
    return prefs


def _clamp(raw: dict, vocab: dict[str, list[str]], notes: list[str]) -> Preferences:
    """Keep only values that exist in the catalogue vocabulary; record everything dropped."""
    from load_data import normalize_name
    ok_terms = set(vocab["accords"])
    p = Preferences(source="llm")
    for key in ("accords", "avoid"):
        vals = raw.get(key) or []
        if isinstance(vals, str):
            vals = [vals]
        kept = []
        for v in vals:
            n = normalize_name(v)
            if n in ok_terms:
                kept.append(n)
            else:
                notes.append(f"LLM proposed unknown {key[:-1] if key.endswith('s') else key} term {v!r} — dropped")
        setattr(p, key, kept)
    fam = raw.get("family")
    if fam in vocab["families"]:
        p.family = fam
    elif fam:
        notes.append(f"LLM proposed unknown family {fam!r} — dropped")
    if raw.get("gender") in vocab["genders"]:
        p.gender = raw["gender"]
    if raw.get("season") in vocab["seasons"]:
        p.season = raw["season"]
    try:
        s = int(raw.get("strength")) if raw.get("strength") is not None else None
        p.strength = s if s is not None and 1 <= s <= 5 else None
    except (TypeError, ValueError):
        pass
    p.notes = notes
    return p


def interpret(text: str, data, client: LLMClient | None = None) -> Preferences:
    """Free text -> Preferences. Keyword matching always runs (Rule 9); the LLM, when available, may add to it —
    its answer is parsed as JSON and clamped to the catalogue vocabulary. Same text -> same result without an LLM."""
    vocab = vocabulary(data)
    kw = _keyword_prefs(text, vocab)
    if client is None:
        return kw
    user = (f"ACCORD_TERMS: {', '.join(vocab['accords'])}\nFAMILIES: {', '.join(vocab['families'])}\n\nCustomer: {text}")
    answer = complete(client, SYSTEM_PROMPT, user, max_tokens=400)
    m = re.search(r"\{.*\}", answer, re.S)
    if not m:
        kw.notes.append("LLM unavailable or returned no JSON — keyword interpretation used")
        return kw
    try:
        raw = json.loads(m.group(0))
    except json.JSONDecodeError:
        kw.notes.append("LLM JSON could not be parsed — keyword interpretation used")
        return kw
    notes = list(kw.notes)
    llm = _clamp(raw if isinstance(raw, dict) else {}, vocab, notes)
    # union with the keyword pass so an LLM omission never loses an explicit word the customer used
    llm.accords = sorted(set(llm.accords) | set(kw.accords))
    llm.avoid = sorted(set(llm.avoid) | set(kw.avoid))
    llm.accords = [a for a in llm.accords if a not in llm.avoid]
    llm.family = llm.family or kw.family
    llm.gender = llm.gender or kw.gender
    llm.season = llm.season or kw.season
    llm.strength = llm.strength or kw.strength
    return llm


__all__ = ["Preferences", "interpret", "vocabulary"]
