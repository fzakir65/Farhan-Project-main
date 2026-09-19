"""Zone B — accords and family sketches taken from the books, expressed as formula_builder accord rows.

    rows, unresolved = curtis_base_rows("Rose", data)              # Curtis & Williams 1994 floral base (skeleton 3 / max)
    rows, unresolved = ohloff_accord_rows("Jasmine", data)         # Ohloff 2e Ch 9.4 basic accord (ingredients only)
    rows, unresolved = curtis_formula_rows("Basic Fougere-type perfume", data)   # a type formula, floral bases expanded
    match_term("muguet") -> ("curtis", "Lily-of-the-Valley") | ("ohloff", "Lily of the valley") | None

How the book numbers become builder inputs (deterministic, documented — the book's intent, the builder's rules):
  * a Curtis skeleton with parts -> Importance_Weight 5 for every material, Typical_Presence = parts / largest parts, so the
    shares the builder starts from are the book's proportions; the Layer is Curtis' own T/M/B; dilutions ('10 %') scale the
    parts (10 parts of a 10 % solution = 1 part of material).
  * an Ohloff accord has no parts: the base ingredient is Driver 5, the others Support 3; the builder's potency damping
    (indole, damascenone …) does the rest, exactly as Ohloff's 'halve or double' trials would.
  * a Curtis type formula: parts as printed; 'Rose base' / 'Jasmin base' / 'Muguet base' lines are expanded into that
    base's skeleton scaled to the parts; Layer from dataset2.
Book names are mapped to dataset2 note names through ALIASES (+ case-insensitive exact match); what cannot be mapped is
returned in `unresolved` and shows up as UNPLACEABLE in the builder — never silently dropped.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ALIASES = {  # normalised book name -> dataset2 Note_Name
    "phenylethyl alcohol": "Phenethyl Alcohol", "2 phenylethanol": "Phenethyl Alcohol", "phenylethyl acetate": "Phenethyl Acetate",
    "alpha ionone": "Alpha-Ionone", "beta ionone": "Beta-Ionone", "gamma methyl ionone": "Methyl Ionone", "isoraldeine gamma methyl ionone": "Methyl Ionone",
    "musk t ethylene brassylate": "Ethylene Brassylate", "musk t": "Ethylene Brassylate", "heliotropine": "Heliotropin",
    "aldehyde c11 enic": "Aldehyde C-11", "aldehyde c11": "Aldehyde C-11", "aldehyde c12 lauric": "Aldehyde C12 Lauric", "aldehyde c12": "Aldehyde C12 Lauric",
    "aldehyde c8": "Aldehyde C-8", "aldehyde c9": "Aldehyde C-9", "aldehyde c10": "Aldehyde C-10", "aldehyde c12 mna": "Aldehyde C-12 MNA",
    "aldehyde c14 peach gamma undecalactone": "Aldehyde C-14", "gamma undecalactone": "Aldehyde C-14", "aldehyde c 16": "Aldehyde C-16",
    "cis 3 hexenyl acetate": "Cis-3-Hexenyl Acetate", "cis 3 hexenol": "Cis-3-Hexenol", "beta damascenone": "Damascenone",
    "amylcinnamic aldehyde": "Amylcinnamic Aldehyde", "hexylcinnamic aldehyde": "Hexylcinnamic Aldehyde", "methyl iso eugenol": "Methyl Isoeugenol",
    "benzyl iso eugenol": "Benzyl Isoeugenol", "iso eugenyl acetate": "Isoeugenyl Acetate", "iso amyl salicylate": "Isoamyl Salicylate",
    "iso butyl phenylacetate": "Isobutyl Phenylacetate", "para cresyl acetate": "Para-Cresyl Acetate", "para cresyl iso butyrate": "Para-Cresyl Isobutyrate",
    "para cresyl phenylacetate": "Para-Cresyl Phenylacetate", "phenylacetaldehyde in phenylethyl alcohol": "Phenylacetaldehyde",
    "jasmin base": "__BASE__Jasmin", "rose base": "__BASE__Rose", "muguet lily of the valley base": "__BASE__Lily-of-the-Valley", "muguet base": "__BASE__Lily-of-the-Valley",
    "sandalwood oil e i": "Sandalwood Oil", "sandalwood oil": "Sandalwood Oil", "vetivert oil bourbon": "Vetiver Haiti", "vetivert oil reunion": "Vetiver Haiti", "vetivert oil": "Vetiver Oil",
    "oakmoss absolute decolourised": "Oakmoss Absolute", "patchouli oil light": "Patchouli Light", "neroli oil reconstituted": "Neroli Oil",
    "bergamot oil fcf": "Bergamot Oil FCF", "bergamot oil furanocoumarin free": "Bergamot Oil FCF", "bergamot oil italian": "Bergamot Oil", "bergamot oil": "Bergamot Oil",
    "lemon oil sicilian": "Lemon Oil", "lavender oil french": "Lavender Oil", "rosemary oil spanish": "Rosemary Oil", "thyme oil white": "Thyme Oil",
    "geranium oil reunion": "Geranium", "geranium oil bourbon": "Geranium", "geranium oil": "Geranium", "benzoin resinoid siam": "Benzoin Siam", "benzoin resinoid": "Benzoin",
    "petitgrain oil bigarade": "Petitgrain Bigarade", "petitgrain oil": "Petitgrain Oil", "ylang ylang oil extra": "Ylang Ylang Extra", "ylang ylang oil": "Ylang-Ylang",
    "civet tincture 3": "Civet Absolute", "ambroxan 1": "Ambroxan", "musk ketone": "Musk Ketone", "clary sage oil": "Clary Sage Oil", "clove bud oil": "Clove Bud Oil",
    "sweet orange oil": "Sweet Orange Oil", "hedione": "Hedione", "indole": "Indole", "1h indole": "Indole", "linalool": "Linalool", "citronellol": "Citronellol",
    "methyl anthranilate": "Methyl Anthranilate", "benzyl acetate": "Benzyl Acetate", "benzyl salicylate": "Benzyl Salicylate", "eugenol": "Eugenol",
    "cyclamen aldehyde": "Cyclamen Aldehyde", "maltol": "Maltol", "ethyl maltol": "Ethyl Maltol", "benzaldehyde": "Almond", "hexyl acetate": "Hexyl Acetate",   # dataset2 "Almond" IS benzaldehyde 100-52-7 (note_name_aliases.csv)
    "geranyl acetate": "Geranyl Acetate", "raspberry ketone": "Raspberry Ketone", "vanillin": "Vanillin", "coumarin": "Coumarin", "nerol": "Nerol", "geraniol": "Geraniol",
    "citral": "Citral", "linalyl acetate": "Linalyl Acetate", "benzyl alcohol": "Benzyl Alcohol", "alpha terpineol": "Alpha-Terpineol",
    "methyl eugenol": "Methyleugenol", "civet tincture": "Civet Absolute", "civet tincture 3": "Civet Absolute",
}
TERM_KEYS = {  # user term -> (source, book accord) ; the first hit wins, Curtis (quantified) before Ohloff
    "rose": [("curtis", "Rose"), ("ohloff", "Rose")], "jasmine": [("curtis", "Jasmin"), ("ohloff", "Jasmine")], "jasmin": [("curtis", "Jasmin"), ("ohloff", "Jasmine")],
    "muguet": [("curtis", "Lily-of-the-Valley"), ("ohloff", "Lily of the valley")], "lily of the valley": [("curtis", "Lily-of-the-Valley"), ("ohloff", "Lily of the valley")],
    "lily-of-the-valley": [("curtis", "Lily-of-the-Valley")], "carnation": [("curtis", "Carnation")], "orange blossom": [("curtis", "Orange Blossom"), ("ohloff", "Orange flower")],
    "orange flower": [("curtis", "Orange Blossom"), ("ohloff", "Orange flower")], "neroli": [("curtis", "Orange Blossom")], "violet": [("curtis", "Violet"), ("ohloff", "Violet")],
    "tuberose": [("curtis", "Tuberose"), ("ohloff", "Tuberose")], "strawberry": [("ohloff", "Strawberry")], "peach": [("ohloff", "Peach")], "apple": [("ohloff", "Apple")],
    "raspberry": [("ohloff", "Raspberry")], "pear": [("ohloff", "Pear")], "cherry": [("ohloff", "Cherry")],
}
FAMILY_KEYS = {  # invent(family=...) names that resolve to a Curtis type formula
    "chypre (curtis)": "Basic Chypre-type perfume", "fougere (curtis)": "Basic Fougere-type perfume", "fougère (curtis)": "Basic Fougere-type perfume",
    "lavender water": "Lavender Water compound", "eau de cologne": "Traditional Eau de Cologne", "cologne": "Traditional Eau de Cologne",
    "floral-aldehydic": "Aldehydic type perfume (Experiment 10.3)", "aldehydic": "Aldehydic type perfume (Experiment 10.3)",
}
FUNCTION_LAYER = {"Top": "Top", "Heart": "Heart", "Base": "Base"}


def _norm(s: str) -> str:
    s = str(s).casefold().replace("‐", "-")
    s = re.sub(r"\b(\d+(?:\.\d+)?)\s*%", r"\1", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def _ref(name: str) -> pd.DataFrame:
    from load_data import DATA_DIR
    p = Path(DATA_DIR) / "reference" / name
    return pd.read_csv(p, dtype=str, keep_default_na=False) if p.exists() else pd.DataFrame()


def resolve(name: str, data) -> str | None:
    """Book material name -> dataset2 Note_Name (exact case-insensitive, then ALIASES, then alias of the name without dilution)."""
    names = getattr(data, "_note_name_index", None)
    if names is None:
        names = {n.casefold(): n for n in data.notes["Note_Name"]}
        try:
            data._note_name_index = names
        except Exception:  # noqa: BLE001
            pass
    if name.casefold() in names:
        return names[name.casefold()]
    key = _norm(name)
    if key in ALIASES:
        return ALIASES[key]
    key2 = re.sub(r"\s+\d+(?:\s+\d+)?$", "", key)           # strip a trailing dilution figure
    if key2 in ALIASES:
        return ALIASES[key2]
    if key2 in names:
        return names[key2]
    return None


def _dilution(dil: str) -> float:
    try:
        return float(dil) / 100.0 if str(dil).strip() else 1.0
    except ValueError:
        return 1.0


def _rows_from_parts(parts: list[tuple[str, str, float]], accord_id: str, accord_name: str, category: str, data) -> tuple[pd.DataFrame, list[str]]:
    """[(dataset2 name, layer, parts)] -> builder rows; presence = parts / max so the shares start as the book's proportions."""
    parts = [(n, L, p) for n, L, p in parts if p > 0]
    if not parts:
        return pd.DataFrame(), []
    mx = max(p for _, _, p in parts)
    rows, unresolved = [], []
    for n, L, p in parts:
        rows.append({"Accord_ID": accord_id, "Accord_Name": accord_name, "Accord_Category": category, "Note_ID": "", "Note_Name": n,
                     "Note_Role": "Driver" if p == mx else "Support", "Layer": L, "Importance_Weight": 5, "Typical_Presence": round(p / mx, 4),
                     "Blend_Compatibility": 0.9, "Stability_Class": "Medium"})
    return pd.DataFrame(rows), unresolved


