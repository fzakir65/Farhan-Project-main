"""
End-to-end preprocessing pipeline for the Perfumery ML project (plan section F).

Implements, in order:
  P1  (F.1) dictionary bijectivity checks
  P2  (F.1) note-vocabulary bridge between the rule-recipe space (accord_note)
            and the real-perfume space (perfume_note), via CAS equality +
            token/stem name matching + fuzzy fallback, with confidence tiers
            and a unified note-id mapping (union-find over accepted matches)
  P3  (F.1) resolution proposals for unmapped_accord_tokens
  P4  (F.2) recipe cleanup: exact-duplicate-row dedup, per-accord
            renormalisation to 100%, note-level aggregation, invariant checks
  P5  (F.2) blended cross-accord recipe lookup for every (primary, secondary)
            pair in training_examples
  P6  (F.3) note feature table: categorical fills + numeric imputation by
            chemical_family mean with is-imputed indicators
  P7  (F.4) training-input feature table: descriptor/avoid multi-hot,
            categorical vocab maps, feature spec for the Stage-1 encoder
  P8  (F.5) stratified 80/10/10 split by target_accord_id_primary with
            per-class presence guarantees + class-weight table

Deferred by design (documented in the report):
  - CAS -> SMILES -> Morgan/Mordred/OpenPOM chemistry embeddings (F.3)
  - MiniLM sentence embeddings for key_nuances/short_description (F.3)
  - Fragrantica/basenotes text augmentation (plan section I)

Produces:
  - preprocessing/outputs/*.csv|*.json   (committed artifacts)
  - preprocessing/intermediate/*.pkl     (gitignored caches)
  - preprocessing/PREPROCESSING_REPORT.md

Run:
  python preprocessing/run_preprocessing.py
"""

from __future__ import annotations

import json
import warnings
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PREP_ROOT = PROJECT_ROOT / "preprocessing"
OUT_DIR = PREP_ROOT / "outputs"
INTERMEDIATE_DIR = PREP_ROOT / "intermediate"
REPORT_PATH = PREP_ROOT / "PREPROCESSING_REPORT.md"

import argparse

_ap = argparse.ArgumentParser()
_ap.add_argument(
    "--master", type=Path,
    default=PROJECT_ROOT / "perfume_system_master_training_dynamic_v4_10000.xlsx",
    help="master workbook; pass the v5 augmented file to include synthetic rows")
MASTER_FILE = _ap.parse_args().master
NOTES_FILE = PROJECT_ROOT / "notes_dataset_normalized.xlsx"

SEED = 42
VAL_FRAC = 0.10
TEST_FRAC = 0.10

# Placeholder accord-blend weights until Stage 2 provides learned weights
# (plan F.2 blend rule (a): weighted average of per-accord pcts, renormalised).
W_PRIMARY = 0.65
W_SECONDARY = 0.35

# Name-matching vocab. FORM/ORIGIN tokens describe extraction method or
# provenance, not odor identity, so they are stripped before stem comparison.
# GENERIC tokens are too unspecific to justify a match on their own.
FORM_TOKENS = {
    "oil", "eo", "absolute", "co2", "extract", "essence", "resinoid",
    "rectified", "concrete", "tincture", "butter", "otto", "alcohol", "coeur",
}
ORIGIN_TOKENS = {
    "haiti", "siam", "bourbon", "madagascar", "indonesia", "virginia",
    "mysore", "calabria", "sicily", "bulgaria", "turkey", "egypt", "morocco",
    "france", "india", "china",
}
GENERIC_TOKENS = {
    "wood", "woods", "flower", "blossom", "leaf", "leaves", "berry", "fruit",
    "note", "accord", "white",
}
FUZZY_HIGH = 0.90
FUZZY_MED = 0.80

RECIPE_PAYLOAD_COLS = [
    "recipe_version", "accord_id", "note_id", "layer", "note_role",
    "default_pct_in_accord", "min_pct_in_accord", "max_pct_in_accord",
]
NOTE_NUMERIC_COLS = [
    "molecular_weight", "boiling_point_c", "logP", "odor_threshold_mg_L",
    "substantivity_index", "tenacity_min_hrs", "tenacity_max_hrs",
    "flash_point_c",
]
NOTE_CATEGORICAL_COLS = [
    "chemical_family", "odor_family", "volatility_class", "solubility",
    "natural_source",
]

OUT_DIR.mkdir(parents=True, exist_ok=True)
INTERMEDIATE_DIR.mkdir(parents=True, exist_ok=True)


# ----------------------------------------------------------------------------
# Reporting helpers (same pattern as eda/run_eda.py)
# ----------------------------------------------------------------------------

@dataclass
class Section:
    title: str
    body: list[str] = field(default_factory=list)

    def line(self, text: str = "") -> None:
        self.body.append(text)

    def bullet(self, text: str) -> None:
        self.body.append(f"- {text}")

    def add_table_link(self, caption: str, relpath: str) -> None:
        self.body.append(f"- output: [{caption}](./{relpath})")


REPORT_SECTIONS: list[Section] = []
REVIEW_ITEMS: list[str] = []


def section(title: str) -> Section:
    s = Section(title=title)
    REPORT_SECTIONS.append(s)
    print(f"\n{'#' * 78}\n# {title}\n{'#' * 78}")
    return s


