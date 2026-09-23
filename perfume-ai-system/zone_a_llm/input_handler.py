"""Task 5 — user input -> button-equivalent Preferences (Zone A).

    prefs = Preferences(accords=["woody", "citrus"], gender="Men", season="Summer")     # the button path
    prefs = interpret("something fresh and woody for summer evenings", data)            # free text, no LLM needed
    prefs = interpret(text, data, client=get_client())                                  # LLM fills the gaps, result validated

Three deterministic passes, then (optionally) the LLM:
  1. catalogue keywords — the 96 accord terms / families / genders / seasons the catalogue itself uses;
  2. the lexicon (data/user_lexicon.csv, zone_a_llm/lexicon.py) — everyday words and perfumery descriptors mapped to
     those terms with weights, with negation ('no florals') and strength qualifiers ('not too strong');
  3. clamping — nothing leaves this module that is not a catalogue value.
The LLM runs only when a client exists AND `llm="fallback"` finds the passes empty (or `llm="always"`); its JSON is clamped
to the same vocabulary and the passes are unioned in, so an explicit word the customer used is never lost. Every call is
appended to data/logs/input_log.csv (text -> what each pass found -> the result) — the raw material of the lexicon review
(data/review_input_log.py) and of the future model's training set. Same text -> same result without an LLM.
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
    weights: dict = field(default_factory=dict)           # accord term -> weight (the order of `accords` follows it)
    trace: list = field(default_factory=list)             # phrase -> terms, one line per match (explainability)
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


_LEXICON = None


def _lexicon():
    global _LEXICON
    if _LEXICON is None:
        from .lexicon import Lexicon
        _LEXICON = Lexicon.load()
    return _LEXICON


def _merge_lexicon(kw: Preferences, text: str) -> Preferences:
    """Keyword pass + lexicon pass -> one Preferences with weights (explicit catalogue words weigh 1.0). The terms the
    keyword pass matched are blanked out for the lexicon, so a multi-word term ('fresh spicy') is never re-read as its parts."""
    hit = _lexicon().apply(text, already=kw.accords + kw.avoid)
    weights: dict[str, float] = {a: 1.0 for a in kw.accords}
    for term, w in hit.weights.items():
        weights[term] = max(weights.get(term, 0.0), round(w, 3))
    avoid = set(kw.avoid) | hit.avoid
    for a in avoid:
        weights.pop(a, None)
    p = Preferences(source="keywords+lexicon" if hit.weights or hit.avoid else "keywords")
    p.weights = dict(sorted(weights.items(), key=lambda kv: (-kv[1], kv[0])))
    p.accords = list(p.weights)
    p.avoid = sorted(avoid)
    p.family = kw.family or hit.family
    p.gender = kw.gender or hit.gender
    p.season = kw.season or hit.season
    p.strength = hit.strength if hit.strength is not None else kw.strength
    p.trace = list(hit.trace)
    p.notes = [n for n in kw.notes if "no catalogue vocabulary" not in n]
    if hit.unmatched:
        p.notes.append("unmatched words: " + ", ".join(hit.unmatched))
    if p.is_empty():
        p.notes.append("no catalogue vocabulary found in the text")
    return p


def interpret(text: str, data, client: LLMClient | None = None, llm: str = "fallback", log: bool = True) -> Preferences:
    """Free text -> Preferences. The keyword and lexicon passes always run (Rule 9). The LLM, when a client exists, runs
    for `llm="always"` or, with `llm="fallback"`, only when the passes found no accord at all; its answer is parsed as
    JSON, clamped to the catalogue vocabulary and unioned with the passes. Same text -> same result without an LLM."""
    vocab = vocabulary(data)
    kw = _keyword_prefs(text, vocab)
    base = _merge_lexicon(kw, text)
    result = base
    llm_terms: list[str] = []
    if client is not None and (llm == "always" or (llm == "fallback" and not base.accords)):
        user = (f"ACCORD_TERMS: {', '.join(vocab['accords'])}\nFAMILIES: {', '.join(vocab['families'])}\n\nCustomer: {text}")
        answer = complete(client, SYSTEM_PROMPT, user, max_tokens=400)
        m = re.search(r"\{.*\}", answer, re.S)
        raw = None
        if m:
            try:
                raw = json.loads(m.group(0))
            except json.JSONDecodeError:
                base.notes.append("LLM JSON could not be parsed — deterministic interpretation used")
        else:
            base.notes.append("LLM unavailable or returned no JSON — deterministic interpretation used")
        if isinstance(raw, dict):
            notes = list(base.notes)
            out = _clamp(raw, vocab, notes)
            llm_terms = list(out.accords)
            weights = dict(base.weights)
            for a in out.accords:                                   # LLM additions come in below the explicit words
                weights.setdefault(a, 0.5)
            avoid = set(base.avoid) | set(out.avoid)
            for a in avoid:
                weights.pop(a, None)
            out.weights = dict(sorted(weights.items(), key=lambda kv: (-kv[1], kv[0])))
            out.accords = list(out.weights)
            out.avoid = sorted(avoid)
            out.family = base.family or out.family
            out.gender = base.gender or out.gender
            out.season = base.season or out.season
            out.strength = base.strength if base.strength is not None else out.strength
            out.trace = base.trace + [f"LLM -> {', '.join(llm_terms) or '(nothing)'}"]
            out.notes = notes
            out.source = "keywords+lexicon+llm"
            result = out
    if log:
        try:
            from .input_log import append as _log
            _log(text, kw, base, llm_terms, result)
        except Exception:  # noqa: BLE001 — logging must never break interpretation
            pass
    return result


__all__ = ["Preferences", "interpret", "vocabulary"]
