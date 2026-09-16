"""Jean Carles' method of studying accords, as a deterministic generator (Zone B: no LLM, no I/O).

Carles (A Method of Creation in Perfumery, pp.5-7, 18-20) builds a perfume from the base upwards:
  1. pick the characteristic base material (oakmoss for a chypre);
  2. pair it with a second base in the series 9:1, 8:2, 7:3, 6:4, 5:5 — never beyond 5:5, or the accord is no
     longer "based on" the first material — and choose one;
  3. add a third product (the musk "that cannot be dispensed with in any chypre"), then study 4- and 5-product
     accords the same way;
  4. soften the base with modifiers (Heart), add a top note for the first impression;
  5. weigh the three groups 25 / 20 / 55 (Top / Modifiers / Base).

This module generates those variation series so that a human (or Zone A) can CHOOSE among them; Zone B only
generates, weighs and later safety-checks. Creativity stays a choice, the arithmetic stays deterministic.
Parts are Carles' 10 %-solution units, proportional to neat material (p.18).
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .formula_builder import LAYER_ORDER, LAYER_TARGETS, formula_from_parts

CARLES_SERIES = ((9, 1), (8, 2), (7, 3), (6, 4), (5, 5))     # p.5: "we shall not test combinations beyond the five:five ratio"


@dataclass(frozen=True)
class Accord:
    """A parts formula: ((material, parts), ...) per layer. Immutable and hashable so studies are reproducible."""
    top: tuple[tuple[str, float], ...] = ()
    heart: tuple[tuple[str, float], ...] = ()
    base: tuple[tuple[str, float], ...] = ()

    def layers(self) -> dict[str, list[tuple[str, float]]]:
        return {"Top": list(self.top), "Heart": list(self.heart), "Base": list(self.base)}

    def materials(self) -> list[str]:
        return [m for layer in (self.top, self.heart, self.base) for m, _ in layer]

    def to_percent(self, layer_pct: dict[str, float] | None = None) -> pd.DataFrame:
        """Percent-by-weight formula using Carles' 25/20/55 (or the given layer percentages)."""
        return formula_from_parts(self.layers(), layer_pct)

    def describe(self) -> str:
        out = []
        for L, items in self.layers().items():
            if items:
                out.append(f"{L}: " + ", ".join(f"{p:g} {m}" for m, p in items))
        return " | ".join(out)


def base_series(primary: str, secondary: str, series=CARLES_SERIES) -> list[Accord]:
    """Step 2 — the five two-material base accords 9:1 ... 5:5 with `primary` dominant (Carles p.5)."""
    return [Accord(base=((primary, float(a)), (secondary, float(b)))) for a, b in series]


def add_base(accord: Accord, material: str, parts: float) -> Accord:
    """Step 3 — extend a base accord with one more base material (e.g. Musk Ketone 1)."""
    return Accord(top=accord.top, heart=accord.heart, base=accord.base + ((material, float(parts)),))


def with_modifiers(accord: Accord, modifiers: list[tuple[str, float]]) -> Accord:
    """Step 4a — Carles' 'modifiers' = the Heart layer (materials of intermediate volatility)."""
    return Accord(top=accord.top, heart=tuple((m, float(p)) for m, p in modifiers), base=accord.base)


def with_top(accord: Accord, top: list[tuple[str, float]]) -> Accord:
    """Step 4b — the top note: 'in no case can the top note be the characteristic note of the perfume' (p.6)."""
    return Accord(top=tuple((m, float(p)) for m, p in top), heart=accord.heart, base=accord.base)


def substitution_series(accord: Accord, layer: str, old: str, candidates: list[str]) -> list[Accord]:
    """Carles' 'modifications' (pp.8-10): the same skeleton with one material swapped for each candidate from the
    family's compatibility table, keeping the parts. Deterministic order = the candidates' order."""
    key = {"Top": "top", "Heart": "heart", "Base": "base"}[layer]
    items = getattr(accord, key)
    if old not in [m for m, _ in items]:
        raise ValueError(f"{old!r} is not in the {layer} layer of {accord.describe()}")
    out = []
    for cand in candidates:
        if cand == old:
            continue
        new_items = tuple((cand if m == old else m, p) for m, p in items)
        out.append(Accord(**{**{"top": accord.top, "heart": accord.heart, "base": accord.base}, key: new_items}))
    return out


def study(primary: str, secondary: str, third: tuple[str, float] | None = None,
          modifiers: list[tuple[str, float]] | None = None, top: list[tuple[str, float]] | None = None) -> pd.DataFrame:
    """Run steps 2-4 in one go and return every variant as a table of percent formulas (one Variant column per
    ratio in the series). The caller picks; nothing here picks for them."""
    frames = []
    for i, acc in enumerate(base_series(primary, secondary), start=1):
        if third:
            acc = add_base(acc, *third)
        if modifiers:
            acc = with_modifiers(acc, modifiers)
        if top:
            acc = with_top(acc, top)
        df = acc.to_percent()
        df.insert(0, "Variant", i)
        df.insert(1, "Ratio", f"{CARLES_SERIES[i - 1][0]}:{CARLES_SERIES[i - 1][1]}")
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def carles_chypre() -> Accord:
    """Carles' own worked example (pp.6-7): Top 4 Sweet Orange / 1 Bergamot; Modifiers 3 Rose Abs / 1 Civet 10 %;
    Base 6 Oakmoss / 4 Ambergris 162B / 1 Musk Ketone. The golden test for the builder."""
    return Accord(top=(("Sweet Orange", 4.0), ("Bergamot", 1.0)),
                  heart=(("Rose Abs.", 3.0), ("Civet Abs. 10% solution", 1.0)),
                  base=(("Oakmoss Abs.", 6.0), ("Ambergris 162B", 4.0), ("Musk Ketone", 1.0)))


def from_reference_table(student_accords: pd.DataFrame, accord_key: str, variant: int = 1) -> Accord:
    """Load one of the student base accords transcribed in data/reference/carles_student_accords.csv."""
    g = student_accords[(student_accords["Accord_Key"] == accord_key) & (student_accords["Variant"].astype(int) == variant)]
    if len(g) == 0:
        raise KeyError(f"{accord_key} variant {variant} not in the reference table")
    base = tuple((r.Material, float(r.Parts)) for r in g.itertuples(index=False))
    return Accord(base=base)


__all__ = ["Accord", "CARLES_SERIES", "LAYER_ORDER", "LAYER_TARGETS", "base_series", "add_base", "with_modifiers",
           "with_top", "substitution_series", "study", "carles_chypre", "from_reference_table"]
