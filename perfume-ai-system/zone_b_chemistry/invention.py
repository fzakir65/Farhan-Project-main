"""Zone B — INVENT a new perfume (not in the catalogue) from preference terms, Carles' way.

    inv = invent(["woody", "fresh spicy", "amber"], data, family="Fougere", n_variants=5)
    inv.variants   -> list of Candidate: each a full Zone B result (structure -> safety -> rebalance), ranked
    inv.report()

How (deterministic; Zone A or the user CHOOSES a candidate, Zone B never picks a favourite):
  1. the preference terms are mapped to dataset3 rule accords (accord_name_aliases.csv), first term strongest;
  2. those accords are combined into one structure by formula_builder (a NEW combination — this is the invention);
  3. optionally a Carles family signature (chypre / fougère / foin / trèfle, data/reference/carles_family_signatures.csv)
     is enforced: signature materials missing from the structure are added at Support weight so the creation stays
     "within the scope" of the family (Carles p.17);
  4. Carles' ratio study (p.5): the two strongest BASE materials are re-weighted through the 9:1 … 5:5 series, giving
     five sibling formulas that differ only in that base accord — the perfumer's own way of exploring a base;
  5. every variant runs through safety + rebalance; candidates are ranked PASS first, then fewest warnings, then the
     smallest deviation from the 25/20/55 targets. Rejections are reported with their cause, never hidden.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .accord_study import CARLES_SERIES
from .formula_builder import LAYER_ORDER, LAYER_TARGETS, accord_rows_for, build_formula
from .optimizer import OptimizeResult, optimize
from .pipeline import grades_from_formula
from .safety_engine import CONCENTRATE_FRACTION, SafetyResult, check_formula

SIGNATURE_WEIGHT = 3            # Support-level weight for a signature material added to keep the family (Carles p.17)


@dataclass
class Candidate:
    name: str
    ratio: str
    accords: list[str]
    formula: pd.DataFrame
    verdict: str
    safety: SafetyResult | None
    optimized: OptimizeResult | None
    added_signature: list[str] = field(default_factory=list)
    unplaced: list[str] = field(default_factory=list)
    score: tuple = ()

    def summary(self) -> str:
        head = f"{self.name} [{self.ratio}] {self.verdict}"
        if self.optimized is not None and len(self.optimized.layers):
            L = self.optimized.layers.set_index("Layer")["Pct"]
            head += f"  top {L.get('Top', 0):.1f} / heart {L.get('Heart', 0):.1f} / base {L.get('Base', 0):.1f}" + (f" / diluent {L['Diluent']:.1f}" if "Diluent" in L else "")
        lines = [head]
        if len(self.formula):
            top = self.formula.sort_values("Pct", ascending=False).head(8)
            lines.append("   " + ", ".join(f"{r.Note_Name} {r.Pct:.2f}" for r in top.itertuples(index=False)))
        if self.added_signature:
            lines.append(f"   signature added: {', '.join(self.added_signature)}")
        if self.unplaced:
            lines.append(f"   unplaced: {', '.join(self.unplaced)}")
        if self.safety is not None and len(self.safety.rejections):
            lines.append("   rejected: " + "; ".join(f"{r.Note_Name} ({r.Reason[:60]})" for r in self.safety.rejections.itertuples(index=False)))
        return "\n".join(lines)


@dataclass
class Invention:
    terms: list[str]
    family: str | None
    accords: list[str]
    unmapped_terms: list[str]
    variants: list[Candidate]

    def best(self) -> Candidate | None:
        return self.variants[0] if self.variants and self.variants[0].verdict == "PASS" else None

    def report(self) -> str:
        lines = [f"INVENTION from {self.terms}" + (f" as a {self.family}" if self.family else "") + f" -> accords {self.accords}"
                 + (f" (unmapped: {self.unmapped_terms})" if self.unmapped_terms else "")]
        for i, v in enumerate(self.variants, 1):
            lines.append(f"{i}. " + v.summary())
        return "\n".join(lines)


def _terms_to_accords(terms: list[str], data) -> tuple[list[str], dict[str, float], list[str]]:
    from .pipeline import perfume_to_accords
    return perfume_to_accords({"Main_Accords": "; ".join(terms)}, data)


def _signature_rows(family: str, data, present: set[str]) -> tuple[pd.DataFrame, list[str]]:
    """Signature materials of a Carles family that the structure lacks, mapped to dataset2 names."""
    import pandas as _pd
    from pathlib import Path
    from load_data import DATA_DIR
    path = Path(DATA_DIR) / "reference" / "carles_family_signatures.csv"
    sig = _pd.read_csv(path, dtype=str, keep_default_na=False)
    sig = sig[sig["Family"].str.casefold() == family.casefold()]
    if sig.empty:
        raise ValueError(f"unknown Carles family {family!r}; choose one of {sorted(set(_pd.read_csv(path, dtype=str)['Family']))}")
    # signature material -> dataset2 note (first exact / contains match by name, deterministic)
    names = sorted(set(data.notes["Note_Name"]))
    low = {n.casefold(): n for n in names}
    rows, added = [], []
    for r in sig.itertuples(index=False):
        key = r.Material.casefold().replace(" abs.", " absolute").replace("oak moss", "oakmoss")
        cand = low.get(key) or next((n for k, n in sorted(low.items()) if k.startswith(key.split()[0]) and key.split()[0] not in ("misc", "amber")), None)
        if cand is None or cand in present or any(cand.casefold().startswith(p.casefold().split()[0]) for p in present):
            continue
        layer = {"Top": "Top", "Heart": "Heart", "Base": "Base"}[r.Layer]
        rows.append({"Accord_ID": f"SIG-{family.upper()}", "Accord_Name": f"{family} signature", "Accord_Category": "Signature",
                     "Note_ID": "", "Note_Name": cand, "Note_Role": "Support", "Layer": layer, "Importance_Weight": SIGNATURE_WEIGHT,
                     "Typical_Presence": 0.6, "Blend_Compatibility": 0.9, "Stability_Class": "Medium"})
        added.append(cand)
    return pd.DataFrame(rows), added


def invent(terms: list[str], data, *, family: str | None = None, n_variants: int = 5,
           concentrate_fraction: float = CONCENTRATE_FRACTION, grades: dict[str, str] | None = None) -> Invention:
    accords, weights, unmapped = _terms_to_accords(terms, data)
    if not accords:
        return Invention(terms, family, [], unmapped, [])
    rows, _ = accord_rows_for(data.accords, accords)
    added: list[str] = []
    if family:
        sig_rows, added = _signature_rows(family, data, set(rows["Note_Name"]))
        if len(sig_rows):
            rows = pd.concat([rows, sig_rows], ignore_index=True)
            weights[f"SIG-{family.upper()}"] = 0.8
    base = build_formula(rows, data.notes, accord_weights=weights)
    unplaced = sorted(set(base.unplaced["Note_Name"])) if len(base.unplaced) else []

    # Carles ratio study on the two strongest base materials
    bases = base.formula[base.formula["Layer"] == "Base"].sort_values(["Pct", "Note_Name"], ascending=[False, True])
    variants: list[Candidate] = []
    series = [("as built", None)] + [(f"{a}:{b}", (a, b)) for a, b in CARLES_SERIES[:max(0, n_variants - 1)]]
    for label, ratio in series:
        f = base.formula.copy()
        if ratio and len(bases) >= 2:
            a_name, b_name = bases.iloc[0]["Note_Name"], bases.iloc[1]["Note_Name"]
            pair_total = float(f.loc[f["Note_Name"].isin([a_name, b_name]), "Pct"].sum())
            f.loc[f["Note_Name"] == a_name, "Pct"] = pair_total * ratio[0] / (ratio[0] + ratio[1])
            f.loc[f["Note_Name"] == b_name, "Pct"] = pair_total * ratio[1] / (ratio[0] + ratio[1])
            name = f"{a_name} : {b_name}"
        elif ratio:
            continue
        else:
            name = "structure as built"
        g = {**grades_from_formula(f), **(grades or {})}
        safety = check_formula(f, data, concentrate_fraction=concentrate_fraction, grades=g)
        opt = optimize(safety, data, concentrate_fraction=concentrate_fraction, grades=g)
        L = opt.layers.set_index("Layer")["Pct"] if len(opt.layers) else pd.Series(dtype=float)
        deviation = sum(abs(float(L.get(k, 0.0)) - LAYER_TARGETS[k][1]) for k in LAYER_ORDER)
        n_warn = len([x for x in opt.safety.flags if x.severity == "WARNING"]) if opt.safety is not None else 99
        score = (0 if opt.verdict == "PASS" else 1, len(unplaced), n_warn, round(deviation, 3), label)
        variants.append(Candidate(name, label, accords, opt.formula, opt.verdict, opt.safety, opt, added, unplaced, score))
    variants.sort(key=lambda c: c.score)
    return Invention(terms, family, accords, unmapped, variants)


__all__ = ["invent", "Invention", "Candidate"]