def curtis_base_rows(base: str, data, skeleton: int | None = None) -> tuple[pd.DataFrame, list[str]]:
    """A Curtis floral base as accord rows. skeleton=None -> the largest of the three skeleton figures per material
    (the fullest version); 1/2/3 -> that column only. Materials the catalogue lacks are returned in `unresolved`."""
    t = _ref("curtis_floral_bases.csv")
    t = t[(t["Base"].str.casefold() == base.casefold()) & (t["Section"].isin(["skeleton", "extension"]))]
    if t.empty:
        raise ValueError(f"unknown Curtis base {base!r}")
    parts, unresolved = [], []
    for r in t.itertuples(index=False):
        cols = [f"Skeleton_{skeleton}"] if skeleton else ["Skeleton_1", "Skeleton_2", "Skeleton_3"]
        vals = [float(getattr(r, c)) for c in cols if str(getattr(r, c)).strip()]
        if not vals or max(vals) <= 0:
            continue
        p = max(vals) * _dilution(r.Dilution_Pct)
        name = resolve(r.Material, data)
        if name and name.startswith("__BASE__") and name[len("__BASE__"):].casefold() != base.casefold():
            sub, sub_unres = curtis_base_rows(name[len("__BASE__"):], data, skeleton)     # a base inside a base (Violet uses Jasmin base)
            unresolved += sub_unres
            tot = float(sub["Typical_Presence"].sum()) if len(sub) else 0.0
            for srow in sub.itertuples(index=False):
                parts.append((srow.Note_Name, srow.Layer, p * float(srow.Typical_Presence) / tot if tot else 0.0))
            continue
        if name is None or name.startswith("__BASE__"):
            unresolved.append(r.Material)
            name = r.Material                                     # stays as written -> UNPLACEABLE in the builder
        parts.append((name, FUNCTION_LAYER[r.Function], p))
    rows, _ = _rows_from_parts(parts, f"CURTIS-{base.upper().replace(' ', '-')}", f"{base} base (Curtis 1994)", "Book floral base", data)
    return rows, unresolved


