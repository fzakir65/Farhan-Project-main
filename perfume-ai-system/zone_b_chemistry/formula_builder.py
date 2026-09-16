"""Task 2 — structural formula builder (Zone B: deterministic, no LLM, no I/O).

    result = build_formula(accord_rows, notes)          # accord_rows: dataset3 rows, notes: dataset2 (via load_data)
    result.formula     -> DataFrame[Note_ID, Note_Name, CAS, Layer, Pct, Accords, ...]   sums to exactly 100.000
    result.unplaced    -> DataFrame of accord rows that could NOT be placed, with the reason (never silently dropped)
    result.flags       -> list[Flag]  every anomaly, with severity and the row it concerns
    result.trace       -> DataFrame   one row per accord row: every factor that produced its share
    result.layers      -> DataFrame   target vs achieved % per layer

Rules (CLAUDE.md "Chemistry engine rules", Jean Carles method):
  placement   by dataset2 Volatility_Class ONLY. A two-layer tag ("Top/Heart") goes to the accord's own Layer
              when that is one of the two, else to the allowed layer furthest below its target.
  weight      Importance_Weight (1-5) x Typical_Presence (0-1) x accord weight; Driver highest, Modifier trace.
  damping     powerful materials get smaller % (Carles' "accessory products"; RSC Ch 8 p.149 Stevens' law):
              share x ODOR_DAMPING[Odor_Strength]. Coarse on purpose — dataset2's thresholds are not yet verified.
  compat      a low Blend_Compatibility scales the share down by that compatibility (CLAUDE.md general rules).
  layers      Top 15-30 (default 25), Heart 15-25 — never above 25 (default 20), Base 45-65 (default 55) — Carles
              pp.6-7, 23. Notes share their layer's % in proportion to their adjusted weight.
  total       exactly 100.000 after rounding (residual goes to the largest component).
  visibility  anything that cannot be placed is listed in `unplaced` and flagged; nothing is dropped silently.

Same input -> same output: inputs are sorted, ties are broken by fixed keys, no randomness, no globals mutated.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

LAYER_TARGETS = {          # (min %, default %, max %)  — Carles pp.6-7, 23 (Heart = his "modifiers", never > 25)
    "Top": (15.0, 25.0, 30.0),
    "Heart": (15.0, 20.0, 25.0),
    "Base": (45.0, 55.0, 65.0),
}
LAYER_ORDER = ("Top", "Heart", "Base")
TWO_LAYER = {"Top/Heart": ("Top", "Heart"), "Heart/Base": ("Heart", "Base")}

ROLE_WEIGHT = {"Driver": (4, 5), "Support": (2, 4), "Modifier": (1, 3)}   # Importance_Weight range expected per role

# Odour-power damping (CLAUDE.md: "Powerful materials (low odor threshold) get SMALLER %", e.g. IBQ ~0.5-1 %, not 15 %).
# Categorical on purpose: dataset2's Odor_Threshold_mg_L differs between duplicate rows of the same note today, so a
# continuous rule would inject noise. `threshold_damping` below is available once those fields are verified.
ODOR_DAMPING = {"Strong": 0.5, "Medium": 1.0, "Low": 1.0, "": 1.0}
THRESHOLD_REF_MG_L = 0.01          # dataset2 median; materials >= 20x more potent than this are halved again
THRESHOLD_POTENT_FACTOR = 0.5
LOW_COMPATIBILITY = 0.7            # Blend_Compatibility below this scales the share by the compatibility itself
ROUND = 3                          # decimals in Pct


@dataclass(frozen=True)
class Flag:
    code: str            # UNPLACEABLE, NOTE_CONFLICT, LAYER_OVERRIDDEN, EMPTY_LAYER, LAYER_OUT_OF_RANGE,
                         # ACCORD_SINGLE_LAYER, ROLE_WEIGHT_MISMATCH, LOW_COMPATIBILITY, ODOR_DAMPED, UNKNOWN_ACCORD
    severity: str        # ERROR (formula incomplete), WARNING (structure compromised), INFO (decision worth seeing)
    message: str
    accord: str = ""
    note: str = ""

    def __str__(self) -> str:
        where = "/".join(x for x in (self.accord, self.note) if x)
        return f"{self.severity:<7} {self.code:<20} {where}: {self.message}" if where else f"{self.severity:<7} {self.code:<20} {self.message}"


@dataclass
class FormulaResult:
    formula: pd.DataFrame
    unplaced: pd.DataFrame
    flags: list[Flag]
    trace: pd.DataFrame
    layers: pd.DataFrame
    total_pct: float = 0.0

    def errors(self) -> list[Flag]:
        return [f for f in self.flags if f.severity == "ERROR"]

    def warnings(self) -> list[Flag]:
        return [f for f in self.flags if f.severity == "WARNING"]

    @property
    def complete(self) -> bool:
        """True when every accord row was placed (no ERROR flags). The formula still sums to 100 either way."""
        return not self.errors()

    def summary(self) -> str:
        lines = [f"formula: {len(self.formula)} notes, total {self.total_pct:.3f} %  "
                 f"({len(self.errors())} ERROR, {len(self.warnings())} WARNING, "
                 f"{len([f for f in self.flags if f.severity == 'INFO'])} INFO)"]
        for r in self.layers.itertuples(index=False):
            lines.append(f"  {r.Layer:<6} target {r.Target_Pct:5.1f}  achieved {r.Achieved_Pct:7.3f}  notes {r.N_Notes}")
        for r in self.formula.itertuples(index=False):
            lines.append(f"  {r.Layer:<6} {r.Pct:7.3f}  {r.Note_Name} ({r.CAS or 'no CAS'})")
        if len(self.unplaced):
            lines.append("  UNPLACED:")
            lines += [f"    {r.Accord_Name}: {r.Note_Name} — {r.Reason}" for r in self.unplaced.itertuples(index=False)]
        return "\n".join(lines)


# ----------------------------------------------------------------------------
# dataset2 lookup
# ----------------------------------------------------------------------------

def _pick_note_row(rows: pd.DataFrame) -> tuple[pd.Series, bool]:
    """One dataset2 row per note name, deterministically. Prefers a checksum-valid CAS, then the note's most common
    Volatility_Class, then fixed alphabetical tie-breaks. Returns (row, had_conflict)."""
    if len(rows) == 1:
        return rows.iloc[0], False
    r = rows.copy()
    r["_valid"] = r["CAS_Valid"] if "CAS_Valid" in r.columns else r["CAS"].astype(bool)
    r["_valid"] = r["_valid"].astype(bool) & (r["CAS"].astype(str) != "")
    mode = r["Volatility_Class"].value_counts()
    r["_vc_rank"] = r["Volatility_Class"].map(lambda v: -mode.get(v, 0))
    r = r.sort_values(["_valid", "_vc_rank", "Volatility_Class", "Odor_Strength", "CAS"],
                      ascending=[False, True, True, True, True], kind="mergesort")
    distinct = rows[["CAS", "Volatility_Class"]].astype(str).drop_duplicates()
    return r.iloc[0], len(distinct) > 1


def _two_layer_choice(options: tuple[str, str], hint: str, raw_by_layer: dict[str, float],
                      targets: dict[str, float]) -> tuple[str, str]:
    """Where does a Top/Heart or Heart/Base note go? The accord's own Layer if allowed, else the allowed layer whose
    raw share is furthest below its target (fill the neediest layer first). Deterministic: ties -> LAYER_ORDER."""
    if hint in options:
        return hint, f"two-layer class {'/'.join(options)}: accord Layer {hint!r} is one of them"
    total = sum(raw_by_layer.values()) or 1.0
    deficit = {L: targets[L] - 100.0 * raw_by_layer.get(L, 0.0) / total for L in options}
    chosen = sorted(options, key=lambda L: (-deficit[L], LAYER_ORDER.index(L)))[0]
    return chosen, f"two-layer class {'/'.join(options)}: {chosen} is furthest below its target"


# ----------------------------------------------------------------------------
# the builder
# ----------------------------------------------------------------------------

def build_formula(accord_rows: pd.DataFrame, notes: pd.DataFrame, *,
                  accord_weights: dict[str, float] | None = None,
                  layer_targets: dict[str, tuple[float, float, float]] = LAYER_TARGETS,
                  odor_damping: dict[str, float] = ODOR_DAMPING,
                  threshold_damping: bool = False,
                  low_compatibility: float = LOW_COMPATIBILITY) -> FormulaResult:
    """Build a Top/Heart/Base formula (percent by weight) from dataset3 accord rows and the dataset2 notes table.

    accord_rows     dataset3 rows for one or more accords (columns as in load_data.accords)
    notes           dataset2 table from load_data (Note_Name, CAS, Volatility_Class, Odor_Strength, ...)
    accord_weights  optional Accord_ID -> relative weight when several accords are combined (default: equal)
    Pure: no I/O, no randomness, inputs are not mutated.
    """
    flags: list[Flag] = []
    targets = {L: layer_targets[L][1] for L in LAYER_ORDER}
    weights = dict(accord_weights or {})

    rows = accord_rows.copy()
    for col, default in (("Note_Role", ""), ("Layer", ""), ("Importance_Weight", 1.0), ("Typical_Presence", 1.0),
                         ("Blend_Compatibility", 1.0), ("Accord_Name", ""), ("Accord_ID", "")):
        if col not in rows.columns:
            rows[col] = default
    rows = _dedupe_accord_rows(rows, flags)
    rows = rows.sort_values(["Accord_ID", "Note_Name", "Note_ID"], kind="mergesort").reset_index(drop=True)
    for aid in sorted(set(rows["Accord_ID"])):
        weights.setdefault(aid, 1.0)

    by_name = {name: g for name, g in notes.groupby("Note_Name", sort=True)}

    # ---- pass 1: resolve each accord row in dataset2, compute its raw adjusted weight
    trace_rows: list[dict] = []
    unplaced: list[dict] = []
    for r in rows.itertuples(index=False):
        rec = {"Accord_ID": r.Accord_ID, "Accord_Name": r.Accord_Name, "Note_Name": r.Note_Name, "Note_Role": r.Note_Role,
               "Accord_Layer": r.Layer, "Importance_Weight": float(r.Importance_Weight), "Typical_Presence": float(r.Typical_Presence),
               "Blend_Compatibility": float(r.Blend_Compatibility), "Accord_Weight": float(weights[r.Accord_ID])}
        g = by_name.get(r.Note_Name)
        if g is None or len(g) == 0:
            reason = "note not in dataset2 (Rule 10: names must match exactly) — reconcile via note_name_aliases.csv or add the note"
            flags.append(Flag("UNPLACEABLE", "ERROR", reason, r.Accord_Name, r.Note_Name))
            unplaced.append({**rec, "Reason": reason})
            trace_rows.append({**rec, "Placed": False, "Reason": reason})
            continue
        note, conflict = _pick_note_row(g)
        vc = str(note["Volatility_Class"])
        if conflict:
            alts = "; ".join(f"{a.CAS or '-'} {a.Volatility_Class}" for a in
                             g[["CAS", "Volatility_Class"]].astype(str).drop_duplicates()
                             .sort_values(["CAS", "Volatility_Class"]).itertuples(index=False))
            flags.append(Flag("NOTE_CONFLICT", "INFO", f"dataset2 has conflicting rows ({alts}); used CAS {note['CAS'] or '-'} / {vc}",
                              r.Accord_Name, r.Note_Name))
        if vc not in LAYER_ORDER and vc not in TWO_LAYER:
            reason = f"dataset2 Volatility_Class {vc!r} is not Top/Heart/Base (or a two-layer tag)"
            flags.append(Flag("UNPLACEABLE", "ERROR", reason, r.Accord_Name, r.Note_Name))
            unplaced.append({**rec, "Reason": reason})
            trace_rows.append({**rec, "Placed": False, "Reason": reason})
            continue

        lo, hi = ROLE_WEIGHT.get(r.Note_Role, (1, 5))
        w = float(r.Importance_Weight)
        if not (lo <= w <= hi):
            flags.append(Flag("ROLE_WEIGHT_MISMATCH", "INFO",
                              f"{r.Note_Role} with Importance_Weight {w:g} (expected {lo}-{hi}); the numeric weight is used",
                              r.Accord_Name, r.Note_Name))
        raw = w * float(r.Typical_Presence) * float(weights[r.Accord_ID])

        strength = str(note.get("Odor_Strength", "") or "")
        damp = float(odor_damping.get(strength, 1.0))
        damp_src = f"Odor_Strength={strength or 'n/a'}"
        if threshold_damping:
            try:
                thr = float(note.get("Odor_Threshold_mg_L", ""))
                if thr > 0 and thr <= THRESHOLD_REF_MG_L / 20:
                    damp *= THRESHOLD_POTENT_FACTOR
                    damp_src += f", threshold {thr:g} mg/L <= ref/20"
            except (TypeError, ValueError):
                pass
        if damp < 1.0:
            flags.append(Flag("ODOR_DAMPED", "INFO", f"powerful material: share x{damp:g} ({damp_src})", r.Accord_Name, r.Note_Name))

        compat = float(r.Blend_Compatibility)
        compat_factor = compat if compat < low_compatibility else 1.0
        if compat_factor < 1.0:
            flags.append(Flag("LOW_COMPATIBILITY", "INFO", f"Blend_Compatibility {compat:g} < {low_compatibility}: share x{compat:g}",
                              r.Accord_Name, r.Note_Name))

        trace_rows.append({**rec, "Placed": True, "Note_ID": note["Note_ID"], "CAS": str(note["CAS"] or ""),
                           "Volatility_Class": vc, "Raw_Weight": raw, "Odor_Damping": damp, "Odor_Damping_Source": damp_src,
                           "Compat_Factor": compat_factor, "Adjusted_Weight": raw * damp * compat_factor, "Reason": ""})

    trace = pd.DataFrame(trace_rows)
    placed = trace[trace["Placed"]].copy() if len(trace) else trace

    # ---- pass 2: layer placement — single-layer notes first, then two-layer notes to the neediest allowed layer
    raw_by_layer: dict[str, float] = {L: 0.0 for L in LAYER_ORDER}
    layer_of: dict[int, str] = {}
    reason_of: dict[int, str] = {}
    for idx, t in placed.iterrows():
        if t["Volatility_Class"] in LAYER_ORDER:
            layer_of[idx] = t["Volatility_Class"]
            reason_of[idx] = f"dataset2 Volatility_Class {t['Volatility_Class']}"
            raw_by_layer[t["Volatility_Class"]] += t["Adjusted_Weight"]
            if t["Accord_Layer"] and t["Accord_Layer"] != t["Volatility_Class"]:
                flags.append(Flag("LAYER_OVERRIDDEN", "INFO",
                                  f"accord says {t['Accord_Layer']}, dataset2 Volatility_Class says {t['Volatility_Class']} — dataset2 wins",
                                  t["Accord_Name"], t["Note_Name"]))
    for idx, t in placed.iterrows():
        if t["Volatility_Class"] in TWO_LAYER:
            L, why = _two_layer_choice(TWO_LAYER[t["Volatility_Class"]], t["Accord_Layer"], raw_by_layer, targets)
            layer_of[idx], reason_of[idx] = L, why
            raw_by_layer[L] += t["Adjusted_Weight"]
    if len(placed):
        placed["Layer"] = pd.Series(layer_of)
        placed["Placement_Reason"] = pd.Series(reason_of)
        trace.loc[placed.index, "Layer"] = placed["Layer"]
        trace.loc[placed.index, "Placement_Reason"] = placed["Placement_Reason"]

    # ---- pass 3: merge the same note across accords, then split each layer's % by adjusted weight
    if len(placed):
        merged = (placed.groupby(["Note_ID", "Note_Name", "CAS", "Layer"], sort=True)
                  .agg(Adjusted_Weight=("Adjusted_Weight", "sum"), Accords=("Accord_Name", lambda s: "; ".join(sorted(set(s)))),
                       Roles=("Note_Role", lambda s: "; ".join(sorted(set(s)))))
                  .reset_index())
    else:
        merged = pd.DataFrame(columns=["Note_ID", "Note_Name", "CAS", "Layer", "Adjusted_Weight", "Accords", "Roles"])

    layer_pct = _layer_percentages(merged, layer_targets, flags)
    merged["Pct"] = 0.0
    for L in LAYER_ORDER:
        sel = merged["Layer"] == L
        tot = merged.loc[sel, "Adjusted_Weight"].sum()
        if tot > 0:
            merged.loc[sel, "Pct"] = layer_pct[L] * merged.loc[sel, "Adjusted_Weight"] / tot
    merged = _normalise_to_100(merged, flags)
    merged["Layer"] = pd.Categorical(merged["Layer"], categories=list(LAYER_ORDER), ordered=True)
    merged = merged.sort_values(["Layer", "Pct", "Note_Name"], ascending=[True, False, True], kind="mergesort").reset_index(drop=True)
    merged["Layer"] = merged["Layer"].astype(str)

    # ---- shape check (RSC Ch 7 p.141): an accord living in one layer only vanishes with that layer
    if len(placed):
        for aid, g in placed.groupby("Accord_ID", sort=True):
            if len(g) >= 2 and g["Layer"].nunique() == 1:
                flags.append(Flag("ACCORD_SINGLE_LAYER", "WARNING",
                                  f"all {len(g)} placed notes sit in {g['Layer'].iloc[0]} — the theme has no successor in the other layers",
                                  g["Accord_Name"].iloc[0]))

    layers = pd.DataFrame([{"Layer": L, "Target_Pct": targets[L], "Applied_Pct": round(layer_pct[L], ROUND),
                            "Achieved_Pct": round(float(merged.loc[merged["Layer"] == L, "Pct"].sum()), ROUND),
                            "N_Notes": int((merged["Layer"] == L).sum())} for L in LAYER_ORDER])
    unplaced_cols = ["Accord_ID", "Accord_Name", "Note_Name", "Note_Role", "Accord_Layer", "Importance_Weight",
                     "Typical_Presence", "Blend_Compatibility", "Accord_Weight", "Reason"]
    unplaced_df = pd.DataFrame(unplaced, columns=unplaced_cols)
    flags = sorted(flags, key=lambda f: ({"ERROR": 0, "WARNING": 1, "INFO": 2}[f.severity], f.code, f.accord, f.note))
    return FormulaResult(formula=merged[["Note_ID", "Note_Name", "CAS", "Layer", "Pct", "Adjusted_Weight", "Accords", "Roles"]],
                         unplaced=unplaced_df, flags=flags, trace=trace, layers=layers,
                         total_pct=round(float(merged["Pct"].sum()), ROUND) if len(merged) else 0.0)


_DEDUPE_COLS = ["Accord_ID", "Note_Name", "Note_Role", "Layer", "Importance_Weight", "Typical_Presence", "Blend_Compatibility"]


def _dedupe_accord_rows(rows: pd.DataFrame, flags: list[Flag]) -> pd.DataFrame:
    """dataset3 repeats some (accord, note) rows. Exact repeats are dropped (INFO); repeats with different values keep
    the strongest statement of the note (highest weight, then presence, then compatibility) and raise a WARNING.
    A note is one material — its weight is never summed across duplicate rows."""
    exact = rows.duplicated(_DEDUPE_COLS)
    if exact.any():
        for aid, n in rows[exact].groupby("Accord_ID").size().items():
            name = rows.loc[rows["Accord_ID"] == aid, "Accord_Name"].iloc[0]
            flags.append(Flag("DUPLICATE_ROW", "INFO", f"{n} exact duplicate accord row(s) ignored", name))
        rows = rows[~exact]
    rows = rows.sort_values(["Accord_ID", "Note_Name", "Importance_Weight", "Typical_Presence", "Blend_Compatibility"],
                            ascending=[True, True, False, False, False], kind="mergesort")
    dup = rows.duplicated(["Accord_ID", "Note_Name"], keep=False)
    if dup.any():
        for (aid, note), g in rows[dup].groupby(["Accord_ID", "Note_Name"], sort=True):
            alts = "; ".join(f"{r.Note_Role} w{r.Importance_Weight:g} p{r.Typical_Presence:g}" for r in g.itertuples(index=False))
            flags.append(Flag("DUPLICATE_NOTE_IN_ACCORD", "WARNING", f"{len(g)} differing rows for this note ({alts}); kept the first",
                              g["Accord_Name"].iloc[0], note))
    return rows.drop_duplicates(["Accord_ID", "Note_Name"], keep="first")


def _layer_percentages(merged: pd.DataFrame, layer_targets, flags: list[Flag]) -> dict[str, float]:
    """Default targets, redistributed when a layer has no notes, then Carles' constraints re-imposed:
    Heart never above its max (25), Base the largest share. Anything still outside a range is flagged."""
    present = {L for L in LAYER_ORDER if (merged["Layer"] == L).any()}
    pct = {L: layer_targets[L][1] for L in LAYER_ORDER}
    if not present:
        return {L: 0.0 for L in LAYER_ORDER}
    missing = [L for L in LAYER_ORDER if L not in present]
    for L in missing:
        flags.append(Flag("EMPTY_LAYER", "WARNING", f"no {L} notes — its {pct[L]:g} % is redistributed to the other layers"))
        share, pct[L] = pct[L], 0.0
        tot = sum(pct[M] for M in present)
        for M in present:
            pct[M] += share * pct[M] / tot
    # Heart cap (Carles p.23): move the excess to Base, else Top
    h_max = layer_targets["Heart"][2]
    if pct["Heart"] > h_max + 1e-9:
        excess, pct["Heart"] = pct["Heart"] - h_max, h_max
        sink = "Base" if "Base" in present else ("Top" if "Top" in present else None)
        if sink:
            pct[sink] += excess
    # Base must be the largest share (Carles p.7): if it is not, lift it to the largest other layer's value
    if "Base" in present:
        others = [pct[M] for M in present if M != "Base"]
        if others and pct["Base"] < max(others):
            flags.append(Flag("LAYER_OUT_OF_RANGE", "WARNING", f"Base ({pct['Base']:.1f} %) is not the largest share — Carles p.7"))
    else:
        flags.append(Flag("LAYER_OUT_OF_RANGE", "WARNING", "no Base notes at all — the formula will lack tenacity (Carles p.7)"))
    for L in present:
        lo, _, hi = layer_targets[L]
        if not (lo - 1e-9 <= pct[L] <= hi + 1e-9):
            flags.append(Flag("LAYER_OUT_OF_RANGE", "WARNING", f"{L} {pct[L]:.1f} % is outside the Carles range {lo:g}-{hi:g} %"))
    return pct


def _normalise_to_100(merged: pd.DataFrame, flags: list[Flag]) -> pd.DataFrame:
    if not len(merged):
        return merged
    total = merged["Pct"].sum()
    if total <= 0:
        return merged
    merged["Pct"] = merged["Pct"] * 100.0 / total
    merged["Pct"] = merged["Pct"].round(ROUND)
    residual = round(100.0 - merged["Pct"].sum(), ROUND)
    if abs(residual) > 0:
        i = merged["Pct"].idxmax()                     # deterministic: first occurrence of the largest share
        merged.loc[i, "Pct"] = round(merged.loc[i, "Pct"] + residual, ROUND)
        if abs(residual) > 0.01:
            flags.append(Flag("NORMALISED", "INFO", f"rounding residual {residual:+.3f} % added to {merged.loc[i, 'Note_Name']}"))
    return merged


# ----------------------------------------------------------------------------
# helpers for Carles-style parts formulas and for going from a perfume to its accord rows
# ----------------------------------------------------------------------------

def formula_from_parts(layers: dict[str, list[tuple[str, float]]],
                       layer_pct: dict[str, float] | None = None) -> pd.DataFrame:
    """Carles' notation -> percentages: {'Top': [('Sweet Orange', 4), ('Bergamot', 1)], ...} with layer percentages
    (default 25/20/55) gives each material layer_pct x parts / sum(parts in layer). Sums to exactly 100."""
    layer_pct = dict(layer_pct or {L: LAYER_TARGETS[L][1] for L in LAYER_ORDER})
    rows = []
    for L in LAYER_ORDER:
        items = layers.get(L, [])
        tot = sum(p for _, p in items)
        for name, parts in items:
            rows.append({"Note_Name": name, "Layer": L, "Parts": parts, "Pct": layer_pct[L] * parts / tot if tot else 0.0})
    df = pd.DataFrame(rows, columns=["Note_Name", "Layer", "Parts", "Pct"])
    if len(df):
        df = _normalise_to_100(df, [])
    return df


def accord_rows_for(accords: pd.DataFrame, accord_names: list[str]) -> tuple[pd.DataFrame, list[Flag]]:
    """dataset3 rows for the named accords (case/whitespace-insensitive on Accord_Name). Unknown names are flagged,
    never silently ignored — the caller decides whether a formula without that accord is acceptable."""
    key = accords["Accord_Name"].astype(str).str.strip().str.casefold()
    flags, parts = [], []
    for name in accord_names:
        sel = accords[key == str(name).strip().casefold()]
        if len(sel) == 0:
            flags.append(Flag("UNKNOWN_ACCORD", "ERROR", "accord has no rows in dataset3", str(name)))
        else:
            parts.append(sel)
    rows = pd.concat(parts, ignore_index=True) if parts else accords.iloc[0:0]
    return rows, flags
