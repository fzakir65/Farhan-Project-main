"""Zone B — appearance and odour STABILITY advisories for a concentrate in a bottle (colour, hydrolysis, solubility).

    flags = assess(concentrate, data, water_pct=8.5, alcohol_pct=78.0)     # -> list[StabilityFlag]

This is cosmetic / olfactory advice, never a safety verdict: nothing here changes a percentage. Every rule is a table
lookup in data/reference/curtis_stability.csv (Curtis & Williams 1994, monograph 'Stability' lines and Ch 11-12), joined
by CAS first and by name when a material has no CAS. Deterministic; no LLM.

Rules (page numbers are the Curtis PDF pages cited in the table):
  SCHIFF_BASE_COLOUR    an amine (indole, anthranilates, jasmin / orange-flower absolutes, mandarin) meets a carbonyl
                        (citral, fatty aldehydes, cinnamaldehyde, benzaldehyde, hydroxycitronellal, vanillin, musk ketone …):
                        yellow-to-brown colour develops as the Schiff base forms (p.146, 183, 213, 554)
  LIGHT_SENSITIVE       materials that darken in daylight (musk ketone, indole, citral, vanillin, cinnamaldehyde …) (p.181-230, 554)
  OXIDATION_PRONE       aldehydes, citral, expressed citrus oils: air oxidation -> sour / almondy notes, loss of freshness
  IRON_SENSITIVE        eugenol, vanillin, clove, cassia, methyl salicylate, birch tar (iron); farnesol (aluminium): discolour on contact
  ESTER_HYDROLYSIS      water in the bottle hydrolyses acetates / formates / propionates / butyrates back to alcohol + acid
                        (vinegar, butyric …); autocatalytic (p.525-526) — graded by the water content
  TERPENE_SOLUBILITY    alcohol strength below 75 % dissolves only traces of terpene-rich oils (lemon, orange, bergamot …):
                        cloudiness unless terpeneless grades are used (p.561)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

TABLE = "reference/curtis_stability.csv"
TERPENE_RICH = re.compile(r"\b(lemon|orange|bergamot|mandarin|tangerine|grapefruit|lime|yuzu|pomelo|clementine|citron|pine|juniper|cypress|fir)\b", re.I)
TERPENELESS = re.compile(r"terpeneless|terpene-free|deterpenated|washed", re.I)
HYDROLYSABLE = re.compile(r"\b(acetate|formate|propionate|butyrate|caproate|isobutyrate|tiglate)\b", re.I)
RESISTANT = re.compile(r"\b(benzoate|salicylate|cinnamate|phthalate)\b", re.I)        # Curtis: phenylethyl formate resists; aryl esters not his hydrolysis examples
ALCOHOL_STRENGTH_MIN = 75.0          # Curtis p.561: 75 % or weaker mixes with only very small proportions of terpene-rich oils
WATER_INFO, WATER_WARN = 10.0, 20.0  # ester-hydrolysis graded by the water share of the bottle (Curtis p.554: 20-30 % water in colognes)


@dataclass
class StabilityFlag:
    code: str
    severity: str                 # WARNING | INFO
    message: str
    materials: list[str] = field(default_factory=list)
    source: str = ""

    def __str__(self) -> str:
        return f"{self.severity} {self.code}: {self.message}" + (f" [{', '.join(self.materials)}]" if self.materials else "") + (f" ({self.source})" if self.source else "")


def load_table(data) -> pd.DataFrame:
    cached = getattr(data, "curtis_stability", None)
    if cached is not None and len(cached):
        return cached
    from load_data import DATA_DIR
    path = Path(DATA_DIR) / TABLE
    if not path.exists():
        return pd.DataFrame(columns=["Material", "CAS", "Classes", "Statement", "Source"])
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    try:
        data.curtis_stability = df
    except Exception:  # noqa: BLE001 - a frozen data object is fine, we just skip the cache
        pass
    return df


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s).casefold()).strip()


def _matches(table: pd.DataFrame, concentrate: pd.DataFrame) -> list[tuple[pd.Series, pd.Series]]:
    """(table row, formula row) pairs: CAS match first, then the table name contained in the note name (or vice versa)."""
    out = []
    by_cas: dict[str, list[int]] = {}
    for i, r in table.iterrows():
        for c in str(r["CAS"]).split("|"):
            if c.strip():
                by_cas.setdefault(c.strip(), []).append(i)
    for _, f in concentrate.iterrows():
        cas = str(f.get("CAS", "")).strip()
        hit = set(by_cas.get(cas, [])) if cas else set()
        if not hit:
            fn = _norm(f["Note_Name"])
            for i, r in table.iterrows():
                if r["CAS"] or "|" in r["Material"] or "(" in r["Material"] and r["Classes"] in ("process", "solvent"):
                    continue
                tn = _norm(re.sub(r"\(.*?\)", "", r["Material"]))
                if tn and (tn in fn or fn in tn):
                    hit.add(i)
        for i in sorted(hit):
            out.append((table.loc[i], f))
    return out


def assess(concentrate: pd.DataFrame, data, *, water_pct: float, alcohol_pct: float, antioxidant: bool = True,
           uv_absorber: bool = True) -> list[StabilityFlag]:
    """Advisories for `concentrate` (Note_Name, CAS, Pct) bottled with `water_pct` water and `alcohol_pct` ethanol (w/w of the bottle)."""
    table = load_table(data)
    flags: list[StabilityFlag] = []
    if concentrate is None or not len(concentrate):
        return flags
    c = concentrate.copy()
    c["Pct"] = pd.to_numeric(c["Pct"], errors="coerce").fillna(0.0)
    c = c[c["Pct"] > 0]
    pairs = _matches(table, c) if len(table) else []
    classes: dict[str, list[tuple[str, str]]] = {}
    for row, f in pairs:
        for k in str(row["Classes"]).split("|"):
            classes.setdefault(k, []).append((str(f["Note_Name"]), str(row["Source"])))

    def names(k: str) -> list[str]:
        return sorted({n for n, _ in classes.get(k, [])})

    def pages(k: str) -> str:
        return "; ".join(sorted({re.sub(r".*PDF ", "PDF ", s) for _, s in classes.get(k, [])}))

    amines, carbonyls = names("schiff_amine"), names("schiff_carbonyl")
    if amines and carbonyls:
        flags.append(StabilityFlag("SCHIFF_BASE_COLOUR", "WARNING",
                                   "an amine meets a carbonyl: expect the product to turn yellow then brown as the Schiff base forms (Aurantiol is this reaction "
                                   "done on purpose); the odour shifts too — amber glass, UV absorber, and a colour check after maturation",
                                   amines + carbonyls, "Curtis 1994 p.146, 183, 213, 554"))
    light = names("light")
    if light:
        flags.append(StabilityFlag("LIGHT_SENSITIVE", "INFO" if uv_absorber else "WARNING",
                                   ("darken in daylight — " + ("the base carries a UV absorber; still fill in amber or opaque packs" if uv_absorber
                                    else "no UV absorber in this base: amber / opaque packs are the only protection")), light, "Curtis 1994 " + pages("light")))
    air = names("air")
    if air:
        flags.append(StabilityFlag("OXIDATION_PRONE", "INFO" if antioxidant else "WARNING",
                                   ("oxidise in air (sour / almondy notes, loss of freshness) — " + ("antioxidant present; minimise headspace, store cool" if antioxidant
                                    else "no antioxidant in this base: add BHT or tocopherol, minimise headspace, store cool")), air, "Curtis 1994 " + pages("air")))
    iron = names("iron")
    if iron:
        flags.append(StabilityFlag("IRON_SENSITIVE", "INFO", "discolour on contact with iron (farnesol: aluminium) — compound and store in glass or stainless steel only",
                                   iron, "Curtis 1994 " + pages("iron")))
    esters = sorted({str(n) for n in c["Note_Name"] if HYDROLYSABLE.search(str(n)) and not RESISTANT.search(str(n))})
    if esters and water_pct >= WATER_INFO:
        sev = "WARNING" if water_pct >= WATER_WARN else "INFO"
        flags.append(StabilityFlag("ESTER_HYDROLYSIS", sev,
                                   f"{water_pct:g} % water in the bottle: these esters hydrolyse back to their alcohol plus an acid (acetic = vinegar, butyric = rancid, "
                                   "formic = sharp) and the acid speeds the reaction up; formates go first — keep water low, mature, re-smell before release",
                                   esters, "Curtis 1994 p.525-526"))
    strength = 100.0 * alcohol_pct / (alcohol_pct + water_pct) if (alcohol_pct + water_pct) > 0 else 100.0
    terpenes = sorted({str(n) for n in c["Note_Name"] if TERPENE_RICH.search(str(n)) and not TERPENELESS.search(str(n))})
    if terpenes and strength < ALCOHOL_STRENGTH_MIN:
        flags.append(StabilityFlag("TERPENE_SOLUBILITY", "WARNING",
                                   f"alcohol strength {strength:.0f} % of the solvent: below 75 % only very small proportions of terpene-rich oils stay dissolved — "
                                   "expect haze; use terpeneless grades of these oils or raise the alcohol", terpenes, "Curtis 1994 p.561"))
    order = {"WARNING": 0, "INFO": 1}
    flags.sort(key=lambda x: (order[x.severity], x.code))
    return flags


__all__ = ["assess", "StabilityFlag", "load_table"]
