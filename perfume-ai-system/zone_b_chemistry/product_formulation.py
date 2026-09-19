"""Zone B — from a fragrance CONCENTRATE (the % formula Zone B builds) to a finished PRODUCT formulation.

    prod = formulate_product(concentrate, data, product_type="Eau de toilette")
    prod.table        -> every component of the bottle: ethanol, water, the concentrate, antioxidant, UV absorber…
    prod.materials    -> each fragrance material at its FINISHED-PRODUCT % (what IFRA limits are written against)
    prod.safety       -> the safety pass re-run at the product concentration (concentrate_fraction = concentrate %)
    prod.allergens    -> the UK/EU allergen declaration (leave-on threshold 0.001 %)
    prod.process      -> maturation / chilling / filtration steps (RSC Fig 9.1 p.160)
    prod.warnings     -> solubility, water level, natural load, missing CAS

What a bottle contains (RSC Fig 9.1, the Business Scents EdP): ethanol 78 %, water 8.5 %, fragrance 12 %, UV absorber
0.5 %, glucose-ether fixative 1 %. Odour-active 'fixatives' (musks, Ambroxan, benzoin…) are already INSIDE the
concentrate — a diluent (DPG) is only used when solubility or an all-pinned concentrate demands it (transcript).
Every auxiliary comes from data/product_bases.csv with its legal basis; nothing here is an LLM decision.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

from .safety_engine import SafetyResult, check_formula

ROUND = 3


@dataclass
class ProductResult:
    product_type: str
    concentrate_pct: float
    table: pd.DataFrame
    materials: pd.DataFrame
    safety: SafetyResult
    allergens: pd.DataFrame
    process: list[str]
    warnings: list[str] = field(default_factory=list)
    batch_g: float = 100.0

    def summary(self) -> str:
        lines = [f"PRODUCT: {self.product_type} — concentrate {self.concentrate_pct:g} % — batch {self.batch_g:g} g — "
                 f"safety at product level: {self.safety.verdict}{' (provisional)' if self.safety.provisional else ''}"]
        for r in self.table.itertuples(index=False):
            lines.append(f"  {r.Pct:7.3f} %  {r.Grams:8.3f} g  {r.Component:<44} {r.Role}")
        if len(self.allergens):
            lines.append("  ALLERGEN DECLARATION (leave-on, > 0.001 %): " + ", ".join(f"{r.Allergen} {r.Product_Pct:.4f} %" for r in self.allergens.itertuples(index=False)))
        for w in self.warnings:
            lines.append(f"  WARNING {w}")
        lines.append("  PROCESS: " + " -> ".join(self.process))
        return "\n".join(lines)


def _rng(s: str) -> tuple[float, float]:
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", str(s))]
    return (nums[0], nums[-1]) if nums else (float("nan"), float("nan"))


def formulate_product(concentrate: pd.DataFrame, data, *, product_type: str = "Eau de toilette",
                      concentrate_pct: float | None = None, water_pct: float | None = None,
                      antioxidant: str | None = "BHT", uv_absorber: bool = True, fixative: bool = False,
                      diluent_pct: float = 0.0, humectant: bool | None = None,
                      batch_g: float = 100.0, grades: dict[str, str] | None = None) -> ProductResult:
    """Wrap a concentrate (Note_Name, CAS, Pct summing to 100) into a product. Percentages are w/w of the bottle.
    `humectant=None` adds propylene glycol only for after-shave product types (Poucher Formula VI: 4-6 %)."""
    pt = data.product_types.set_index("Product_Type")
    if product_type not in pt.index:
        raise ValueError(f"unknown product type {product_type!r}; choose one of {list(pt.index)}")
    row = pt.loc[product_type]
    lo, hi = float(row["Concentrate_Min_Pct"]), float(row["Concentrate_Max_Pct"])
    conc = float(concentrate_pct) if concentrate_pct is not None else round((lo + hi) / 2, 1)
    if not (lo - 1e-9 <= conc <= hi + 1e-9):
        raise ValueError(f"{product_type}: concentrate {conc} % outside the {lo}-{hi} % range (product_types.csv)")
    bases = data.product_bases.set_index("Component")
    warnings: list[str] = []

    # solvent split: alcohol share of the solvent from the product type (RSC Table A2), upper bound = clearest product
    a_lo, a_hi = _rng(row["Alcohol_Pct_Range"])
    solvent = 100.0 - conc
    if water_pct is None:
        water = round(solvent * (1 - a_hi / 100.0), 2)
    else:
        water = float(water_pct)
    if water > 12.0:
        warnings.append(f"water {water:g} % > 12 %: run a solubility trial; polysorbate 20 (<= 2 %) may be needed to keep the product clear")

    comps = []
    def add(name, pct, role=None):
        b = bases.loc[name]
        if pct > float(b["Max_Pct"]) + 1e-9:
            warnings.append(f"{name} {pct:g} % exceeds its maximum {b['Max_Pct']} % ({b['Legal_Basis']})")
        comps.append({"Component": name, "INCI": b["INCI"], "CAS": b["CAS"], "Role": role or b["Role"], "Pct": pct,
                      "Basis": b["Legal_Basis"], "Source": b["Source"]})

    comps.append({"Component": "Fragrance concentrate", "INCI": "Parfum (Fragrance)", "CAS": "", "Role": "the formula from Zone B", "Pct": conc,
                  "Basis": "IFRA Cat 4 / UK Cosmetics Reg — checked at this concentration below", "Source": "formula_builder + safety_engine + optimizer"})
    add("Purified water", water)
    if antioxidant:
        add(antioxidant, float(bases.loc[antioxidant, "Default_Pct"]))
    if uv_absorber:
        add("Benzophenone-3", float(bases.loc["Benzophenone-3", "Default_Pct"]))
    if fixative:
        add("PPG-20 methyl glucose ether", float(bases.loc["PPG-20 methyl glucose ether", "Default_Pct"]))
    if diluent_pct > 0:
        add("Dipropylene glycol", float(diluent_pct))
    if humectant is None:
        humectant = "after" in product_type.lower() and "shave" in product_type.lower()
    if humectant:
        add("Propylene glycol", float(bases.loc["Propylene glycol", "Default_Pct"]))
    ethanol = round(100.0 - sum(c["Pct"] for c in comps), ROUND)
    if ethanol < 50:
        warnings.append(f"ethanol only {ethanol:g} % — below the 50 % floor of any RSC Table A2 product; check the solvent split")
    comps.insert(0, {"Component": "Ethanol (denatured, DEB 100)", "INCI": "Alcohol Denat.", "CAS": "64-17-5", "Role": "solvent",
                     "Pct": ethanol, "Basis": bases.loc["Ethanol (denatured, DEB 100)", "Legal_Basis"], "Source": bases.loc["Ethanol (denatured, DEB 100)", "Source"]})
    table = pd.DataFrame(comps)
    table["Grams"] = (table["Pct"] * batch_g / 100.0).round(ROUND)

    # fragrance materials at finished-product level
    c = concentrate.copy()
    c["Pct"] = pd.to_numeric(c["Pct"], errors="coerce").fillna(0.0)
    mats = c[["Note_Name", "CAS", "Pct"]].rename(columns={"Pct": "Concentrate_Pct"})
    mats["Product_Pct"] = (mats["Concentrate_Pct"] * conc / 100.0).round(5)
    mats["Grams"] = (mats["Product_Pct"] * batch_g / 100.0).round(4)
    natural_load = float(c.loc[c["Note_Name"].str.contains(r"absolute|resin|balsam|tincture|concrete", case=False, regex=True), "Pct"].sum())
    if natural_load > 20:
        warnings.append(f"{natural_load:.1f} % of the concentrate is absolutes/resinoids/balsams — mature 4-6 weeks and chill-filter; consider up to 5 % DPG")
    if (mats["CAS"] == "").any():
        warnings.append(f"{int((mats['CAS'] == '').sum())} material(s) without CAS: their product-level safety is UNVERIFIED")

    # safety at product concentration: the concentrate's % are judged against limit / (conc/100)
    safety = check_formula(concentrate[["Note_Name", "CAS", "Pct"]], data, concentrate_fraction=conc / 100.0, grades=grades)

    # allergen declaration (direct materials + constituent contributions from constituents.csv)
    allergens = _allergen_declaration(mats, data, conc)

    process = [
        "weigh the fragrance materials into the concentrate; pre-dilute powerful materials (musks 1 %, geosmin/skatole 0.1 %)",
        ("mix the concentrate into the propylene glycol, then dissolve in the ethanol (Poucher Formula VI, p.373)" if humectant
         else "blend the concentrate into the ethanol"),
        "add the water and the auxiliaries slowly with mixing (antioxidant dissolved in ethanol first)",
        f"mature {'4-6 weeks' if natural_load > 20 else '10-14 days'} at room temperature in the dark",
        "chill to +1 °C for 24 h (Poucher: 'cool to about 4 °C', p.373); filter through a fine filter (0.2 % magnesium carbonate as filter aid if precipitates are stubborn)",
        "fill into clean glass; label with the allergen declaration; light-stability and solubility checks at 5 °C / 40 °C",
    ]
    return ProductResult(product_type, conc, table, mats, safety, allergens, process, warnings, batch_g)


def _allergen_declaration(mats: pd.DataFrame, data, conc: float) -> pd.DataFrame:
    al = getattr(data, "allergens", None)
    if al is None or len(al) == 0:
        return pd.DataFrame(columns=["Allergen", "CAS", "Product_Pct", "Sources"])
    by_cas: dict[str, tuple[str, str]] = {}
    for r in al.itertuples(index=False):
        for c in str(r.All_CAS).split("|"):
            if c:
                by_cas[c] = (r.Allergen, r.CAS)
    totals: dict[str, float] = {}
    sources: dict[str, list[str]] = {}
    for r in mats.itertuples(index=False):
        if r.CAS in by_cas:
            name = by_cas[r.CAS][0]
            totals[name] = totals.get(name, 0.0) + float(r.Product_Pct)
            sources.setdefault(name, []).append(f"{r.Note_Name} (direct)")
    cons = getattr(data, "constituents", None)
    if cons is not None and len(cons):
        for r in mats.itertuples(index=False):
            for c in cons[cons["Natural_CAS"] == r.CAS].itertuples(index=False):
                if c.Constituent_CAS in by_cas:
                    name = by_cas[c.Constituent_CAS][0]
                    amt = float(r.Product_Pct) * float(c.Fraction_Used)
                    totals[name] = totals.get(name, 0.0) + amt
                    sources.setdefault(name, []).append(f"{r.Note_Name} x{float(c.Fraction_Used):g}")
    thr = float(al["Leave_On_Threshold_Pct"].iloc[0])
    rows = [{"Allergen": n, "CAS": next(v[1] for v in by_cas.values() if v[0] == n), "Product_Pct": round(v, 5), "Sources": "; ".join(sources[n])}
            for n, v in sorted(totals.items()) if v > thr]
    return pd.DataFrame(rows, columns=["Allergen", "CAS", "Product_Pct", "Sources"])


__all__ = ["formulate_product", "ProductResult"]