def save_table(df: pd.DataFrame, name: str) -> str:
    rel = f"outputs/{name}.csv"
    df.to_csv(PREP_ROOT / rel, index=False)
    print(f"  out: {rel}  ({len(df)} rows)")
    return rel


def save_json(obj, name: str) -> str:
    rel = f"outputs/{name}.json"
    with open(PREP_ROOT / rel, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
    print(f"  out: {rel}")
    return rel


def save_intermediate(df: pd.DataFrame, name: str) -> None:
    rel = f"intermediate/{name}.pkl"
    df.to_pickle(PREP_ROOT / rel)
    print(f"  cache: {rel}  ({len(df)} rows)")


# ----------------------------------------------------------------------------
# P0. Load
# ----------------------------------------------------------------------------

print("Loading workbooks ...")
master = pd.ExcelFile(MASTER_FILE)
training = master.parse("training_examples")
accords = master.parse("accords")
accord_note = master.parse("accord_note")
notes_catalog = master.parse("notes")
perfume_note = master.parse("perfume_note")
perfume_accord = master.parse("perfume_accord")
recipe_default = master.parse("accord_recipe_default")
descriptor_vocab = master.parse("descriptor_vocab")
occasion_vocab = master.parse("occasion_vocab")
descriptor_synonyms = master.parse("descriptor_synonyms")
occasion_synonyms = master.parse("occasion_synonyms")
accord_dictionary = master.parse("accord_dictionary_master")
note_dictionary = master.parse("note_dictionary_master")
unmapped_tokens = pd.ExcelFile(NOTES_FILE).parse("unmapped_accord_tokens")

RULE_NOTE_IDS = set(accord_note["note_id"])
PERFUME_NOTE_IDS = set(perfume_note["note_id"])
print(f"  rule-recipe note space: {len(RULE_NOTE_IDS)} ids | "
      f"real-perfume note space: {len(PERFUME_NOTE_IDS)} ids | "
      f"exact-id overlap: {len(RULE_NOTE_IDS & PERFUME_NOTE_IDS)}")


# ----------------------------------------------------------------------------
# P1. (F.1) Dictionary bijectivity checks
# ----------------------------------------------------------------------------

sec = section("P1 — Dictionary bijectivity checks (F.1)")

checks = []
for dict_name, df, key_col, id_col in [
    ("note_dictionary_master", note_dictionary, "raw_note_name", "note_id"),
    ("accord_dictionary_master", accord_dictionary, "raw_accord_name", "accord_id"),
    ("descriptor_synonyms", descriptor_synonyms, "phrase", "canonical_descriptor"),
    ("occasion_synonyms", occasion_synonyms, "phrase", "canonical_occasion"),
]:
    dup_keys = df[df.duplicated(subset=[key_col], keep=False)]
    ambiguous = dup_keys.groupby(key_col)[id_col].nunique()
    n_ambiguous = int((ambiguous > 1).sum())
    checks.append({
        "dictionary": dict_name, "rows": len(df),
        "unique_keys": df[key_col].nunique(),
        "duplicate_key_rows": len(dup_keys),
        "keys_mapping_to_multiple_ids": n_ambiguous,
    })
    if n_ambiguous:
        REVIEW_ITEMS.append(
            f"{dict_name}: {n_ambiguous} raw keys map to more than one id — resolve manually.")

check_df = pd.DataFrame(checks)
rel = save_table(check_df, "01_dictionary_checks")
sec.bullet("A dictionary is safe when every raw key maps to exactly one id "
           "(duplicate rows repeating the same mapping are harmless).")
for row in checks:
    verdict = "OK" if row["keys_mapping_to_multiple_ids"] == 0 else "AMBIGUOUS"
    sec.bullet(f"`{row['dictionary']}`: {row['rows']} rows, "
               f"{row['keys_mapping_to_multiple_ids']} ambiguous keys — **{verdict}**")
sec.add_table_link("dictionary checks", rel)

# Catalog-level sanity: one normalized name per note_id and vice versa.
name_dupes = notes_catalog[notes_catalog.duplicated(subset=["normalized_note_name"], keep=False)]
sec.bullet(f"`notes` catalog: {len(notes_catalog)} rows, "
           f"{name_dupes['normalized_note_name'].nunique()} normalized names shared by multiple note_ids.")


# ----------------------------------------------------------------------------
# P2. (F.1) Note-vocabulary bridge + unified note ids
# ----------------------------------------------------------------------------

sec = section("P2 — Note-vocabulary bridge (F.1, checkpoint L.4)")

catalog = notes_catalog.set_index("note_id")
NAME = catalog["normalized_note_name"].astype(str).to_dict()
CAS = catalog["cas_number_clean"].dropna().astype(str).str.strip().to_dict()


def stem_tokens(name: str) -> frozenset[str]:
    toks = set(name.split("_"))
    stem = toks - FORM_TOKENS - ORIGIN_TOKENS
    return frozenset(stem if stem else toks)


def best_match(src_id: str, target_ids: list[str], cas_to_targets: dict[str, list[str]]):
    """Best bridge candidate for src_id among target_ids.

    Returns (target_id, method, score, confidence) or None. Tier order:
    cas > stem_equal > stem_subset_multi > stem_subset_single > fuzzy.
    """
    src_name = NAME[src_id]
    src_stem = stem_tokens(src_name)

    src_cas = CAS.get(src_id)
    if src_cas and src_cas in cas_to_targets:
        return cas_to_targets[src_cas][0], "cas", 1.0, "high"

    best = None  # (tier_rank, score, target_id, method, confidence)
    for tid in target_ids:
        t_stem = stem_tokens(NAME[tid])
        shared = src_stem & t_stem
        if src_stem == t_stem:
            cand = (0, 1.0, tid, "stem_equal", "high")
        elif (src_stem <= t_stem or t_stem <= src_stem) and len(shared) >= 2:
            cand = (1, len(shared) / len(src_stem | t_stem), tid, "stem_subset_multi", "high")
        elif (src_stem <= t_stem or t_stem <= src_stem) and len(shared) == 1 \
                and next(iter(shared)) not in GENERIC_TOKENS:
            cand = (2, len(shared) / len(src_stem | t_stem), tid, "stem_subset_single", "medium")
        else:
            m = SequenceMatcher(None, src_name, NAME[tid])
            if m.real_quick_ratio() >= FUZZY_MED and m.quick_ratio() >= FUZZY_MED:
                ratio = m.ratio()
                if ratio >= FUZZY_HIGH:
                    cand = (3, ratio, tid, "fuzzy", "high")
                elif ratio >= FUZZY_MED:
                    cand = (4, ratio, tid, "fuzzy", "medium")
                else:
                    continue
            else:
                continue
        if best is None or (cand[0], -cand[1]) < (best[0], -best[1]):
            best = cand
    if best is None:
        return None
    _, score, tid, method, confidence = best
    return tid, method, round(score, 4), confidence


def build_bridge(src_ids: set[str], dst_ids: set[str]) -> pd.DataFrame:
    shared_ids = sorted(src_ids & dst_ids)
    src_only = sorted(src_ids - dst_ids)
    dst_only = sorted(dst_ids - src_ids)
    cas_to_dst: dict[str, list[str]] = {}
    for did in dst_only:
        c = CAS.get(did)
        if c:
            cas_to_dst.setdefault(c, []).append(did)
    rows = [
        {"src_note_id": i, "src_name": NAME[i], "dst_note_id": i, "dst_name": NAME[i],
         "method": "exact_id", "score": 1.0, "confidence": "high"}
        for i in shared_ids
    ]
    for sid in src_only:
        hit = best_match(sid, dst_only, cas_to_dst)
        if hit:
            tid, method, score, confidence = hit
            rows.append({"src_note_id": sid, "src_name": NAME[sid], "dst_note_id": tid,
                         "dst_name": NAME[tid], "method": method, "score": score,
                         "confidence": confidence})
        else:
            rows.append({"src_note_id": sid, "src_name": NAME[sid], "dst_note_id": None,
                         "dst_name": None, "method": "unmatched", "score": 0.0,
                         "confidence": "none"})
    out = pd.DataFrame(rows)
    out["needs_review"] = out["confidence"].eq("medium")
    return out


bridge_r2p = build_bridge(RULE_NOTE_IDS, PERFUME_NOTE_IDS)
bridge_p2r = build_bridge(PERFUME_NOTE_IDS, RULE_NOTE_IDS)
rel_r2p = save_table(bridge_r2p, "02_note_bridge_rule_to_perfume")
rel_p2r = save_table(bridge_p2r, "02_note_bridge_perfume_to_rule")

for label, br, total in [("rule→perfume", bridge_r2p, len(RULE_NOTE_IDS)),
                         ("perfume→rule", bridge_p2r, len(PERFUME_NOTE_IDS))]:
    counts = br["method"].value_counts().to_dict()
    matched = int(br["dst_note_id"].notna().sum())
    sec.bullet(f"**{label}**: {matched}/{total} notes bridged "
               f"({br['confidence'].eq('high').sum()} high, "
               f"{br['confidence'].eq('medium').sum()} medium/needs-review). "
               f"Methods: {counts}")
n_review = int(bridge_r2p["needs_review"].sum() + bridge_p2r["needs_review"].sum())
REVIEW_ITEMS.append(
    f"Note bridge: {n_review} medium-confidence pairs across both directions need "
    f"human review (filter `needs_review == True` in the 02_note_bridge_* tables). "
    f"Unmatched notes stay space-local — decide per plan F.1 whether to map manually or "
    f"tag outputs as rule-derived vs real-derived.")

# Unified note ids: union-find over accepted (high-confidence) matches only.
parent: dict[str, str] = {nid: nid for nid in catalog.index}


def find(x: str) -> str:
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def union(a: str, b: str) -> None:
    ra, rb = find(a), find(b)
    if ra != rb:
        # deterministic: lower id wins as root
        lo, hi = sorted([ra, rb])
        parent[hi] = lo


for br in (bridge_r2p, bridge_p2r):
    accepted = br[br["confidence"].eq("high") & br["dst_note_id"].notna()]
    for _, r in accepted.iterrows():
        union(r["src_note_id"], r["dst_note_id"])

unified = pd.DataFrame({
    "note_id": sorted(catalog.index),
})
unified["unified_note_id"] = unified["note_id"].map(find)
unified["normalized_note_name"] = unified["note_id"].map(NAME)
unified["in_rule_space"] = unified["note_id"].isin(RULE_NOTE_IDS)
unified["in_perfume_space"] = unified["note_id"].isin(PERFUME_NOTE_IDS)
group_sizes = unified.groupby("unified_note_id")["note_id"].transform("count")
unified["merged_group_size"] = group_sizes
rel_uni = save_table(unified, "02_unified_note_map")
n_groups = unified["unified_note_id"].nunique()
n_merged = int((unified["merged_group_size"] > 1).sum())
sec.bullet(f"**Unified note map**: {len(unified)} catalog notes → {n_groups} unified ids; "
           f"{n_merged} notes participate in merged groups (high-confidence matches only; "
           f"medium pairs merge after human review).")
sec.bullet(f"Blend weights, stems: FORM tokens stripped {sorted(FORM_TOKENS)}; "
           f"ORIGIN tokens stripped {sorted(ORIGIN_TOKENS)}; single-token matches on "
           f"{sorted(GENERIC_TOKENS)} are rejected as too generic.")
sec.add_table_link("bridge rule→perfume", rel_r2p)
sec.add_table_link("bridge perfume→rule", rel_p2r)
sec.add_table_link("unified note map", rel_uni)

# Same-space CAS duplicates: chemically identical ids inside one space.
cas_series = catalog["cas_number_clean"].dropna().astype(str).str.strip()
cas_groups = cas_series.groupby(cas_series).count()
dup_cas_ids = cas_series[cas_series.isin(cas_groups[cas_groups > 1].index)]
dup_cas_df = (catalog.loc[dup_cas_ids.index, ["normalized_note_name", "cas_number_clean"]]
              .reset_index().sort_values(["cas_number_clean", "note_id"]))
rel = save_table(dup_cas_df, "02_same_cas_note_groups")
sec.bullet(f"{dup_cas_df['cas_number_clean'].nunique()} CAS numbers are shared by multiple "
           f"catalog notes ({len(dup_cas_df)} rows). Cross-space shares drive the `cas` "
           f"bridge tier; same-space shares are kept separate (often deliberate variants, "
           f"e.g. oil vs absolute) and listed for review.")
sec.add_table_link("same-CAS note groups", rel)


# ----------------------------------------------------------------------------
# P3. (F.1) unmapped_accord_tokens resolution proposals
# ----------------------------------------------------------------------------

sec = section("P3 — Unmapped accord-token resolution (F.1)")

accord_names = accords.set_index("accord_id")["normalized_accord_name"].astype(str).to_dict()
rows = []
for _, r in unmapped_tokens.iterrows():
    token = str(r["normalized_accord_name"])
    tok_stem = set(token.split("_"))
    best = None
    for aid, aname in accord_names.items():
        a_stem = set(aname.split("_"))
        shared = tok_stem & a_stem
        ratio = SequenceMatcher(None, token, aname).ratio()
        score = max(ratio, len(shared) / max(len(tok_stem | a_stem), 1))
        if best is None or score > best[0]:
            best = (score, aid, aname)
    score, aid, aname = best
    if score >= 0.8:
        decision = "map_to_accord"
    elif score >= 0.5:
        decision = "review"
    else:
        decision = "descriptor_only"
    rows.append({"raw_accord_token": r["raw_accord_token"], "normalized_token": token,
                 "best_accord_id": aid, "best_accord_name": aname,
                 "score": round(score, 3), "proposed_decision": decision})

umt_df = pd.DataFrame(rows)
rel = save_table(umt_df, "03_unmapped_accord_token_resolution")
n_map = (umt_df["proposed_decision"] == "map_to_accord").sum()
n_desc = (umt_df["proposed_decision"] == "descriptor_only").sum()
n_rev = (umt_df["proposed_decision"] == "review").sum()
sec.bullet(f"{len(umt_df)} unmapped tokens: {n_map} proposed accord mappings, "
           f"{n_desc} proposed descriptor-only, {n_rev} need review.")
if (umt_df["score"] == 1.0).all():
    sec.bullet("All 10 tokens matched an accord name **exactly** — the master workbook "
               "already added them to the `accords` sheet (ACC-0300…ACC-0309). The "
               "`unmapped_accord_tokens` sheet in notes_dataset_normalized.xlsx is stale "
               "relative to the master; treat the master catalog as authoritative.")
sec.add_table_link("token resolution proposals", rel)
REVIEW_ITEMS.append(
    f"Unmapped accord tokens: confirm the {len(umt_df)} proposals in "
    f"03_unmapped_accord_token_resolution.csv (auto-threshold 0.8).")


# ----------------------------------------------------------------------------
# P4. (F.2) Recipe cleanup
# ----------------------------------------------------------------------------

sec = section("P4 — Recipe cleanup (F.2)")

before = len(recipe_default)
recipe_clean = recipe_default.drop_duplicates(subset=RECIPE_PAYLOAD_COLS, keep="first").copy()
n_dropped = before - len(recipe_clean)

sums = recipe_clean.groupby("accord_id")["default_pct_in_accord"].sum()
factors = 100.0 / sums
recipe_clean["renorm_factor"] = recipe_clean["accord_id"].map(factors)
for col in ["default_pct_in_accord", "min_pct_in_accord", "max_pct_in_accord"]:
    recipe_clean[col] = recipe_clean[col] * recipe_clean["renorm_factor"]
recipe_clean = recipe_clean.drop(columns=["renorm_factor"])

renormed = factors[(factors - 1).abs() > 1e-6]
sums_after = recipe_clean.groupby("accord_id")["default_pct_in_accord"].sum()
viol_sum = int((sums_after - 100).abs().gt(1e-6).sum())
viol_rng = int(((recipe_clean["min_pct_in_accord"] > recipe_clean["default_pct_in_accord"]) |
                (recipe_clean["default_pct_in_accord"] > recipe_clean["max_pct_in_accord"])).sum())

sec.bullet(f"Dropped {n_dropped} exact-duplicate rows ({before} → {len(recipe_clean)}); "
           f"duplicates were verbatim copied rows (ACC-0111 tripled, four accords doubled, "
           f"16 accords partially duplicated).")
sec.bullet(f"Renormalised {len(renormed)} accords back to a 100% sum "
           f"(min/max scaled by the same factor, preserving window geometry).")
sec.bullet(f"Post-clean invariants: sum-to-100 violations = {viol_sum}; "
           f"min ≤ default ≤ max violations = {viol_rng}.")

rel_role = save_table(recipe_clean, "04_recipe_clean_role_level")

# Note-level aggregation: a note may hold several roles/layers inside one
# accord; Stage-4 targets need one pct per (accord, note).
note_level = (recipe_clean
              .groupby(["accord_id", "accord_name", "accord_category", "note_id", "note_name"],
                       as_index=False)
              .agg(default_pct=("default_pct_in_accord", "sum"),
                   min_pct=("min_pct_in_accord", "sum"),
                   max_pct=("max_pct_in_accord", "sum"),
                   layers=("layer", lambda s: "|".join(sorted(set(s)))),
                   roles=("note_role", lambda s: "|".join(sorted(set(s))))))
rel_note = save_table(note_level, "04_recipe_clean_note_level")
sec.bullet(f"Note-level table: {len(note_level)} (accord, note) rows across "
           f"{note_level['accord_id'].nunique()} accords with recipes.")

# Membership table dedup for consistency.
an_before = len(accord_note)
accord_note_clean = accord_note.drop_duplicates(keep="first").copy()
rel_an = save_table(accord_note_clean, "04_accord_note_clean")
sec.bullet(f"`accord_note` membership: dropped {an_before - len(accord_note_clean)} "
           f"exact-duplicate rows ({an_before} → {len(accord_note_clean)}).")

# Recipe notes should be a subset of membership notes per accord.
mem = accord_note_clean.groupby("accord_id")["note_id"].apply(set)
rec = note_level.groupby("accord_id")["note_id"].apply(set)
stray = {a: sorted(rec[a] - mem.get(a, set())) for a in rec.index if rec[a] - mem.get(a, set())}
sec.bullet(f"Recipe/membership consistency: {len(stray)} accords have recipe notes missing "
           f"from `accord_note` membership." + (" Details logged for review." if stray else ""))
if stray:
    stray_df = pd.DataFrame([(a, n) for a, ns in stray.items() for n in ns],
                            columns=["accord_id", "note_id"])
    rel_stray = save_table(stray_df, "04_recipe_notes_missing_from_membership")
    sec.add_table_link("stray recipe notes", rel_stray)
    REVIEW_ITEMS.append(f"{len(stray)} accords have recipe notes absent from accord_note "
                        f"membership — see 04_recipe_notes_missing_from_membership.csv.")
sec.add_table_link("clean recipes (role level)", rel_role)
sec.add_table_link("clean recipes (note level)", rel_note)
sec.add_table_link("clean accord_note membership", rel_an)
save_intermediate(recipe_clean, "recipe_clean_role_level")
save_intermediate(note_level, "recipe_clean_note_level")


# ----------------------------------------------------------------------------
# P5. (F.2) Blended cross-accord recipes
# ----------------------------------------------------------------------------

sec = section("P5 — Blended cross-accord recipes (F.2)")

pairs = (training.dropna(subset=["target_accord_id_secondary"])
         [["target_accord_id_primary", "target_accord_id_secondary"]]
         .drop_duplicates())
recipes_by_accord = {a: g.set_index("note_id")["default_pct"]
                     for a, g in note_level.groupby("accord_id")}

primary_targets = set(training["target_accord_id_primary"])
secondary_targets = set(training["target_accord_id_secondary"].dropna())
have_recipe = set(recipes_by_accord)
missing_primary = sorted(primary_targets - have_recipe)
missing_secondary = sorted(secondary_targets - have_recipe)

blend_rows = []
covered_pairs = 0
for _, r in pairs.iterrows():
    p, s = r["target_accord_id_primary"], r["target_accord_id_secondary"]
    if p not in recipes_by_accord or s not in recipes_by_accord:
        continue
    covered_pairs += 1
    blended = (recipes_by_accord[p].mul(W_PRIMARY)
               .add(recipes_by_accord[s].mul(W_SECONDARY), fill_value=0.0))
    for note_id, pct in blended.items():
        blend_rows.append({"accord_id_primary": p, "accord_id_secondary": s,
                           "note_id": note_id, "blended_pct": round(float(pct), 6)})

blend_df = pd.DataFrame(blend_rows)
rel = save_table(blend_df, "05_blended_pair_recipes")
save_intermediate(blend_df, "blended_pair_recipes")

pair_sums = blend_df.groupby(["accord_id_primary", "accord_id_secondary"])["blended_pct"].sum()
sec.bullet(f"Blend rule (a) from F.2 with placeholder weights "
           f"**{W_PRIMARY}/{W_SECONDARY}** (primary/secondary) — replace with Stage-2 "
           f"weights at inference; the lookup exists so training targets are precomputable.")
sec.bullet(f"{covered_pairs}/{len(pairs)} unique (primary, secondary) pairs blended "
           f"({len(blend_df)} note rows); max |sum − 100| = "
           f"{float((pair_sums - 100).abs().max()):.2e}.")
sec.bullet(f"Recipe coverage of training targets: {len(missing_primary)} primary and "
           f"{len(missing_secondary)} secondary target accords have **no recipe** in "
           f"`accord_recipe_default`.")
if missing_primary or missing_secondary:
    cov_df = pd.DataFrame(
        [{"accord_id": a, "role": "primary",
          "n_examples": int((training["target_accord_id_primary"] == a).sum())}
         for a in missing_primary] +
        [{"accord_id": a, "role": "secondary",
          "n_examples": int((training["target_accord_id_secondary"] == a).sum())}
         for a in missing_secondary])
    rel_cov = save_table(cov_df, "05_target_accords_without_recipes")
    sec.add_table_link("target accords without recipes", rel_cov)
    n_ex_uncovered = int(training["target_accord_id_primary"].isin(missing_primary).sum())
    REVIEW_ITEMS.append(
        f"{len(missing_primary)} primary target accords ({n_ex_uncovered} training examples) "
        f"have no rule recipe — Stages 3–4 cannot produce a formula for them without "
        f"extending accord_recipe_default. See 05_target_accords_without_recipes.csv.")
sec.add_table_link("blended pair recipes", rel)


# ----------------------------------------------------------------------------
# P6. (F.3) Note feature table
# ----------------------------------------------------------------------------

sec = section("P6 — Note feature table (F.3)")

feat = notes_catalog.copy()
cat_vocab = {}
for col in NOTE_CATEGORICAL_COLS:
    feat[col] = feat[col].fillna("unknown").astype(str).str.strip().str.lower()
    cat_vocab[col] = sorted(feat[col].unique())

imputed_any = 0
family_means = {}
for col in NOTE_NUMERIC_COLS:
    feat[col] = pd.to_numeric(feat[col], errors="coerce")
    flag = f"{col}_imputed"
    feat[flag] = feat[col].isna().astype(int)
    imputed_any += int(feat[flag].sum())
    grp = feat.groupby("chemical_family")[col].transform("mean")
    feat[col] = feat[col].fillna(grp).fillna(feat[col].mean())
    family_means[col] = "chemical_family mean, global-mean fallback"

feat["has_cas"] = feat["cas_number_clean"].notna().astype(int)
feat["in_rule_space"] = feat["note_id"].isin(RULE_NOTE_IDS).astype(int)
feat["in_perfume_space"] = feat["note_id"].isin(PERFUME_NOTE_IDS).astype(int)
feat = feat.merge(unified[["note_id", "unified_note_id"]], on="note_id", how="left")

keep_cols = (["note_id", "unified_note_id", "normalized_note_name", "note_name",
              "chemical_name", "cas_number_clean", "has_cas",
              "in_rule_space", "in_perfume_space"]
             + NOTE_CATEGORICAL_COLS + NOTE_NUMERIC_COLS
             + [f"{c}_imputed" for c in NOTE_NUMERIC_COLS])
note_features = feat[keep_cols]
rel = save_table(note_features, "06_note_features")
save_intermediate(note_features, "note_features")
rel_vocab = save_json(cat_vocab, "06_note_categorical_vocab")

n_missing_all = int((note_features[[f"{c}_imputed" for c in NOTE_NUMERIC_COLS]]
                     .sum(axis=1) == len(NOTE_NUMERIC_COLS)).sum())
sec.bullet(f"{len(note_features)} notes × {len(NOTE_NUMERIC_COLS)} numeric features; "
           f"{imputed_any} cells imputed via chemical_family means (per plan F.3) with "
           f"is-imputed indicator columns; {n_missing_all} notes had every numeric "
           f"feature missing (fully family-imputed).")
sec.bullet(f"Categoricals lower-cased with `unknown` fill: "
           + ", ".join(f"`{c}` ({len(v)} levels)" for c, v in cat_vocab.items()) + ".")
sec.bullet("**Deferred** (documented, per plan): CAS→SMILES→Morgan/Mordred/OpenPOM "
           "chemistry embeddings and MiniLM text embeddings for key_nuances / "
           "short_description. Both bolt onto this table by `note_id` without touching "
           "anything downstream.")
sec.add_table_link("note features", rel)
sec.add_table_link("categorical vocab", rel_vocab)


# ----------------------------------------------------------------------------
# P7. (F.4) Training-input feature table
# ----------------------------------------------------------------------------

sec = section("P7 — Training-input features (F.4)")

tr = training.copy()

# Descriptor multi-hot over the 98-token controlled vocabulary.
DESCRIPTORS = descriptor_vocab["descriptor"].astype(str).tolist()
syn_map = dict(zip(descriptor_synonyms["phrase"].astype(str),
                   descriptor_synonyms["canonical_descriptor"].astype(str)))
desc_tokens = (tr["descriptor_tags_csv"].fillna("").str.split(",")
               .apply(lambda ts: [syn_map.get(t.strip(), t.strip()) for t in ts if t.strip()]))
oov = sorted({t for ts in desc_tokens for t in ts} - set(DESCRIPTORS))
desc_mh = pd.DataFrame(
    {f"desc_{d}": desc_tokens.apply(lambda ts, d=d: int(d in ts)) for d in DESCRIPTORS})

# Avoid multi-hot over the canonical avoid tokens observed in the data.
avoid_tokens = (tr["avoid_notes_csv"].fillna("").str.split(",")
                .apply(lambda ts: [t.strip() for t in ts if t.strip()]))
AVOIDS = sorted({t for ts in avoid_tokens for t in ts})
avoid_mh = pd.DataFrame(
    {f"avoid_{a}": avoid_tokens.apply(lambda ts, a=a: int(a in ts)) for a in AVOIDS})

# Categorical vocab maps for the Stage-1 structured encoder.
AGE_BUCKETS = sorted(tr["age_bucket"].astype(str).unique())
input_vocab = {
    "age_bucket_order": AGE_BUCKETS,
    "gender": sorted(tr["gender"].astype(str).unique()),
    "region": sorted(tr["region"].astype(str).unique()),
    "background_tag": sorted(tr["background_tag"].astype(str).unique()),
    "occasion_tag": sorted(occasion_vocab["occasion"].astype(str).unique()),
    "descriptors": DESCRIPTORS,
    "avoid_tokens": AVOIDS,
}
rel_vocab = save_json(input_vocab, "07_input_vocab")

base_cols = ["request_id", "user_text", "age", "age_bucket", "gender", "region",
             "background_tag", "occasion_tag", "target_accord_id_primary",
             "target_accord_id_secondary", "target_perfume_id_reference",
             "user_rating_1_5", "accepted_flag"]
if "is_augmented" in tr.columns:
    base_cols.append("is_augmented")
processed = pd.concat([tr[base_cols].reset_index(drop=True),
                       desc_mh.reset_index(drop=True),
                       avoid_mh.reset_index(drop=True)], axis=1)
processed["n_descriptors"] = desc_mh.sum(axis=1)
processed["n_avoids"] = avoid_mh.sum(axis=1)
rel_proc = save_table(processed, "07_training_processed")
save_intermediate(processed, "training_processed")

feature_spec = {
    "text": {"column": "user_text", "tokenizer": "encoder-native", "max_len": 64,
             "note": "99th percentile length ≈ 140 chars (EDA §4)"},
    "ordinal": {"age_bucket": AGE_BUCKETS},
    "categorical_embeddings": {
        "gender": len(input_vocab["gender"]), "region": len(input_vocab["region"]),
        "background_tag": len(input_vocab["background_tag"]),
        "occasion_tag": len(input_vocab["occasion_tag"]),
    },
    "multi_hot": {"descriptors": len(DESCRIPTORS), "avoid_tokens": len(AVOIDS)},
    "targets": {"primary": "target_accord_id_primary (200 active classes)",
                "secondary": "target_accord_id_secondary (34% present)",
                "reference": "target_perfume_id_reference — SOFT retrieval signal only "
                             "(checkpoint L.5; 1.9% accord-match rate)",
                "preference": "user_rating_1_5 (17%), accepted_flag (15%)"},
}
rel_spec = save_json(feature_spec, "07_feature_spec")

sec.bullet(f"Descriptor multi-hot: {len(DESCRIPTORS)} vocab columns; synonym map applied; "
           f"out-of-vocabulary tokens found: {len(oov)}"
           + (f" → {oov}" if oov else "") + ".")
sec.bullet(f"Avoid multi-hot: {len(AVOIDS)} canonical tokens {AVOIDS}.")
sec.bullet(f"Processed table: {processed.shape[0]} rows × {processed.shape[1]} columns "
           f"(raw text kept verbatim for the encoder; no leakage removal here — the "
           f"templated-text risk is handled by the held-out real-prompt set, plan F.5).")
sec.add_table_link("processed training table", rel_proc)
sec.add_table_link("input vocab", rel_vocab)
sec.add_table_link("Stage-1 feature spec", rel_spec)


# ----------------------------------------------------------------------------
# P8. (F.5) Stratified splits + class weights
# ----------------------------------------------------------------------------

sec = section("P8 — Stratified splits and class weights (F.5)")

rng = np.random.default_rng(SEED)
split = pd.Series("train", index=tr.index, name="split")
# Synthetic rows (is_augmented=1) are excluded from stratified assignment and
# therefore stay in train — they must never reach val/test (plan F.5).
aug_mask = (tr["is_augmented"].fillna(0).astype(int) == 1
            if "is_augmented" in tr.columns
            else pd.Series(False, index=tr.index))
for _, grp in tr[~aug_mask].groupby("target_accord_id_primary"):
    idx = grp.index.to_numpy()
    rng.shuffle(idx)
    n = len(idx)
    n_val = max(1, int(np.floor(VAL_FRAC * n)))
    n_test = max(1, int(np.floor(TEST_FRAC * n)))
    split.loc[idx[:n_val]] = "val"
    split.loc[idx[n_val:n_val + n_test]] = "test"

splits_df = pd.DataFrame({"request_id": tr["request_id"], "split": split})
rel_splits = save_table(splits_df, "08_splits")

per_split = split.value_counts().to_dict()
cls_presence = tr.groupby("target_accord_id_primary").apply(
    lambda g: split.loc[g.index].nunique(), include_groups=False)
sec.bullet(f"Seed {SEED}; per-class allocation floor(10%) with a minimum of 1 example in "
           f"val and test → sizes {per_split}; "
           f"{int((cls_presence == 3).sum())}/{tr['target_accord_id_primary'].nunique()} "
           f"classes present in all three splits.")
sec.bullet("Oversampling of rare classes is done at train time via the weight table below "
           "— never materialised into val/test (plan F.5).")
if bool(aug_mask.any()):
    sec.bullet(f"**Augmented data**: {int(aug_mask.sum())} synthetic rows "
               f"(is_augmented=1, from {MASTER_FILE.name}) forced into the train "
               f"split; val/test contain only original v4 rows, so metrics remain "
               f"comparable with pre-augmentation runs.")

counts = tr.loc[split == "train", "target_accord_id_primary"].value_counts()
beta = 0.999
eff_num = (1 - np.power(beta, counts.values)) / (1 - beta)
cb = (1.0 / eff_num)
cb = cb / cb.sum() * len(counts)
inv = (1.0 / counts.values)
inv = inv / inv.sum() * len(counts)
class_weights = pd.DataFrame({
    "accord_id": counts.index, "train_count": counts.values,
    "inverse_freq_weight": np.round(inv, 6),
    "class_balanced_weight_beta0.999": np.round(cb, 6),
}).sort_values("train_count", ascending=False)
rel_w = save_table(class_weights, "08_class_weights")
sec.bullet(f"Class weights for the Stage-2 loss: inverse-frequency and class-balanced "
           f"effective-number weights (Cui et al. 2019, β=0.999) over "
           f"{len(class_weights)} training classes "
           f"(head ACC counts {counts.iloc[0]}–{counts.iloc[-1]}).")
sec.bullet("**Open item (plan F.5)**: the N=200 manually-written real prompts for the "
           "anti-template held-out set still need to be authored (checkpoint L.7).")
sec.add_table_link("splits", rel_splits)
sec.add_table_link("class weights", rel_w)
REVIEW_ITEMS.append("Author the N=200 real (non-templated) prompts for the adversarial "
                    "held-out set (plan F.5 / checkpoint L.7).")


# ----------------------------------------------------------------------------
# Report
# ----------------------------------------------------------------------------

print(f"\n{'#' * 78}\n# Writing report\n{'#' * 78}")

lines = [
    "# PREPROCESSING REPORT — Perfumery ML project",
    "",
    f"Generated by `preprocessing/run_preprocessing.py` (seed {SEED}). "
    f"Implements plan §F; assumes Tier-0 scope (checkpoint L.3 default), so no "
    f"constraint tables are built (F.6 skipped).",
    "",
    "## Executive summary",
    "",
]
b_r2p = bridge_r2p
lines += [
    f"- **Note bridge (L.4)**: {int(b_r2p['dst_note_id'].notna().sum())}/{len(RULE_NOTE_IDS)} "
    f"rule-space notes now map into the perfume space "
    f"({int(b_r2p['confidence'].eq('high').sum())} auto-accepted, "
    f"{int(b_r2p['needs_review'].sum())} pending review); unified note ids issued for all "
    f"{len(unified)} catalog notes.",
    f"- **Recipes**: {n_dropped} duplicate rows removed, {len(renormed)} accords "
    f"renormalised to 100%, zero remaining sum or min/max violations.",
    f"- **Blends**: {covered_pairs} (primary, secondary) pair recipes materialised with "
    f"placeholder weights {W_PRIMARY}/{W_SECONDARY}.",
    f"- **Coverage gap**: {len(missing_primary)} primary target accords lack any rule "
    f"recipe — flagged for a decision before Stage-3/4 training.",
    f"- **Features**: note table ({len(note_features)} × "
    f"{len(NOTE_NUMERIC_COLS) + len(NOTE_CATEGORICAL_COLS)} features, family-mean "
    f"imputation), training table ({processed.shape[0]} × {processed.shape[1]}), "
    f"feature spec for the Stage-1 encoder.",
    f"- **Splits**: stratified 80/10/10 with all-classes-present guarantee; class-weight "
    f"table for the Stage-2 loss.",
    "",
    "## Items needing human review / sign-off",
    "",
]
lines += [f"{i}. {item}" for i, item in enumerate(REVIEW_ITEMS, 1)]
lines.append("")

for s in REPORT_SECTIONS:
    lines.append(f"## {s.title}")
    lines.append("")
    lines.extend(s.body)
    lines.append("")

REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
print(f"Report written: {REPORT_PATH}")
print("\nDone.")
