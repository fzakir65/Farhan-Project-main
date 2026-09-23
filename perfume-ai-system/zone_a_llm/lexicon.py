"""Zone A — the human-input datasheet: data/user_lexicon.csv applied to free text, with negation and strength qualifiers.

    lx = Lexicon.load()                                  # 500+ phrases -> catalogue terms (Curtis, Ohloff, everyday language)
    hit = lx.apply("beachy, salty, like the ocean, no vanilla, not too strong")
    hit.weights   -> {'aquatic': 1.0, 'salty': 0.8, 'marine': 0.9, ...}    (accumulated, longest phrase wins, deterministic)
    hit.avoid     -> {'vanilla'}          hit.strength -> 2          hit.trace -> ['ocean -> aquatic:1;marine:0.9;salty:0.7', ...]

Negation: a phrase inside a window opened by no / not / without / avoid / hate / dislike / don't like / don't want /
can't stand / nothing / never … and closed by punctuation, 'but', 'and' or 5 words counts as AVOID. 'not too strong',
'not overpowering' are strength qualifiers, not avoidance. Same text -> same result, no LLM involved.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

NEG_OPENERS = r"(?:no|not|without|avoid|hate|hates|dislike|dislikes|don'?t like|don'?t want|do not like|do not want|can'?t stand|cannot stand|nothing|never|minus|allergic to|sick of|tired of|except)"
NEG_CLOSERS = r"(?:[.,;!?()]|\bbut\b|\bhowever\b|\bjust\b|\bonly\b|\bplease\b|$)"
NEG_WINDOW = re.compile(rf"\b{NEG_OPENERS}\b\s+((?:(?!{NEG_CLOSERS}).){{0,60}})", re.I)
STRENGTH_NEG = re.compile(r"\b(?:not|never|nothing)\s+(?:too\s+|so\s+|very\s+|really\s+)?(strong|heavy|loud|overpowering|overwhelming|powerful|intense|much|cloying)\b", re.I)
STRENGTH_POS = re.compile(r"\b(?:very|really|super|extremely|extra)\s+(strong|powerful|long lasting|long-lasting|intense)\b", re.I)


def _norm(text: str) -> str:
    t = text.casefold().replace("’", "'").replace("‑", "-").replace("–", "-")
    t = re.sub(r"[^a-z0-9'\- ]+", lambda m: f" {m.group(0)} ", t)     # keep punctuation as tokens for the negation windows
    return re.sub(r"\s+", " ", t).strip()


def _stem_variants(phrase: str) -> list[str]:
    """Plural / adjective variants so 'florals', 'woods', 'smokey' hit the row ('floral', 'woody', 'smoky')."""
    out = {phrase}
    if phrase.endswith("y"):
        out.add(phrase[:-1] + "ies")
    out.add(phrase + "s")
    out.add(phrase + "es")
    return sorted(out, key=len, reverse=True)


@dataclass
class LexiconHit:
    weights: dict[str, float] = field(default_factory=dict)
    avoid: set[str] = field(default_factory=set)
    family: str | None = None
    gender: str | None = None
    season: str | None = None
    strength: int | None = None
    trace: list[str] = field(default_factory=list)
    unmatched: list[str] = field(default_factory=list)


class Lexicon:
    def __init__(self, df: pd.DataFrame):
        self.df = df[df["Apply"].str.strip().str.lower() == "yes"].copy() if "Apply" in df.columns else df.copy()
        self.rows: dict[str, dict] = {}
        for r in self.df.itertuples(index=False):
            pairs = []
            for item in str(r.Accord_Terms).split(";"):
                if ":" in item:
                    t, w = item.rsplit(":", 1)
                    try:
                        pairs.append((t.strip(), float(w)))
                    except ValueError:
                        continue
            self.rows[str(r.Phrase).casefold()] = {"pairs": pairs, "family": r.Family or None, "gender": r.Gender or None, "season": r.Season or None,
                                                   "strength": int(r.Strength) if str(r.Strength).strip() else None, "kind": r.Kind, "source": r.Source}
        # longest phrases first so 'sea breeze' beats 'sea', 'not too strong' beats 'strong'
        self.order = sorted(self.rows, key=lambda p: (-len(p.split()), -len(p)))
        self.patterns = {p: re.compile(r"(?<![a-z'])(?:" + "|".join(re.escape(v) for v in _stem_variants(p)) + r")(?![a-z'])") for p in self.order}

    @classmethod
    def load(cls, path: str | Path | None = None) -> "Lexicon":
        if path is None:
            from load_data import DATA_DIR
            path = Path(DATA_DIR) / "user_lexicon.csv"
        return cls(pd.read_csv(path, dtype=str, keep_default_na=False))

    def apply(self, text: str, already: list[str] | None = None) -> LexiconHit:
        """`already`: phrases the catalogue keyword pass has already matched (e.g. the multi-word term 'fresh spicy') —
        blanked before scanning so the lexicon cannot re-read their component words as separate terms."""
        t = _norm(text)
        for phrase in sorted(already or [], key=len, reverse=True):
            t = re.sub(rf"(?<![a-z']){re.escape(phrase.casefold())}(?![a-z'])", lambda m: " " * len(m.group(0)), t)
        hit = LexiconHit()
        # strength qualifiers first, then blank them so 'strong' inside 'not too strong' cannot match again
        m = STRENGTH_NEG.search(t)
        if m:
            hit.strength = 2
            hit.trace.append(f"'{m.group(0)}' -> strength 2 (qualifier)")
            t = t[:m.start()] + " " * (m.end() - m.start()) + t[m.end():]
        m = STRENGTH_POS.search(t)
        if m:
            hit.strength = 5
            hit.trace.append(f"'{m.group(0)}' -> strength 5 (qualifier)")
            t = t[:m.start()] + " " * (m.end() - m.start()) + t[m.end():]
        neg_spans = [(m.start(1), m.end(1)) for m in NEG_WINDOW.finditer(t)]
        consumed = [False] * len(t)
        for phrase in self.order:
            for m in self.patterns[phrase].finditer(t):
                if any(consumed[m.start():m.end()]):
                    continue
                for i in range(m.start(), m.end()):
                    consumed[i] = True
                row = self.rows[phrase]
                negated = any(a <= m.start() < b for a, b in neg_spans)
                if row["strength"] is not None and not row["pairs"]:
                    if hit.strength is None:
                        hit.strength = row["strength"]
                        hit.trace.append(f"'{phrase}' -> strength {row['strength']}")
                    continue
                if negated:
                    main = [term for term, w in row["pairs"] if w >= 0.9] or [row["pairs"][0][0]]   # 'no patchouli' avoids patchouli, not its whole family
                    for term in main:
                        hit.avoid.add(term)
                    hit.trace.append(f"'{phrase}' (negated) -> avoid {', '.join(main)}")
                    continue
                for term, w in row["pairs"]:
                    hit.weights[term] = max(hit.weights.get(term, 0.0), w) + 0.05 * (hit.weights.get(term, 0.0) > 0)   # repeats nudge, never dominate
                hit.trace.append(f"'{phrase}' -> " + ";".join(f"{term}:{w:g}" for term, w in row["pairs"]) + f" [{row['kind']}]")
                hit.family = hit.family or row["family"]
                hit.gender = hit.gender or row["gender"]
                hit.season = hit.season or row["season"]
        for term in hit.avoid:
            hit.weights.pop(term, None)
        # what the user wrote that nothing matched (content words only) — the review loop feeds on this
        words = [w for w in re.findall(r"[a-z][a-z'\-]{2,}", t)]
        hit.unmatched = sorted({w for i, w in enumerate(words) if not consumed[t.find(w)] and w not in STOPWORDS})
        return hit


STOPWORDS = set("""the and for with that this from have want would like something some very really into about just been more most than
no not without avoid hate hates dislike dislikes don't doesn't cannot can't never nothing except minus allergic sick tired
vibe vibes thing things stuff anything everything nothing else other another same different maybe perhaps quite rather
buy buying bought price cheap expensive bottle bottles size ml oz gift birthday christmas husband wife girlfriend boyfriend
then them they their there here when what which who how also its it's you your our can could should but not too all any one two
please give need looking looks smell smells smelling scent scents perfume perfumes fragrance fragrances cologne wear wearing
day night out evening morning everyday feel feels feeling kind sort type bit lot little much many good great nice best love loves
loved make makes made get gets got use uses used try trying been being does doing did will shall might may must""".split())


__all__ = ["Lexicon", "LexiconHit"]
