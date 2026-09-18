"""Task 4 — optimizer (Zone B: deterministic, no LLM, no I/O).

    result = optimize(safety_result, data)      # safety_result: safety_engine.check_formula(...) on a built formula
    result.verdict      -> "PASS" | "REJECT"
    result.formula      -> sums to exactly 100.000 with every capped material PINNED at its ceiling
    result.iterations   -> how many rebalance -> safety rounds it took to become stable
    result.trace        -> what moved where in each round, and why
    result.safety       -> the final safety result (PASS, provisional until step 0 exists)

Rules (CLAUDE.md step 6 "Normalisation re-check"):
  - the mass removed by the safety cuts is redistributed only across UNCONSTRAINED materials — first within the
    same layer, then across layers; a material sitting at a ceiling never moves up again;
  - Carles' Heart cap (25 %) is respected while redistributing: overflow goes to Base, then Top;
  - after every rebalance the full safety pass runs again; the loop ends only when it changes nothing;
  - when no unpinned odorant can absorb the removed mass, the remainder becomes a DILUENT line (dipropylene glycol
    by default — an odourless solvent used exactly for this, RSC Ch 9 / product practice), flagged DILUENT_ADDED;
    nothing is ever pushed over a ceiling. Layer statistics are computed on odorants only;
  - a REJECT from the safety engine is passed through untouched (Zone B never removes a banned note by itself).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .formula_builder import LAYER_ORDER, LAYER_TARGETS
from .safety_engine import CONCENTRATE_FRACTION, SafetyResult, check_formula

ROUND = 3
TOL = 1e-6
MAX_ITER = 10
DILUENT = {"Note_ID": "SOLVENT-DPG", "Note_Name": "Dipropylene glycol (diluent)", "CAS": "25265-71-8", "Layer": "Diluent"}


@dataclass
class OptimizeResult:
    verdict: str
    formula: pd.DataFrame
    safety: SafetyResult | None
    iterations: int
    trace: list[str]
    flags: list[str] = field(default_factory=list)
    total_pct: float = 0.0
    layers: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def ok(self) -> bool:
        return self.verdict == "PASS"

    def summary(self) -> str:
        lines = [f"optimizer: {self.verdict} after {self.iterations} round(s), total {self.total_pct:.3f} %"]
        if len(self.layers):
            for r in self.layers.itertuples(index=False):
                lines.append(f"  {r.Layer:<6} {r.Pct:7.3f} %  (Carles {r.Min:g}-{r.Max:g})  {'OUT OF RANGE' if not r.In_Range else ''}")
        if len(self.formula):
            for r in self.formula.itertuples(index=False):
                lines.append(f"  {r.Layer:<6} {r.Pct:8.4f}  {r.Note_Name}{'  [pinned]' if r.Pinned else ''}")
        lines += [f"  {f}" for f in self.flags]
        return "\n".join(lines)


def _rebalance(f: pd.DataFrame, pinned: set[str], layer_targets, trace: list[str]) -> tuple[pd.DataFrame, bool]:
    """Bring the total back to 100 by scaling UNPINNED materials, same layer first. Returns (frame, achievable)."""
    f = f.copy()
    f["Pinned"] = f["CAS"].isin(pinned)
    total = float(f["Pct"].sum())
    deficit = 100.0 - total
    if abs(deficit) <= TOL:
        return f, True
    free = f[~f["Pinned"]]
    if len(free) == 0 or float(free["Pct"].sum()) <= 0:
        trace.append(f"deficit {deficit:+.4f} % but no unpinned material can absorb it -> cannot normalise")
        return f, False
    h_max = layer_targets["Heart"][2]
    # 1. per-layer deficit = target share of the removed mass, absorbed by that layer's free materials
    removed_by_layer = {}
    if "Input_Pct" in f.columns:
        for L in LAYER_ORDER:
            sel = f["Layer"] == L
            removed_by_layer[L] = float((f.loc[sel, "Input_Pct"] - f.loc[sel, "Pct"]).clip(lower=0).sum())
    spill = 0.0
    for L in LAYER_ORDER:
        need = removed_by_layer.get(L, 0.0)
        if need <= TOL:
            continue
        sel = (f["Layer"] == L) & ~f["Pinned"]
        base = float(f.loc[sel, "Pct"].sum())
        room = (h_max - float(f.loc[f["Layer"] == "Heart", "Pct"].sum())) if L == "Heart" else float("inf")
        give = min(need, max(room, 0.0)) if base > 0 else 0.0
        if give > TOL:
            f.loc[sel, "Pct"] += give * f.loc[sel, "Pct"] / base
            trace.append(f"{L}: {give:.4f} % of the {need:.4f} % removed in this layer redistributed to {int(sel.sum())} unpinned note(s)")
        spill += need - give
    # 2. whatever a layer could not absorb, and any remaining deficit, goes to free materials across layers
    #    (Base first, then Top, then Heart up to its cap) in proportion to their current share
    remaining = 100.0 - float(f["Pct"].sum())
    for L in ("Base", "Top", "Heart"):
        if remaining <= TOL:
            break
        sel = (f["Layer"] == L) & ~f["Pinned"]
        base = float(f.loc[sel, "Pct"].sum())
        if base <= 0:
            continue
        room = (h_max - float(f.loc[f["Layer"] == "Heart", "Pct"].sum())) if L == "Heart" else float("inf")
        give = min(remaining, max(room, 0.0))
        if give > TOL:
            f.loc[sel, "Pct"] += give * f.loc[sel, "Pct"] / base
            trace.append(f"cross-layer: {give:.4f} % absorbed by unpinned {L} notes")
            remaining -= give
    if remaining > TOL:
        # last resort: ignore the Heart cap rather than fail to normalise? No — CLAUDE.md: Heart never above 25.
        trace.append(f"{remaining:.4f} % cannot be placed without breaching the Heart cap or a pinned ceiling")
        return f, False
    return f, True


def optimize(safety: SafetyResult, data, *, layer_targets=LAYER_TARGETS,
             concentrate_fraction: float | None = None, grades: dict[str, str] | None = None,
             max_iter: int = MAX_ITER) -> OptimizeResult:
    """Rebalance a safety-checked formula to exactly 100 % with capped materials pinned, re-running the safety
    pass after every rebalance until nothing changes. Pure: inputs are not mutated."""
    trace: list[str] = []
    flags: list[str] = []
    fraction = safety.concentrate_fraction if concentrate_fraction is None else concentrate_fraction
    if safety.verdict == "REJECT":
        trace.append("safety verdict REJECT — nothing to optimise; remove the rejected material(s) and rebuild")
        f = safety.formula.copy()
        f["Pinned"] = f["CAS"].isin(safety.pinned)
        return OptimizeResult("REJECT", f, safety, 0, trace, flags, round(float(f["Pct"].sum()), ROUND), _layers(f, layer_targets))

    f = safety.formula.copy()
    if "Layer" not in f.columns:
        f["Layer"] = ""
    pinned = set(safety.pinned)
    current = safety
    for it in range(1, max_iter + 1):
        f, ok = _rebalance(f, pinned, layer_targets, trace)
        if not ok:
            # every odorant that could absorb the removed mass is pinned (or the Heart cap binds): fill with diluent
            residual = round(100.0 - float(f["Pct"].sum()), ROUND)
            if "Note_ID" not in f.columns:
                f["Note_ID"] = ""
            if (f["Note_ID"] == DILUENT["Note_ID"]).any():
                f.loc[f["Note_ID"] == DILUENT["Note_ID"], "Pct"] += residual
            else:
                row = {c: "" for c in f.columns}
                row.update(DILUENT)
                row["Pct"] = residual
                if "Input_Pct" in f.columns:
                    row["Input_Pct"] = 0.0
                f = pd.concat([f, pd.DataFrame([row])], ignore_index=True)
            f["Pinned"] = f["CAS"].isin(pinned)
            trace.append(f"diluent: {residual:.3f} % dipropylene glycol added — no unpinned odorant could absorb the removed mass")
            flags.append(f"WARNING DILUENT_ADDED: {residual:.3f} % dipropylene glycol fills the mass removed by safety cuts (all odorants pinned)")
        # exact 100 after rounding: residual on the largest UNPINNED share
        f["Pct"] = f["Pct"].round(ROUND)
        residual = round(100.0 - float(f["Pct"].sum()), ROUND)
        if abs(residual) > 0:
            free = f[~f["Pinned"]]
            i = free["Pct"].idxmax() if len(free) else f["Pct"].idxmax()
            f.loc[i, "Pct"] = round(f.loc[i, "Pct"] + residual, ROUND)
        # re-run safety on the rebalanced formula
        again = check_formula(f.drop(columns=[c for c in ("Input_Pct", "Pinned") if c in f.columns]), data,
                              concentrate_fraction=fraction, grades=grades)
        current = again
        if again.verdict == "REJECT":
            flags.append("REJECT: the rebalanced formula fails the safety pass")
            g = again.formula.copy()
            g["Pinned"] = g["CAS"].isin(again.pinned)
            return OptimizeResult("REJECT", g, again, it, trace, flags, round(float(g["Pct"].sum()), ROUND), _layers(g, layer_targets))
        new_pins = again.pinned - pinned
        if again.adjustments.empty and not new_pins:
            trace.append(f"round {it}: stable — safety pass changed nothing")
            f["Pinned"] = f["CAS"].isin(pinned)
            layers = _layers(f, layer_targets)
            for r in layers.itertuples(index=False):
                if not r.In_Range and r.Pct > 0:
                    flags.append(f"WARNING: {r.Layer} {r.Pct:.3f} % is outside the Carles range {r.Min:g}-{r.Max:g} % after rebalancing")
            return OptimizeResult("PASS", f, again, it, trace, flags, round(float(f["Pct"].sum()), ROUND), layers)
        trace.append(f"round {it}: safety pass capped {len(again.adjustments)} note(s) again ({', '.join(sorted(set(again.adjustments['Note_Name'])))}); "
                     f"pinning {len(new_pins)} more and rebalancing")
        pinned |= again.pinned
        f = again.formula.copy()            # check_formula carries Layer through and adds Input_Pct
    flags.append(f"REJECT: not stable after {max_iter} rounds")
    f["Pinned"] = f["CAS"].isin(pinned)
    return OptimizeResult("REJECT", f, current, max_iter, trace, flags, round(float(f["Pct"].sum()), ROUND), _layers(f, layer_targets))


def _layers(f: pd.DataFrame, layer_targets) -> pd.DataFrame:
    """Carles layer shares of the ODORANTS (the diluent is listed separately)."""
    rows = []
    dil = float(f.loc[f["Layer"] == "Diluent", "Pct"].sum()) if "Layer" in f.columns else 0.0
    if dil > 0:
        rows.append({"Layer": "Diluent", "Pct": round(dil, ROUND), "Min": 0.0, "Max": 100.0, "In_Range": True})
    for L in LAYER_ORDER:
        p = float(f.loc[f["Layer"] == L, "Pct"].sum()) if "Layer" in f.columns else 0.0
        lo, _, hi = layer_targets[L]
        rows.append({"Layer": L, "Pct": round(p, ROUND), "Min": lo, "Max": hi, "In_Range": (lo - TOL <= p <= hi + TOL) or p == 0})
    return pd.DataFrame(rows)


__all__ = ["optimize", "OptimizeResult", "MAX_ITER"]
