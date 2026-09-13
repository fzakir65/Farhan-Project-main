"""Task 1 — load, clean and validate every data table into pandas DataFrames.

    from load_data import load_all
    data = load_all()            # Data object; data.issues lists everything found
    python load_data.py          # prints a data report; exit 2 if any ERROR issues

Zone-B code must obtain data only through this module. Nothing here calls an LLM.
All cleaning is deterministic (same files -> same frames -> same issues).

Design notes
- CAS is the join key between notes, IFRA, group rules and the UK/EU regulatory list.
  `cas_index()` maps every CAS listed in a table (including `All_CAS`) to its row.
- Cleaning repairs only what is unambiguous (whitespace, case, a detectable one-column
  shift in dataset1, exact duplicate rows). Everything else is *reported*, not guessed.
- Severity: ERROR = the data violates a rule the engine depends on (Zone B must not
  run on it until fixed); WARNING = gap that degrades results; INFO = statistic.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"

FILES = {
    "perfumes": "dataset1_perfumes.csv",
    "notes": "dataset2_notes.csv",
    "accords": "dataset3_accords.csv",
    "ifra_limits": "ifra_limits.csv",
    "group_rules": "group_rules.csv",
    "regulatory": "regulatory_uk.csv",
    "safety_caps": "safety_caps.csv",
    "reaction_rules": "reaction_rules.csv",
}

REQUIRED_COLUMNS = {
    "perfumes": ["Perfume_ID", "Perfume_Name", "Brand", "Fragrance_Family", "Main_Accords", "Top_Notes",
                 "Middle_Notes", "Base_Notes", "Gender", "Season", "Longevity", "Sillage", "Description",
                 "Mood_Vibe", "Occasion"],
    "notes": ["Note_ID", "Note_Name", "Chemical_Name", "CAS", "Volatility_Class", "Odor_Strength",
              "Accords_Used_In"],
    "accords": ["Accord_ID", "Accord_Name", "Accord_Category", "Note_ID", "Note_Name", "Note_Role", "Layer",
                "Importance_Weight", "Typical_Presence", "Blend_Compatibility", "Stability_Class"],
    "ifra_limits": ["Material_Name", "CAS", "IFRA_Type", "Category_4_Limit", "Phototoxic", "Notes", "IFRA_Key",
                    "IFRA_Standard_Name", "All_CAS", "Amendment", "Prohibition_Scope"],
    "group_rules": ["Group_Name", "Rule_Type", "Members_CAS", "Members_Names", "Rule", "Limit", "Limit_Basis"],
    "regulatory": ["Material_Name", "CAS", "Jurisdiction", "Status", "Fine_Fragrance_Limit_Pct", "Legal_Basis",
                   "Note", "Confidence"],
    "safety_caps": ["Material_Name", "CAS", "Max_Safe_Percent", "Reason", "Grade_Note", "Provisional"],
    "reaction_rules": ["Material_A", "CAS_A", "Material_B", "CAS_B", "Rule_Type", "Issue", "Action", "Limit_Basis"],
}

# --- controlled vocabularies -------------------------------------------------
IFRA_TYPE_PARTS = {"Restriction", "Prohibition", "Specification"}
PROHIBITION_SCOPES = {"grade", "category", "as_such", "all"}
LAYERS = {"Top", "Heart", "Base", "Top/Heart", "Heart/Base"}
NOTE_ROLES = {"Driver", "Support", "Modifier"}
STABILITY = {"High", "Medium", "Low"}
ODOR_STRENGTH = {"Low", "Medium", "Strong"}
ODOR_STRENGTH_ALIASES = {"high": "Strong", "soft": "Low", "light": "Low", "weak": "Low"}
GENDER_ALIASES = {"men": "Men", "male": "Men", "women": "Women", "female": "Women", "unisex": "Unisex"}
GROUP_RULE_TYPES = {"ifra_sum", "ifra_sum_of_fractions", "ifra_spec_coa"}
REACTION_RULE_TYPES = {"ifra", "ifra_spec", "olfactory"}
REG_STATUS = {"BANNED", "RESTRICTED"}
REG_JURISDICTIONS = {"GB+EU", "GB", "EU"}
SEASON_WORDS = re.compile(r"\b(?:spring|summer|fall|autumn|winter|all seasons|day|evening|night)\b", re.I)
CAS_PLACEHOLDERS = {"-", "n/a", "na", "none", "nan", "unknown", "tbd", "?"}
OFFICIAL_IFRA = "reference/ifra_51st_standards_overview.csv"

# Source text -> 1..5 (CLAUDE.md schema: Longevity(1-5), Sillage(1-5))
LONGEVITY_SCORE = {
    "very weak": 1, "weak": 2, "moderate": 3, "moderate to long lasting": 3, "long lasting": 4,
    "strong": 4, "very long lasting": 5, "eternal": 5,
}
SILLAGE_SCORE = {
    "intimate": 1, "soft": 1, "moderate": 2, "moderate to strong": 3, "strong": 3, "heavy": 4,
    "very strong": 4, "enormous": 5,
}


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------

@dataclass
class Issue:
    severity: str          # ERROR | WARNING | INFO
    table: str
    row: str               # row id or index, "" for table-level
    message: str

    def __str__(self) -> str:
        where = f"{self.table}[{self.row}]" if self.row else self.table
        return f"{self.severity:<7} {where}: {self.message}"


@dataclass
class Data:
    perfumes: pd.DataFrame
    notes: pd.DataFrame
    accords: pd.DataFrame
    ifra_limits: pd.DataFrame
    group_rules: pd.DataFrame
    regulatory: pd.DataFrame
    safety_caps: pd.DataFrame
    reaction_rules: pd.DataFrame
    issues: list[Issue] = field(default_factory=list)
    # convenience frames produced by cross-validation
    unmatched_accord_notes: pd.DataFrame = field(default_factory=pd.DataFrame)
    regulatory_overrides: pd.DataFrame = field(default_factory=pd.DataFrame)
    notes_regulated: pd.DataFrame = field(default_factory=pd.DataFrame)

    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "ERROR"]

    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "WARNING"]


CAS_RE = re.compile(r"^(\d{2,7})-(\d{2})-(\d)$")


def is_valid_cas(cas) -> bool:
    """CAS Registry Number: NNNNNNN-NN-C with check digit = sum(i * digit_i) mod 10,
    digits weighted from the right starting at 1 (check digit excluded)."""
    if cas is None or (isinstance(cas, float) and pd.isna(cas)):
        return False
    m = CAS_RE.match(str(cas).strip())
    if not m:
        return False
    digits = m.group(1) + m.group(2)
    check = sum((i + 1) * int(d) for i, d in enumerate(reversed(digits))) % 10
    return check == int(m.group(3))


def normalize_name(s) -> str:
    """Lower-case, collapse whitespace, unify dashes/quotes — for name matching only."""
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    s = str(s).replace("’", "'").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip().lower()


def normalize_layer(s) -> str:
    """'Top / Heart' -> 'Top/Heart'; title-case single layers."""
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    parts = [p.strip().capitalize() for p in str(s).split("/")]
    return "/".join(parts)


def split_multi(s, sep: str = ";") -> list[str]:
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return []
    return [p.strip() for p in str(s).split(sep) if p.strip()]


def split_cas_list(s) -> list[str]:
    return split_multi(s, sep="|")


def _to_float(x) -> float:
    """'' / junk -> NaN. (pandas stores None as NaN anyway, so we standardise on NaN.)"""
    try:
        return float(str(x).replace(",", ".").strip())
    except (TypeError, ValueError):
        return float("nan")


def _isnum(x) -> bool:
    return x is not None and not pd.isna(x)


def _read(path: Path, table: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{table}: {path} not found — run `python data/build_datasets.py`")
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8")
    missing = [c for c in REQUIRED_COLUMNS[table] if c not in df.columns]
    if missing:
        raise ValueError(f"{table}: missing required columns {missing}")
    for c in df.columns:
        df[c] = df[c].str.strip()
    return df


def cas_index(df: pd.DataFrame, cas_col: str = "CAS", all_cas_col: str | None = "All_CAS") -> dict[str, int]:
    """Map every CAS a row lists (primary + All_CAS) -> positional row index. First wins."""
    idx: dict[str, int] = {}
    for i, row in enumerate(df.itertuples(index=False)):
        r = row._asdict()
        cands = [r.get(cas_col, "")]
        if all_cas_col and all_cas_col in r:
            cands += split_cas_list(r[all_cas_col])
        for c in cands:
            c = str(c).strip()
            if c and c not in idx:
                idx[c] = i
    return idx


# ----------------------------------------------------------------------------
# per-table loaders
# ----------------------------------------------------------------------------

def load_perfumes(path: Path) -> tuple[pd.DataFrame, list[Issue]]:
    df = _read(path, "perfumes")
    issues: list[Issue] = []

    # Detectable one-column shift in the source (Gender holds season words, Sillage holds a
    # sentence): move everything one column right; Gender becomes unknown.
    shifted = df["Gender"].str.contains(SEASON_WORDS) & (df["Sillage"].str.len() > 25)
    for i in df.index[shifted]:
        df.loc[i, ["Description", "Sillage", "Longevity", "Season", "Gender"]] = [
            df.at[i, "Sillage"], df.at[i, "Longevity"], df.at[i, "Season"], df.at[i, "Gender"], ""]
        issues.append(Issue("WARNING", "perfumes", df.at[i, "Perfume_ID"],
                            "columns were shifted by one in the source; repaired, Gender now unknown"))

    df["Gender"] = df["Gender"].map(lambda g: GENDER_ALIASES.get(g.lower(), g))
    unknown_gender = df[~df["Gender"].isin({"Men", "Women", "Unisex", ""})]
    for _, r in unknown_gender.iterrows():
        issues.append(Issue("WARNING", "perfumes", r["Perfume_ID"], f"unrecognised Gender {r['Gender']!r}"))

    df["Longevity_Score"] = df["Longevity"].map(lambda s: LONGEVITY_SCORE.get(re.sub(r"^\S*\d\S*\s+", "", s.lower())))
    df["Sillage_Score"] = df["Sillage"].map(lambda s: SILLAGE_SCORE.get(s.lower()))
    for col, score in (("Longevity", "Longevity_Score"), ("Sillage", "Sillage_Score")):
        for _, r in df[df[score].isna() & (df[col] != "")].iterrows():
            issues.append(Issue("WARNING", "perfumes", r["Perfume_ID"], f"unmapped {col} value {r[col]!r}"))
    df["Longevity_Score"] = df["Longevity_Score"].astype("Int64")
    df["Sillage_Score"] = df["Sillage_Score"].astype("Int64")

    for col in ("Main_Accords", "Top_Notes", "Middle_Notes", "Base_Notes", "Season"):
        df[f"{col}_List"] = df[col].map(split_multi)

    dup = df["Perfume_ID"].duplicated(keep=False)
    if dup.any():
        issues.append(Issue("ERROR", "perfumes", "", f"{dup.sum()} rows share a Perfume_ID"))
    if (df["Mood_Vibe"] == "").all():
        issues.append(Issue("INFO", "perfumes", "", "Mood_Vibe has no source data yet (all empty)"))
    if (df["Occasion"] == "").all():
        issues.append(Issue("INFO", "perfumes", "", "Occasion has no source data yet (all empty)"))
    return df, issues


def load_notes(path: Path) -> tuple[pd.DataFrame, list[Issue]]:
    df = _read(path, "notes")
    issues: list[Issue] = []

    before = len(df)
    df = df.drop_duplicates().reset_index(drop=True)
    if len(df) < before:
        issues.append(Issue("INFO", "notes", "", f"dropped {before - len(df)} exact duplicate rows"))

    df["Volatility_Class"] = df["Volatility_Class"].map(normalize_layer)
    for _, r in df[~df["Volatility_Class"].isin(LAYERS)].iterrows():
        issues.append(Issue("ERROR", "notes", r["Note_ID"], f"Volatility_Class {r['Volatility_Class']!r} not in {sorted(LAYERS)}"))

    df["Odor_Strength"] = df["Odor_Strength"].map(
        lambda s: ODOR_STRENGTH_ALIASES.get(s.lower(), s.capitalize()) if s else "")
    for _, r in df[~df["Odor_Strength"].isin(ODOR_STRENGTH | {""})].iterrows():
        issues.append(Issue("WARNING", "notes", r["Note_ID"], f"Odor_Strength {r['Odor_Strength']!r} unrecognised"))

    # '-' etc. mean "no CAS" (accords, bases, captive molecules); a present-but-wrong CAS is
    # an ERROR because every safety lookup keys on it — a wrong CAS can let a banned material through.
    df["CAS"] = df["CAS"].map(lambda c: "" if c.lower() in CAS_PLACEHOLDERS else c)
    df["CAS_Valid"] = df["CAS"].map(is_valid_cas)
    bad_cas = df[(df["CAS"] != "") & ~df["CAS_Valid"]]
    for _, r in bad_cas.iterrows():
        issues.append(Issue("ERROR", "notes", r["Note_ID"], f"CAS {r['CAS']!r} fails the CAS checksum for {r['Note_Name']!r}"))
    if len(bad_cas):
        issues.append(Issue("ERROR", "notes", "", f"{len(bad_cas)} notes carry a CAS that fails the checksum — "
                                                  "fix in source before Zone B can trust CAS joins"))
    n_nocas = int((df["CAS"] == "").sum())
    if n_nocas:
        issues.append(Issue("WARNING", "notes", "", f"{n_nocas} notes have no CAS — safety lookups will miss them (accords/bases are expected here)"))

    df["Note_Name_Norm"] = df["Note_Name"].map(normalize_name)
    df["Accords_Used_In_List"] = df["Accords_Used_In"].map(split_multi)

    # Same name, different chemistry: cannot be resolved automatically.
    grp = df.groupby("Note_Name_Norm")
    conflicts = grp.agg(n=("Note_ID", "size"), cas=("CAS", "nunique"), vol=("Volatility_Class", "nunique"))
    for name, r in conflicts[(conflicts["cas"] > 1) | (conflicts["vol"] > 1)].iterrows():
        variants = df[df["Note_Name_Norm"] == name][["Note_ID", "CAS", "Volatility_Class"]].drop_duplicates()
        issues.append(Issue("WARNING", "notes", name,
                            f"{int(r['n'])} rows share this name with conflicting CAS/volatility: "
                            + "; ".join(f"{v.Note_ID} {v.CAS or '-'} {v.Volatility_Class}" for v in variants.itertuples())))
    return df, issues


def load_accords(path: Path) -> tuple[pd.DataFrame, list[Issue]]:
    df = _read(path, "accords")
    issues: list[Issue] = []
    df["Layer"] = df["Layer"].map(normalize_layer)
    df["Note_Role"] = df["Note_Role"].str.capitalize()
    df["Stability_Class"] = df["Stability_Class"].str.capitalize()
    df["Note_Name_Norm"] = df["Note_Name"].map(normalize_name)
    df["Accord_Name_Norm"] = df["Accord_Name"].map(normalize_name)

    for col, vocab in (("Layer", LAYERS), ("Note_Role", NOTE_ROLES), ("Stability_Class", STABILITY)):
        for _, r in df[~df[col].isin(vocab)].iterrows():
            issues.append(Issue("ERROR", "accords", f"{r['Accord_ID']}/{r['Note_ID']}", f"{col} {r[col]!r} not in {sorted(vocab)}"))

    for col, lo, hi in (("Importance_Weight", 1, 5), ("Typical_Presence", 0, 1), ("Blend_Compatibility", 0, 1)):
        df[col] = pd.to_numeric(df[col], errors="coerce")
        bad = df[df[col].isna() | (df[col] < lo) | (df[col] > hi)]
        for _, r in bad.iterrows():
            issues.append(Issue("ERROR", "accords", f"{r['Accord_ID']}/{r['Note_ID']}", f"{col}={r[col]} outside [{lo}, {hi}]"))

    short = df[df["Accord_Name"].str.len() < 3]["Accord_Name"].unique()
    for name in short:
        issues.append(Issue("WARNING", "accords", name, "suspiciously short Accord_Name (truncated in source?)"))
    return df, issues


def load_ifra_limits(path: Path) -> tuple[pd.DataFrame, list[Issue]]:
    df = _read(path, "ifra_limits")
    issues: list[Issue] = []
    df["Category_4_Limit"] = df["Category_4_Limit"].map(_to_float)
    df["All_CAS_List"] = df["All_CAS"].map(split_cas_list)
    df["Type_Parts"] = df["IFRA_Type"].map(lambda t: [p for p in t.split("_") if p])
    df["Is_Prohibited_As_Such"] = df["Type_Parts"].map(lambda p: p == ["Prohibition"])
    df["Is_Restricted"] = df["Type_Parts"].map(lambda p: "Restriction" in p)
    df["Has_Prohibited_Grade"] = df["Type_Parts"].map(lambda p: "Prohibition" in p and p != ["Prohibition"])

    for _, r in df.iterrows():
        rid = r["Material_Name"]
        if not set(r["Type_Parts"]) <= IFRA_TYPE_PARTS or not r["Type_Parts"]:
            issues.append(Issue("ERROR", "ifra_limits", rid, f"IFRA_Type {r['IFRA_Type']!r} not made of {sorted(IFRA_TYPE_PARTS)}"))
        if not is_valid_cas(r["CAS"]):
            issues.append(Issue("ERROR", "ifra_limits", rid, f"invalid CAS {r['CAS']!r}"))
        for c in r["All_CAS_List"]:
            if not is_valid_cas(c):
                issues.append(Issue("ERROR", "ifra_limits", rid, f"invalid CAS {c!r} in All_CAS"))
        if r["CAS"] not in r["All_CAS_List"]:
            issues.append(Issue("ERROR", "ifra_limits", rid, "primary CAS is not in All_CAS"))
        if r["Is_Restricted"] and not _isnum(r["Category_4_Limit"]):
            issues.append(Issue("ERROR", "ifra_limits", rid, "Restriction without a numeric Category_4_Limit"))
        if r["Is_Prohibited_As_Such"] and _isnum(r["Category_4_Limit"]):
            issues.append(Issue("ERROR", "ifra_limits", rid, "pure Prohibition must not carry a Category_4_Limit"))
        if _isnum(r["Category_4_Limit"]) and not (0 < r["Category_4_Limit"] <= 100):
            issues.append(Issue("ERROR", "ifra_limits", rid, f"Category_4_Limit {r['Category_4_Limit']} outside (0, 100]"))
        if r["Phototoxic"] not in {"Yes", "No"}:
            issues.append(Issue("ERROR", "ifra_limits", rid, f"Phototoxic must be Yes/No, got {r['Phototoxic']!r}"))
        has_prohibition = "Prohibition" in r["Type_Parts"]
        if has_prohibition and r["Prohibition_Scope"] not in PROHIBITION_SCOPES:
            issues.append(Issue("ERROR", "ifra_limits", rid, f"Prohibition_Scope must be one of {sorted(PROHIBITION_SCOPES)}, got {r['Prohibition_Scope']!r}"))
        if not has_prohibition and r["Prohibition_Scope"]:
            issues.append(Issue("ERROR", "ifra_limits", rid, "Prohibition_Scope set on a row without a Prohibition"))
        if r["Is_Prohibited_As_Such"] and r["Prohibition_Scope"] != "all":
            issues.append(Issue("ERROR", "ifra_limits", rid, "pure Prohibition must have Prohibition_Scope=all"))
        if not re.fullmatch(r"IFRA_STD_\d{3}", r["IFRA_Key"]):
            issues.append(Issue("ERROR", "ifra_limits", rid, f"bad IFRA_Key {r['IFRA_Key']!r}"))
    dup = df["IFRA_Key"].duplicated(keep=False)
    if dup.any():
        issues.append(Issue("ERROR", "ifra_limits", "", f"duplicate IFRA_Key rows: {sorted(df[dup]['IFRA_Key'].unique())}"))
    return df, issues


def load_group_rules(path: Path) -> tuple[pd.DataFrame, list[Issue]]:
    df = _read(path, "group_rules")
    issues: list[Issue] = []
    df["Members_CAS_List"] = df["Members_CAS"].map(split_cas_list)
    df["Limit"] = df["Limit"].map(_to_float)
    for _, r in df.iterrows():
        if r["Rule_Type"] not in GROUP_RULE_TYPES:
            issues.append(Issue("ERROR", "group_rules", r["Group_Name"], f"Rule_Type {r['Rule_Type']!r} not in {sorted(GROUP_RULE_TYPES)}"))
        if not _isnum(r["Limit"]) or r["Limit"] <= 0:
            issues.append(Issue("ERROR", "group_rules", r["Group_Name"], "Limit must be a positive number"))
        if len(r["Members_CAS_List"]) < 2:
            issues.append(Issue("ERROR", "group_rules", r["Group_Name"], "a group needs at least two member CAS"))
        for c in r["Members_CAS_List"]:
            if not is_valid_cas(c):
                issues.append(Issue("ERROR", "group_rules", r["Group_Name"], f"invalid member CAS {c!r}"))
    return df, issues


def load_regulatory(path: Path) -> tuple[pd.DataFrame, list[Issue]]:
    df = _read(path, "regulatory")
    issues: list[Issue] = []
    df["Fine_Fragrance_Limit_Pct"] = df["Fine_Fragrance_Limit_Pct"].map(_to_float)
    for _, r in df.iterrows():
        rid = r["Material_Name"]
        if r["Status"] not in REG_STATUS:
            issues.append(Issue("ERROR", "regulatory", rid, f"Status {r['Status']!r} not in {sorted(REG_STATUS)}"))
        if r["Jurisdiction"] not in REG_JURISDICTIONS:
            issues.append(Issue("ERROR", "regulatory", rid, f"Jurisdiction {r['Jurisdiction']!r} not in {sorted(REG_JURISDICTIONS)}"))
        if not is_valid_cas(r["CAS"]):
            issues.append(Issue("ERROR", "regulatory", rid, f"invalid CAS {r['CAS']!r}"))
        if r["Status"] == "RESTRICTED" and not _isnum(r["Fine_Fragrance_Limit_Pct"]):
            issues.append(Issue("ERROR", "regulatory", rid, "RESTRICTED without a numeric Fine_Fragrance_Limit_Pct"))
        if r["Status"] == "BANNED" and _isnum(r["Fine_Fragrance_Limit_Pct"]):
            issues.append(Issue("ERROR", "regulatory", rid, "BANNED must not carry a limit"))
        if r["Confidence"] not in {"high", "medium", "low"}:
            issues.append(Issue("ERROR", "regulatory", rid, f"Confidence {r['Confidence']!r} must be high/medium/low"))
    n_med = int((df["Confidence"] != "high").sum())
    if n_med:
        issues.append(Issue("WARNING", "regulatory", "", f"{n_med} entries are below 'high' confidence — verify against the current UK Annex II/III text"))
    return df, issues


def load_safety_caps(path: Path) -> tuple[pd.DataFrame, list[Issue]]:
    df = _read(path, "safety_caps")
    issues: list[Issue] = []
    df["Max_Safe_Percent"] = df["Max_Safe_Percent"].map(_to_float)
    for _, r in df.iterrows():
        rid = r["Material_Name"]
        if not _isnum(r["Max_Safe_Percent"]) or not (0 < r["Max_Safe_Percent"] <= 100):
            issues.append(Issue("ERROR", "safety_caps", rid, f"Max_Safe_Percent {r['Max_Safe_Percent']} outside (0, 100]"))
        if r["Provisional"] not in {"Yes", "No"}:
            issues.append(Issue("ERROR", "safety_caps", rid, f"Provisional must be Yes/No, got {r['Provisional']!r}"))
        if r["CAS"] == "":
            issues.append(Issue("WARNING", "safety_caps", rid, "no CAS — cap can only be matched by name"))
        elif not is_valid_cas(r["CAS"]):
            issues.append(Issue("ERROR", "safety_caps", rid, f"invalid CAS {r['CAS']!r}"))
    df["Material_Name_Norm"] = df["Material_Name"].map(normalize_name)
    return df, issues


def load_reaction_rules(path: Path) -> tuple[pd.DataFrame, list[Issue]]:
    df = _read(path, "reaction_rules")
    issues: list[Issue] = []
    for _, r in df.iterrows():
        rid = f"{r['Material_A']} + {r['Material_B']}"
        if r["Rule_Type"] not in REACTION_RULE_TYPES:
            issues.append(Issue("ERROR", "reaction_rules", rid, f"Rule_Type {r['Rule_Type']!r} not in {sorted(REACTION_RULE_TYPES)}"))
        for c in (r["CAS_A"], r["CAS_B"]):
            if not is_valid_cas(c):
                issues.append(Issue("ERROR", "reaction_rules", rid, f"invalid CAS {c!r}"))
    return df, issues


# ----------------------------------------------------------------------------
# cross-table validation
# ----------------------------------------------------------------------------

def official_ifra_types(data_dir: Path) -> dict[str, tuple[str, str]]:
    """CAS -> (IFRA_STD key, Standard type) over the *whole* official 51st Amendment table,
    so the report can tell 'IFRA also prohibits this' from 'IFRA has no Standard'."""
    path = data_dir / OFFICIAL_IFRA
    if not path.exists():
        return {}
    off = pd.read_csv(path, skiprows=2, dtype=str, keep_default_na=False)
    out: dict[str, tuple[str, str]] = {}
    for _, r in off.iterrows():
        for cas in re.findall(r"\d{2,7}-\d{2}-\d", r["CAS numbers"]):
            out.setdefault(cas, (r["Key"], r["IFRA Standard type"]))
    return out


def cross_validate(d: Data, data_dir: Path = DATA_DIR) -> list[Issue]:
    issues: list[Issue] = []
    ifra_idx = cas_index(d.ifra_limits)
    reg_idx = cas_index(d.regulatory, all_cas_col=None)
    note_cas = set(d.notes.loc[d.notes["CAS"] != "", "CAS"])
    official = official_ifra_types(data_dir)

    # 1. Rule 10: every accord note must exist in dataset2 (by name; IDs reported too)
    note_names = set(d.notes["Note_Name_Norm"])
    miss = d.accords[~d.accords["Note_Name_Norm"].isin(note_names)]
    d.unmatched_accord_notes = (miss.groupby(["Note_Name", "Note_ID"]).size().reset_index(name="rows_in_accords")
                                .sort_values("rows_in_accords", ascending=False).reset_index(drop=True))
    if len(miss):
        issues.append(Issue("ERROR", "accords", "",
                            f"{d.unmatched_accord_notes.shape[0]} distinct note names ({len(miss)} rows) are not in "
                            f"dataset2 — formula builder cannot place them (see data.unmatched_accord_notes)"))
    id_miss = int((~d.accords["Note_ID"].isin(set(d.notes["Note_ID"]))).sum())
    if id_miss:
        issues.append(Issue("WARNING", "accords", "", f"{id_miss} accord rows reference a Note_ID absent from dataset2"))

    # 2. safety caps must never exceed an IFRA limit, cap a prohibited material, or contradict a ban
    for _, cap in d.safety_caps.iterrows():
        if not cap["CAS"]:
            continue
        i = ifra_idx.get(cap["CAS"])
        if i is not None:
            lim = d.ifra_limits.iloc[i]
            if lim["Is_Prohibited_As_Such"]:
                issues.append(Issue("ERROR", "safety_caps", cap["Material_Name"], f"caps an IFRA-prohibited material ({lim['IFRA_Key']})"))
            elif lim["Is_Restricted"] and _isnum(lim["Category_4_Limit"]) and cap["Max_Safe_Percent"] > lim["Category_4_Limit"]:
                issues.append(Issue("ERROR", "safety_caps", cap["Material_Name"],
                                    f"cap {cap['Max_Safe_Percent']} exceeds IFRA Cat 4 limit {lim['Category_4_Limit']} ({lim['IFRA_Key']})"))
            elif lim["Has_Prohibited_Grade"] and not cap["Grade_Note"]:
                issues.append(Issue("WARNING", "safety_caps", cap["Material_Name"], f"{lim['IFRA_Key']} prohibits a grade of this material but Grade_Note is empty"))
        j = reg_idx.get(cap["CAS"])
        if j is not None:
            reg = d.regulatory.iloc[j]
            if reg["Status"] == "BANNED":
                issues.append(Issue("ERROR", "safety_caps", cap["Material_Name"], f"caps a material BANNED in {reg['Jurisdiction']}"))
            elif _isnum(reg["Fine_Fragrance_Limit_Pct"]) and cap["Max_Safe_Percent"] > reg["Fine_Fragrance_Limit_Pct"]:
                issues.append(Issue("ERROR", "safety_caps", cap["Material_Name"],
                                    f"cap {cap['Max_Safe_Percent']} exceeds UK/EU limit {reg['Fine_Fragrance_Limit_Pct']}"))

    # 3. where the regulatory layer overrides IFRA (report — this is by design)
    rows = []
    for _, reg in d.regulatory.iterrows():
        i = ifra_idx.get(reg["CAS"])
        ifra = d.ifra_limits.iloc[i] if i is not None else None
        ifra_lim = ifra["Category_4_Limit"] if ifra is not None and _isnum(ifra["Category_4_Limit"]) else None
        key, off_type = official.get(reg["CAS"], (None, None))
        if ifra is not None:
            key, off_type = ifra["IFRA_Key"], ifra["IFRA_Type"].upper()
        # PROHIBITION / PROHIBITION_SPECIFICATION / PROHIBITION_RESTRICTION all prohibit the material
        # as such (a spec or natural-trace allowance may follow) -> the ban agrees with IFRA.
        ifra_prohibits = bool(off_type) and off_type.startswith("PROHIBITION")
        reg_lim = reg["Fine_Fragrance_Limit_Pct"] if _isnum(reg["Fine_Fragrance_Limit_Pct"]) else None
        # UK/EU is stricter than IFRA when it bans something IFRA merely restricts / has no Standard for,
        # or caps a restricted material below the IFRA Cat 4 limit.
        overrides = (reg["Status"] == "BANNED" and not ifra_prohibits) or (
            reg["Status"] == "RESTRICTED" and ifra_lim is not None and reg_lim is not None and reg_lim < ifra_lim)
        rows.append({"Material_Name": reg["Material_Name"], "CAS": reg["CAS"], "Status": reg["Status"],
                     "UK_EU_Limit": reg_lim, "IFRA_Key": key,
                     "IFRA_Type": off_type, "IFRA_Cat4_Limit": ifra_lim, "In_ifra_limits_csv": ifra is not None,
                     "Overrides_IFRA": bool(overrides), "In_Notes_Catalog": reg["CAS"] in note_cas})
    d.regulatory_overrides = pd.DataFrame(rows)
    n_over = int(d.regulatory_overrides["Overrides_IFRA"].sum())
    n_agree = int(len(d.regulatory_overrides) - n_over)
    issues.append(Issue("INFO", "regulatory", "", f"{n_over} UK/EU entries are stricter than IFRA and override it; "
                                                  f"{n_agree} agree with an IFRA prohibition (see data.regulatory_overrides)"))

    # 4. which catalogue notes are touched by IFRA / regulatory
    notes_cas = d.notes[d.notes["CAS"] != ""]
    reg_hits = notes_cas[notes_cas["CAS"].isin(reg_idx)]
    ifra_hits = notes_cas[notes_cas["CAS"].isin(ifra_idx)]
    d.notes_regulated = (reg_hits.assign(Status=lambda x: x["CAS"].map(lambda c: d.regulatory.iloc[reg_idx[c]]["Status"]))
                         [["Note_ID", "Note_Name", "CAS", "Status"]].drop_duplicates().reset_index(drop=True))
    issues.append(Issue("INFO", "notes", "", f"{ifra_hits['Note_ID'].nunique()} notes have an IFRA Standard; "
                                             f"{reg_hits['Note_ID'].nunique()} are on the UK/EU list"))
    for _, r in d.notes_regulated[d.notes_regulated["Status"] == "BANNED"].drop_duplicates("Note_ID").iterrows():
        issues.append(Issue("WARNING", "notes", r["Note_ID"], f"{r['Note_Name']!r} is BANNED in the UK/EU — Zone B will reject any formula using it"))

    # 5. reaction / group rule members should be known materials
    known = set(ifra_idx) | note_cas
    for _, r in d.reaction_rules.iterrows():
        for c in (r["CAS_A"], r["CAS_B"]):
            if c not in known:
                issues.append(Issue("WARNING", "reaction_rules", f"{r['Material_A']} + {r['Material_B']}", f"CAS {c} is in neither notes nor ifra_limits"))
    for _, g in d.group_rules.iterrows():
        unknown = [c for c in g["Members_CAS_List"] if c not in ifra_idx]
        if unknown:
            issues.append(Issue("WARNING", "group_rules", g["Group_Name"], f"{len(unknown)} member CAS not covered by ifra_limits All_CAS: {unknown[:4]}{'…' if len(unknown) > 4 else ''}"))
    return issues


# ----------------------------------------------------------------------------
# entry points
# ----------------------------------------------------------------------------

def load_all(data_dir: Path | str = DATA_DIR) -> Data:
    data_dir = Path(data_dir)
    loaders = {
        "perfumes": load_perfumes, "notes": load_notes, "accords": load_accords,
        "ifra_limits": load_ifra_limits, "group_rules": load_group_rules, "regulatory": load_regulatory,
        "safety_caps": load_safety_caps, "reaction_rules": load_reaction_rules,
    }
    frames, issues = {}, []
    for table, fn in loaders.items():
        df, iss = fn(data_dir / FILES[table])
        frames[table], issues = df, issues + iss
    data = Data(**frames, issues=issues)
    data.issues += cross_validate(data, data_dir)
    return data


def report(d: Data) -> str:
    lines = ["DATA REPORT", "=" * 60]
    for table in FILES:
        df = getattr(d, table)
        lines.append(f"{table:<16} {len(df):>5} rows  {df.shape[1]:>3} cols")
    lines += ["", f"issues: {len(d.errors())} ERROR, {len(d.warnings())} WARNING, "
                  f"{len([i for i in d.issues if i.severity == 'INFO'])} INFO", ""]
    for sev in ("ERROR", "WARNING", "INFO"):
        group = [i for i in d.issues if i.severity == sev]
        if not group:
            continue
        lines.append(f"--- {sev} ({len(group)}) ---")
        shown = group if sev != "WARNING" else group[:40]
        lines += [f"  {i}" for i in shown]
        if len(shown) < len(group):
            lines.append(f"  … {len(group) - len(shown)} more WARNING lines omitted (see data.issues)")
        lines.append("")
    if len(d.regulatory_overrides):
        ov = d.regulatory_overrides[d.regulatory_overrides["Overrides_IFRA"]]
        lines.append("UK/EU entries that override IFRA (stricter than the 51st Amendment):")
        for _, r in ov.iterrows():
            lim = "BANNED" if r["Status"] == "BANNED" else f"cap {r['UK_EU_Limit']}"
            if r["IFRA_Key"] is None:
                ifra = "no IFRA Standard"
            else:
                val = "" if r["IFRA_Cat4_Limit"] is None else f" {r['IFRA_Cat4_Limit']}"
                ifra = f"IFRA {r['IFRA_Type']}{val} ({r['IFRA_Key']})"
            flag = "  [in notes catalogue]" if r["In_Notes_Catalog"] else ""
            lines.append(f"  {r['Material_Name']:<62} {lim:<10} vs {ifra}{flag}")
        banned_notes = d.notes_regulated[d.notes_regulated["Status"] == "BANNED"]
        if len(banned_notes):
            lines += ["", "Catalogue notes the regulatory layer will REJECT:"]
            for _, r in banned_notes.drop_duplicates("Note_ID").iterrows():
                lines.append(f"  {r['Note_ID']}  {r['Note_Name']}  ({r['CAS']})")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    data_dir = Path(argv[0]) if argv else DATA_DIR
    d = load_all(data_dir)
    print(report(d))
    return 2 if d.errors() else 0


if __name__ == "__main__":
    sys.exit(main())