def ohloff_accord_rows(accord: str, data) -> tuple[pd.DataFrame, list[str]]:
    t = _ref("ohloff_accords.csv")
    t = t[t["Accord"].str.casefold() == accord.casefold()].sort_values("Position")
    if t.empty:
        raise ValueError(f"unknown Ohloff accord {accord!r}")
    rows, unresolved = [], []
    for r in t.itertuples(index=False):
        name = resolve(r.Ingredient, data)
        if name is None:
            unresolved.append(r.Ingredient)
            name = r.Ingredient
        first = int(r.Position) == 1
        rows.append({"Accord_ID": f"OHLOFF-{accord.upper().replace(' ', '-')}", "Accord_Name": f"{accord} accord (Ohloff 2e)", "Accord_Category": "Book accord",
                     "Note_ID": "", "Note_Name": name, "Note_Role": "Driver" if first else "Support", "Layer": "", "Importance_Weight": 5 if first else 3,
                     "Typical_Presence": 1.0, "Blend_Compatibility": 0.9, "Stability_Class": "Medium"})
    return pd.DataFrame(rows), unresolved


def curtis_formula_rows(formula: str, data, base_top_n: int | None = None) -> tuple[pd.DataFrame, list[str]]:
    """A Curtis type formula (chypre, fougere, lavender water, cologne, aldehydic) as accord rows; 'X base' lines expand
    into the base's skeleton (all of it, or only its `base_top_n` largest materials when used as a family sketch)."""
    t = _ref("curtis_formulas.csv")
    t = t[t["Formula"].str.casefold() == formula.casefold()]
    if t.empty:
        raise ValueError(f"unknown Curtis formula {formula!r}; one of {sorted(set(_ref('curtis_formulas.csv')['Formula']))}")
    vol = data.notes.drop_duplicates("Note_Name").set_index("Note_Name")["Volatility_Class"].to_dict()
    parts, unresolved = [], []
    for r in t.itertuples(index=False):
        p = float(r.Parts)
        m = re.match(r"^(.*?)\s+(\d+(?:\.\d+)?)%$", r.Material)          # 'Civet Tincture 3%' -> 3 % dilution
        mat, dil = (m.group(1), float(m.group(2)) / 100.0) if m else (r.Material, 1.0)
        name = resolve(mat, data)
        if name and name.startswith("__BASE__"):
            sub, sub_unres = curtis_base_rows(name[len("__BASE__"):], data)
            unresolved += sub_unres
            if base_top_n and len(sub) > base_top_n:
                sub = sub.sort_values(["Typical_Presence", "Note_Name"], ascending=[False, True]).head(base_top_n)
            tot = float(sub["Typical_Presence"].sum()) if len(sub) else 0.0
            for s in sub.itertuples(index=False):                       # the base's own proportions, scaled to the formula's parts
                parts.append((s.Note_Name, s.Layer, p * float(s.Typical_Presence) / tot if tot else 0.0))
            continue
        if name is None:
            unresolved.append(r.Material)
            name = mat
        layer = str(vol.get(name, "")).split("/")[0].strip()
        parts.append((name, layer if layer in FUNCTION_LAYER else "", p * dil))
    rows, _ = _rows_from_parts(parts, f"CURTIS-{formula.split(' ')[0].upper()}", f"{formula} (Curtis 1994)", "Book type formula", data)
    return rows, unresolved


def match_term(term: str) -> tuple[str, str] | None:
    key = term.strip().casefold()
    for k, opts in TERM_KEYS.items():
        if key == k or re.search(rf"\b{re.escape(k)}\b", key):
            return opts[0]
    return None


def family_formula(family: str) -> str | None:
    return FAMILY_KEYS.get(family.strip().casefold())


__all__ = ["curtis_base_rows", "ohloff_accord_rows", "curtis_formula_rows", "match_term", "family_formula", "resolve", "ALIASES", "TERM_KEYS", "FAMILY_KEYS"]
