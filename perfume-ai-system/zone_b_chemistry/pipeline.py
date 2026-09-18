"""Zone B end to end: accords -> structure (Task 2) -> safety (Task 3) -> rebalance (Task 4).

    out = run_zone_b(accord_names, data, concentrate_fraction=1.0, grades=None, accord_weights=None)
    out.verdict   "PASS" | "REJECT" | "INCOMPLETE" (some notes could not be placed — see out.build.unplaced)
    out.formula   final % formula (sums to 100 when PASS)
    out.build / out.safety / out.optimized   the three stage results, each with its own trace and flags

Deterministic, no LLM, no I/O. Zone A hands over accord names (and nothing numeric); this module owns the numbers.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .formula_builder import FormulaResult, accord_rows_for, build_formula
from .optimizer import OptimizeResult, optimize
from .safety_engine import CONCENTRATE_FRACTION, SafetyResult, check_formula


@dataclass
class ZoneBResult:
    verdict: str
    formula: pd.DataFrame
    build: FormulaResult
    safety: SafetyResult | None
    optimized: OptimizeResult | None
    lookup_flags: list

    def report(self) -> str:
        parts = [f"ZONE B: {self.verdict}", "--- structure (Task 2) ---", self.build.summary()]
        if self.lookup_flags:
            parts.append("--- accord lookup ---\n" + "\n".join(str(f) for f in self.lookup_flags))
        if self.safety is not None:
            parts += ["--- safety (Task 3) ---", self.safety.summary()]
        if self.optimized is not None:
            parts += ["--- rebalance (Task 4) ---", self.optimized.summary(), "trace:"] + [f"  {t}" for t in self.optimized.trace]
        return "\n".join(parts)


GRADE_WORDS = ("rectified", "crude", "gum", "absolute", "resinoid", "extract", "distillate", "oil", "erecta", "minuta", "patula")


def grades_from_formula(formula: pd.DataFrame) -> dict[str, str]:
    """Default grade per CAS, read from the names of the notes IN THIS FORMULA ('Birch Tar Rectified' -> 'rectified',
    'Styrax Resinoid' -> 'resinoid'). A name without a grade word gives no grade, and if two notes in the formula share
    a CAS but state different grades the CAS stays unknown — either way the safety engine REJECTS grade-scoped
    materials, the conservative outcome CLAUDE.md asks for. Never keyed on the whole catalogue: plain 'Birch Tar'
    must not inherit 'rectified' from a sibling row that happens to share its CAS. Caller-supplied grades override."""
    out: dict[str, str] = {}
    conflict: set[str] = set()
    for name, cas in sorted(zip(formula["Note_Name"], formula["CAS"].fillna("").astype(str))):
        if not cas:
            continue
        words = [w for w in GRADE_WORDS if w in name.lower().split()]
        grade = " ".join(words)
        if cas in out and out[cas].split(" (")[0] != grade:
            conflict.add(cas)
        elif words:
            out[cas] = f"{grade} (from note name {name!r})"
        elif cas not in out:
            conflict.add(cas)          # a grade-less note: never let a graded sibling speak for it
    return {c: g for c, g in out.items() if c not in conflict}


def run_zone_b(accord_names: list[str], data, *, concentrate_fraction: float = CONCENTRATE_FRACTION,
               grades: dict[str, str] | None = None, accord_weights: dict[str, float] | None = None,
               require_complete: bool = True) -> ZoneBResult:
    rows, lookup_flags = accord_rows_for(data.accords, accord_names)
    build = build_formula(rows, data.notes, accord_weights=accord_weights)
    grades = {**grades_from_formula(build.formula), **(grades or {})}
    if len(build.formula) == 0:
        return ZoneBResult("INCOMPLETE", build.formula, build, None, None, lookup_flags)
    if require_complete and (not build.complete or lookup_flags):
        # the structure is usable, but the caller asked for every note to be placed: report, do not proceed
        return ZoneBResult("INCOMPLETE", build.formula, build, None, None, lookup_flags)
    safety = check_formula(build.formula, data, concentrate_fraction=concentrate_fraction, grades=grades)
    optimized = optimize(safety, data, concentrate_fraction=concentrate_fraction, grades=grades)
    return ZoneBResult(optimized.verdict, optimized.formula, build, safety, optimized, lookup_flags)


__all__ = ["run_zone_b", "ZoneBResult", "grades_from_formula"]
