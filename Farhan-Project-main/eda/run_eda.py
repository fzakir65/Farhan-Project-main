"""
Comprehensive End-to-End EDA for the Perfumery ML project.
Produces:
  - eda/figures/*.png        (charts)
  - eda/tables/*.csv         (tabular outputs for the report and downstream preprocessing)
  - eda/intermediate/*.parquet (cached cleaned tables)
  - eda/EDA_REPORT.md        (the human-readable consolidated report)

Run:
  python3 eda/run_eda.py

Author: ML team — Perfumery project — generated 2026-05-05.
"""

from __future__ import annotations

import json
import re
import sys
import warnings
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")
pd.options.display.float_format = "{:,.4f}".format

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------

PROJECT_ROOT = Path("/Users/omaralfrouh/Desktop/Farhan Project")
EDA_ROOT = PROJECT_ROOT / "eda"
FIG_DIR = EDA_ROOT / "figures"
TABLE_DIR = EDA_ROOT / "tables"
INTERMEDIATE_DIR = EDA_ROOT / "intermediate"
REPORT_PATH = EDA_ROOT / "EDA_REPORT.md"

ACCORD_FILE = "accord_dataset_normalized_v2.xlsx"
NOTES_FILE = "notes_dataset_normalized.xlsx"
MASTER_FILE = "perfume_system_master_training_dynamic_v4_10000.xlsx"
RECIPES_FILE = "perfume_system_master_with_recipes.xlsx"

sns.set_theme(context="paper", style="whitegrid", palette="deep", font_scale=0.95)
plt.rcParams["figure.dpi"] = 110
plt.rcParams["savefig.dpi"] = 130
plt.rcParams["figure.constrained_layout.use"] = True
plt.rcParams["axes.titlesize"] = 11
plt.rcParams["axes.labelsize"] = 9


# ----------------------------------------------------------------------------
# Reporting helpers
# ----------------------------------------------------------------------------

@dataclass
class Section:
    title: str
    body: list[str] = field(default_factory=list)
    figures: list[tuple[str, str]] = field(default_factory=list)  # (caption, relpath)
    tables: list[tuple[str, str]] = field(default_factory=list)   # (caption, relpath)

    def line(self, text: str = "") -> None:
        self.body.append(text)

    def bullet(self, text: str) -> None:
        self.body.append(f"- {text}")

    def add_figure(self, caption: str, relpath: str) -> None:
        self.figures.append((caption, relpath))
        self.body.append(f"\n![{caption}](./{relpath})\n")

    def add_table_link(self, caption: str, relpath: str) -> None:
        self.tables.append((caption, relpath))
        self.body.append(f"- table: [{caption}](./{relpath})")


REPORT_SECTIONS: list[Section] = []


def section(title: str) -> Section:
    s = Section(title=title)
    REPORT_SECTIONS.append(s)
    print(f"\n{'#' * 80}\n# {title}\n{'#' * 80}")
    return s


def save_fig(name: str) -> str:
    """Save current matplotlib figure under figures/ and return relative path."""
    rel = f"figures/{name}.png"
    full = EDA_ROOT / rel
    plt.savefig(full, bbox_inches="tight")
    plt.close()
    print(f"  fig saved: {rel}")
    return rel


def save_table(df: pd.DataFrame, name: str) -> str:
    rel = f"tables/{name}.csv"
    full = EDA_ROOT / rel
    df.to_csv(full, index=False)
    print(f"  tbl saved: {rel}  ({len(df)} rows)")
    return rel


def save_intermediate(df: pd.DataFrame, name: str) -> str:
    rel = f"intermediate/{name}.pkl"
    full = EDA_ROOT / rel
    df.to_pickle(full)
    print(f"  cache : {rel}  ({len(df)} rows)")
    return rel


# ----------------------------------------------------------------------------
# Section 0: Load all sheets from all four workbooks
# ----------------------------------------------------------------------------

def load_workbooks() -> dict[str, pd.DataFrame]:
    """Return a flat dict {workbook_short:sheet_name -> dataframe}."""
    sources = {
        "accord_v2": ACCORD_FILE,
        "notes_v1": NOTES_FILE,
        "master": MASTER_FILE,
        "recipes": RECIPES_FILE,
    }
    out: dict[str, pd.DataFrame] = {}
    for short, fn in sources.items():
        path = PROJECT_ROOT / fn
        xls = pd.ExcelFile(path)
        for sheet in xls.sheet_names:
            df = pd.read_excel(path, sheet_name=sheet)
            key = f"{short}:{sheet}"
            out[key] = df
            print(f"  loaded {key:50s}  shape={df.shape}")
    return out


# ----------------------------------------------------------------------------
# Section 1: Schema integrity, foreign-key checks, duplicate detection
# ----------------------------------------------------------------------------

def section_1_integrity(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    s = section("1. Data integrity, schema, foreign keys")

    # Catalog of sheets
    rows = []
    for key, df in data.items():
        rows.append(
            {
                "workbook_sheet": key,
                "n_rows": len(df),
                "n_cols": df.shape[1],
                "columns": ",".join(df.columns.tolist()),
                "any_null": int(df.isna().any().any()),
                "all_null_cols": ",".join([c for c in df.columns if df[c].isna().all()]),
            }
        )
    catalog = pd.DataFrame(rows)
    catalog_rel = save_table(catalog, "01_workbook_catalog")
    s.line(
        f"Loaded **{len(data)} sheets** from 4 workbooks (accord_v2, notes_v1, master, recipes)."
    )
    s.add_table_link("Per-sheet schema and shape", catalog_rel)

    # Promote canonical references for downstream sections
    canon = {
        "training_examples": data["master:training_examples"],
        "accords": data["master:accords"],
        "accord_note": data["master:accord_note"],
        "accord_recipe_default": data["master:accord_recipe_default"],
        "perfumes": data["master:perfumes"],
        "perfume_accord": data["master:perfume_accord"],
        "perfume_note": data["master:perfume_note"],
        "notes_master": data["master:notes"],
        "notes_v1": data["notes_v1:notes"],
        "accord_dictionary_master": data["master:accord_dictionary_master"],
        "note_dictionary_master": data["master:note_dictionary_master"],
        "descriptor_vocab": data["master:descriptor_vocab"],
        "descriptor_synonyms": data["master:descriptor_synonyms"],
        "occasion_vocab": data["master:occasion_vocab"],
        "occasion_synonyms": data["master:occasion_synonyms"],
        "unmapped_accord_tokens": data["notes_v1:unmapped_accord_tokens"],
        "note_accord_usage": data["notes_v1:note_accord_usage"],
        "accord_v2_accords": data["accord_v2:accords"],
        "accord_v2_accord_note": data["accord_v2:accord_note"],
        "accord_v2_accord_flat": data["accord_v2:accord_flat"],
    }

    # Cross-workbook duplication of accord_note (we observed it in accord_v2 + master + recipes)
    an_master = canon["accord_note"][["accord_id", "note_id", "note_role", "layer", "importance_weight", "presence_prob", "compatibility_score"]].copy()
    an_v2 = canon["accord_v2_accord_note"][an_master.columns]
    an_recipes = data["recipes:accord_note"][an_master.columns]
    diff_master_vs_v2 = (
        pd.concat([an_master, an_v2]).drop_duplicates(keep=False)
    )
    diff_master_vs_recipes = (
        pd.concat([an_master, an_recipes]).drop_duplicates(keep=False)
    )
    s.bullet(
        f"`accord_note` content match across workbooks: master vs accord_v2 differing rows = "
        f"**{len(diff_master_vs_v2)}**, master vs recipes differing rows = **{len(diff_master_vs_recipes)}**."
    )

    # Foreign key checks
    fk_checks = []

    def fk(name, child, parent, child_col, parent_col):
        miss = set(child[child_col].dropna().unique()) - set(parent[parent_col].dropna().unique())
        fk_checks.append(
            {"check": name, "n_orphans": len(miss), "examples": ",".join(sorted(miss)[:8])}
        )

    fk("accord_note.accord_id ⊆ accords.accord_id", canon["accord_note"], canon["accords"], "accord_id", "accord_id")
    fk("accord_note.note_id ⊆ notes_master.note_id", canon["accord_note"], canon["notes_master"], "note_id", "note_id")
    fk("accord_recipe_default.accord_id ⊆ accords.accord_id", canon["accord_recipe_default"], canon["accords"], "accord_id", "accord_id")
    fk("accord_recipe_default.note_id ⊆ notes_master.note_id", canon["accord_recipe_default"], canon["notes_master"], "note_id", "note_id")
    fk("training.target_accord_id_primary ⊆ accords.accord_id", canon["training_examples"], canon["accords"], "target_accord_id_primary", "accord_id")
    secondary = canon["training_examples"][canon["training_examples"]["target_accord_id_secondary"].notna()].rename(columns={"target_accord_id_secondary": "accord_id"})
    fk("training.target_accord_id_secondary ⊆ accords.accord_id", secondary, canon["accords"], "accord_id", "accord_id")
    refp = canon["training_examples"][canon["training_examples"]["target_perfume_id_reference"].notna()].rename(columns={"target_perfume_id_reference": "perfume_id"})
    fk("training.target_perfume_id_reference ⊆ perfumes.perfume_id", refp, canon["perfumes"], "perfume_id", "perfume_id")
    fk("perfume_accord.accord_id ⊆ accords.accord_id", canon["perfume_accord"], canon["accords"], "accord_id", "accord_id")
    fk("perfume_accord.perfume_id ⊆ perfumes.perfume_id", canon["perfume_accord"], canon["perfumes"], "perfume_id", "perfume_id")
    fk("perfume_note.note_id ⊆ notes_master.note_id", canon["perfume_note"], canon["notes_master"], "note_id", "note_id")
    fk("perfume_note.perfume_id ⊆ perfumes.perfume_id", canon["perfume_note"], canon["perfumes"], "perfume_id", "perfume_id")

    fk_df = pd.DataFrame(fk_checks)
    fk_rel = save_table(fk_df, "01_fk_checks")
    s.add_table_link("Foreign key integrity report", fk_rel)
    bad = fk_df[fk_df["n_orphans"] > 0]
    if len(bad):
        s.bullet(f"⚠️ {len(bad)} foreign-key checks found orphan IDs — see table.")
        for _, r in bad.iterrows():
            s.bullet(f"  - {r['check']}: **{r['n_orphans']}** orphans, e.g. {r['examples']}")
    else:
        s.bullet("✅ All foreign-key checks pass — every referenced ID exists in its parent catalog.")

    # Duplicate detection
    dup_rows = []
    for key, df in canon.items():
        if "id" in df.columns or any(c.endswith("_id") for c in df.columns):
            primary_id_candidates = [c for c in df.columns if c.endswith("_id") and "ref" not in c]
            if primary_id_candidates:
                pk = primary_id_candidates[0]
                dup_count = int(df[pk].duplicated().sum())
                dup_rows.append(
                    {
                        "table": key,
                        "primary_key_candidate": pk,
                        "duplicate_pk_rows": dup_count,
                    }
                )
    dup_df = pd.DataFrame(dup_rows)
    dup_rel = save_table(dup_df, "01_duplicate_pk_check")
    s.add_table_link("Duplicate primary-key check", dup_rel)

    return canon


# ----------------------------------------------------------------------------
# Section 2: Catalog sizes and coverage
# ----------------------------------------------------------------------------

def section_2_catalog(canon: dict[str, pd.DataFrame]) -> None:
    s = section("2. Catalog sizes and active vs dormant entries")

    accords = canon["accords"]
    notes = canon["notes_master"]
    te = canon["training_examples"]
    used_primary = set(te["target_accord_id_primary"].dropna().unique())
    used_secondary = set(te["target_accord_id_secondary"].dropna().unique())
    accords["used_as_primary"] = accords["accord_id"].isin(used_primary)
    accords["used_as_secondary"] = accords["accord_id"].isin(used_secondary)
    accords["used_in_training"] = accords["used_as_primary"] | accords["used_as_secondary"]

    s.line(f"Catalog: **{len(accords)} accords**, **{len(notes)} notes**.")
    s.bullet(f"Accords used as primary target: **{accords['used_as_primary'].sum()}**.")
    s.bullet(f"Accords used as secondary only: **{(accords['used_as_secondary'] & ~accords['used_as_primary']).sum()}**.")
    s.bullet(f"Accords never used as a target: **{(~accords['used_in_training']).sum()}** (dormant).")

    # accord category x usage
    by_cat = (
        accords.groupby("accord_category")["used_in_training"].agg(["sum", "count"]).rename(columns={"sum": "used", "count": "total"})
    )
    by_cat["util_pct"] = (100 * by_cat["used"] / by_cat["total"]).round(1)
    by_cat = by_cat.sort_values("total", ascending=False)
    s.add_table_link("Accord categories: catalog vs used", save_table(by_cat.reset_index(), "02_accord_category_usage"))

    # Top dormant accords
    dormant = accords[~accords["used_in_training"]][["accord_id", "accord_name", "accord_category"]]
    s.add_table_link("All dormant accords (never a training target)", save_table(dormant, "02_dormant_accords"))

    # Accord usage frequency chart
    primary_freq = te["target_accord_id_primary"].value_counts()
    plt.figure(figsize=(10, 4))
    plt.plot(np.arange(len(primary_freq)), primary_freq.values, lw=1.2)
    plt.fill_between(np.arange(len(primary_freq)), primary_freq.values, alpha=0.2)
    plt.yscale("log")
    plt.xlabel("Accord rank (sorted by frequency)")
    plt.ylabel("Times used as primary target (log)")
    plt.title(f"Primary-accord frequency (head→tail) — {len(primary_freq)} of {len(accords)} accords used")
    s.add_figure("Primary-accord frequency (log scale)", save_fig("02_primary_accord_freq"))

    # Save fully annotated accord catalog with usage flags
    save_table(accords, "02_accords_with_usage_flags")

    # Notes used in training (via accord_note membership of used accords)
    an = canon["accord_note"]
    used_notes = set(an[an["accord_id"].isin(used_primary | used_secondary)]["note_id"].unique())
    notes["used_via_used_accord"] = notes["note_id"].isin(used_notes)
    s.bullet(f"Notes reachable via a used accord (membership only): **{notes['used_via_used_accord'].sum()}** of {len(notes)} catalog notes.")

    # vocabularies
    desc_vocab = set(canon["descriptor_vocab"]["descriptor"].astype(str))
    occ_vocab = set(canon["occasion_vocab"]["occasion"].astype(str))
    desc_used = set()
    for x in te["descriptor_tags_csv"].dropna():
        desc_used.update([t.strip() for t in str(x).split(",") if t.strip()])
    occ_used = set(te["occasion_tag"].dropna().unique())

    s.bullet(f"Descriptor vocab: **{len(desc_vocab)}** canonical labels; descriptors actually used in training: **{len(desc_used)}** ({sorted(desc_used)}).")
    s.bullet(f"Descriptors in vocab but never used in training (`coverage gap`): {len(desc_vocab - desc_used)} — see table.")
    save_table(pd.DataFrame({"unused_descriptor": sorted(desc_vocab - desc_used)}), "02_unused_descriptors")
    s.bullet(f"Occasion vocab: **{len(occ_vocab)}**; occasions actually used: **{len(occ_used)}**.")
    save_table(pd.DataFrame({"unused_occasion": sorted(occ_vocab - occ_used)}), "02_unused_occasions")
    save_table(pd.DataFrame({"used_descriptor": sorted(desc_used)}), "02_used_descriptors")
    save_table(pd.DataFrame({"used_occasion": sorted(occ_used)}), "02_used_occasions")

    # Synonyms — verify the synonym tables actually map into the canonical vocabularies
    desc_syn = canon["descriptor_synonyms"]
    occ_syn = canon["occasion_synonyms"]
    bad_desc_syn = desc_syn[~desc_syn["canonical_descriptor"].isin(desc_vocab)]
    bad_occ_syn = occ_syn[~occ_syn["canonical_occasion"].isin(occ_vocab)]
    s.bullet(f"Descriptor synonym → canonical mapping integrity: {len(bad_desc_syn)} broken pointers.")
    s.bullet(f"Occasion synonym → canonical mapping integrity: {len(bad_occ_syn)} broken pointers.")
    if len(bad_desc_syn):
        save_table(bad_desc_syn, "02_broken_descriptor_synonyms")
    if len(bad_occ_syn):
        save_table(bad_occ_syn, "02_broken_occasion_synonyms")

    # Unmapped accord tokens from notes_v1
    s.bullet(
        "Unmapped accord tokens carried over from `notes_v1` (need canonical assignment): "
        f"**{len(canon['unmapped_accord_tokens'])}** — "
        + ", ".join(canon["unmapped_accord_tokens"]["raw_accord_token"].tolist())
    )


# ----------------------------------------------------------------------------
# Section 3: training_examples — null map, target distribution, feedback sparsity
# ----------------------------------------------------------------------------

def section_3_training(canon: dict[str, pd.DataFrame]) -> None:
    s = section("3. Training examples: targets, sparsity, demographics")

    te = canon["training_examples"].copy()
    n = len(te)

    # Null map
    nulls = te.isna().mean().sort_values(ascending=False)
    null_df = pd.DataFrame({"column": nulls.index, "null_pct": (100 * nulls.values).round(2)})
    save_table(null_df, "03_null_pct_per_column")
    s.bullet(f"Total examples: **{n:,}**.")
    for col, pct in null_df.set_index("column")["null_pct"].items():
        if pct > 0:
            s.bullet(f"`{col}` null rate: **{pct:.1f}%**.")

    # Sparsity bar chart
    plot_df = null_df[null_df["null_pct"] > 0].sort_values("null_pct")
    plt.figure(figsize=(8, 4))
    sns.barplot(data=plot_df, x="null_pct", y="column", color="C0")
    plt.xlabel("Null rate (%)")
    plt.title("Sparsity of training_examples columns")
    s.add_figure("Null rate per column", save_fig("03_null_rate_bar"))

    # Demographics histograms
    fig, axes = plt.subplots(2, 3, figsize=(13, 6))
    axes = axes.flatten()
    for ax, col in zip(axes, ["age", "age_bucket", "gender", "region", "background_tag", "occasion_tag"]):
        if pd.api.types.is_numeric_dtype(te[col]):
            sns.histplot(te[col], bins=20, ax=ax, color="C0")
        else:
            counts = te[col].fillna("MISSING").value_counts().sort_values(ascending=False)
            sns.barplot(x=counts.values, y=counts.index, ax=ax, color="C0")
        ax.set_title(col)
    plt.suptitle("Demographic & context distributions in training_examples", y=1.02)
    s.add_figure("Demographic and context distributions", save_fig("03_demographics"))

    # Descriptor frequency
    desc_counts = Counter()
    for x in te["descriptor_tags_csv"].dropna():
        for t in str(x).split(","):
            t = t.strip()
            if t:
                desc_counts[t] += 1
    desc_df = pd.DataFrame(desc_counts.items(), columns=["descriptor", "n"]).sort_values("n", ascending=False)
    save_table(desc_df, "03_descriptor_frequency")
    plt.figure(figsize=(8, 4))
    sns.barplot(data=desc_df, x="n", y="descriptor", color="C0")
    plt.title(f"Descriptor token frequency across {n:,} training examples")
    s.add_figure("Descriptor frequency", save_fig("03_descriptor_freq"))

    # Avoid-notes frequency
    avoid_counts = Counter()
    for x in te["avoid_notes_csv"].dropna():
        for t in str(x).split(","):
            t = t.strip()
            if t:
                avoid_counts[t] += 1
    avoid_df = pd.DataFrame(avoid_counts.items(), columns=["avoid_token", "n"]).sort_values("n", ascending=False)
    save_table(avoid_df, "03_avoid_token_frequency")

    plt.figure(figsize=(8, 4))
    sns.barplot(data=avoid_df.head(20), x="n", y="avoid_token", color="C3")
    plt.title("Top 20 avoid-note tokens")
    s.add_figure("Avoid-note token frequency", save_fig("03_avoid_freq"))

    # Number of descriptors per example
    te["n_descriptors"] = te["descriptor_tags_csv"].fillna("").apply(lambda x: 0 if x == "" else len([t for t in x.split(",") if t.strip()]))
    te["n_avoids"] = te["avoid_notes_csv"].fillna("").apply(lambda x: 0 if x == "" else len([t for t in x.split(",") if t.strip()]))
    summary = te[["n_descriptors", "n_avoids"]].describe().round(2)
    save_table(summary.reset_index(), "03_descriptor_and_avoid_counts_per_example")

    # Primary accord head/tail, gini, entropy
    primary_freq = te["target_accord_id_primary"].value_counts()
    p = primary_freq.values / primary_freq.sum()
    entropy = float(-(p * np.log2(p)).sum())
    gini = float(1 - np.sum(p ** 2))
    s.bullet(f"Primary-accord label entropy: **{entropy:.2f} bits** (max possible at uniform 200 classes ≈ {np.log2(200):.2f} bits).")
    s.bullet(f"Primary-accord Gini diversity: **{gini:.3f}** (1 − Σp²).")
    head_top1_share = float(primary_freq.iloc[0] / primary_freq.sum())
    head_top10_share = float(primary_freq.iloc[:10].sum() / primary_freq.sum())
    s.bullet(f"Top-1 accord share: **{head_top1_share:.1%}**; top-10 share: **{head_top10_share:.1%}**.")
    save_table(primary_freq.reset_index().rename(columns={"index": "accord_id", "target_accord_id_primary": "n"}), "03_primary_accord_freq")

    # Per-accord example counts: stratification feasibility
    n_le_1 = int((primary_freq <= 1).sum())
    n_le_5 = int((primary_freq <= 5).sum())
    n_le_10 = int((primary_freq <= 10).sum())
    s.bullet(f"Accords with ≤1 examples: **{n_le_1}**, ≤5: **{n_le_5}**, ≤10: **{n_le_10}** (stratified 80/10/10 splits will lose these).")

    # Secondary accord coverage
    has_secondary = te["target_accord_id_secondary"].notna()
    s.bullet(f"Secondary accord coverage: **{has_secondary.mean():.1%}** ({has_secondary.sum():,} of {n:,}).")

    # Reference perfume coverage
    has_ref = te["target_perfume_id_reference"].notna()
    s.bullet(f"Reference perfume coverage: **{has_ref.mean():.1%}** ({has_ref.sum():,} of {n:,}).")
    s.bullet(f"Distinct reference perfumes used: **{te['target_perfume_id_reference'].nunique()}** (out of 450 catalog perfumes).")

    # Feedback sparsity
    has_rating = te["user_rating_1_5"].notna()
    has_accept = te["accepted_flag"].notna()
    s.bullet(f"Explicit ratings: **{has_rating.sum():,}** ({has_rating.mean():.1%}).")
    s.bullet(f"Accepted flags: **{has_accept.sum():,}** ({has_accept.mean():.1%}).")
    if has_rating.any():
        plt.figure(figsize=(5, 3))
        sns.histplot(te.loc[has_rating, "user_rating_1_5"], bins=5, color="C2")
        plt.title("Distribution of explicit ratings (1–5)")
        s.add_figure("Rating distribution (where present)", save_fig("03_rating_distribution"))

    # Save the augmented training_examples for downstream sections
    save_intermediate(te, "training_examples_augmented")


# ----------------------------------------------------------------------------
# Section 4: user_text linguistic and leakage analysis
# ----------------------------------------------------------------------------

TEMPLATE_PATTERNS = [
    (r"^I'm (\d+)( and|.) (Looking for|Build me|Make it|Give me|Can you|I want|I’m).+", "Im_X_open"),
    (r"^Turning (\d+) soon\.", "turning_X_soon"),
    (r"^(\d+) here\.", "X_here"),
    (r"^Age (\d+)\.", "Age_X"),
    (r"^I am (\d+)\b", "I_am_X"),
    (r"^I want a perfume for ", "I_want_a_perfume_for"),
    (r"^Need a signature for ", "Need_a_signature_for"),
    (r"^Build me something around ", "Build_me_something_around"),
    (r"^Make it remind me of ", "Make_it_remind_me_of"),
    (r"^Can you do ", "Can_you_do"),
    (r"^Looking for something that fits ", "Looking_for_something_that_fits"),
    (r"^Give me a scent that screams ", "Give_me_a_scent"),
]


def detect_template(text: str) -> str:
    if not isinstance(text, str):
        return "OTHER"
    for pattern, label in TEMPLATE_PATTERNS:
        if re.search(pattern, text):
            return label
    return "OTHER"


def section_4_text(canon: dict[str, pd.DataFrame]) -> None:
    s = section("4. user_text linguistic analysis & label leakage")

    te = canon["training_examples"].copy()
    te["text_len_char"] = te["user_text"].astype(str).str.len()
    te["text_len_word"] = te["user_text"].astype(str).str.split().str.len()
    te["template"] = te["user_text"].apply(detect_template)

    # Length distribution
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.5))
    sns.histplot(te["text_len_char"], bins=30, ax=axes[0], color="C0")
    axes[0].set_title(f"Character length (mean {te['text_len_char'].mean():.0f}, median {te['text_len_char'].median():.0f})")
    sns.histplot(te["text_len_word"], bins=30, ax=axes[1], color="C0")
    axes[1].set_title(f"Word length (mean {te['text_len_word'].mean():.0f}, median {te['text_len_word'].median():.0f})")
    s.add_figure("user_text length distributions (chars / words)", save_fig("04_text_length"))

    tl_summary = te[["text_len_char", "text_len_word"]].describe().round(2)
    save_table(tl_summary.reset_index(), "04_text_length_summary")

    # Template detection
    tmpl_counts = te["template"].value_counts()
    save_table(tmpl_counts.reset_index().rename(columns={"index": "template", "template": "n"}), "04_template_distribution")
    plt.figure(figsize=(8, 4))
    sns.barplot(x=tmpl_counts.values, y=tmpl_counts.index, color="C0")
    plt.title("Template-pattern coverage of user_text (OTHER = unmatched)")
    plt.xlabel("# rows")
    s.add_figure("Template coverage", save_fig("04_template_coverage"))
    s.bullet(
        f"`OTHER` (unmatched-by-templates) rows: **{int(tmpl_counts.get('OTHER', 0))}** of {len(te):,}; "
        f"the templated leakage means downstream metrics on this corpus are an upper bound."
    )

    # Sample examples per template
    samples_rows = []
    for t, grp in te.groupby("template"):
        for x in grp["user_text"].head(3).tolist():
            samples_rows.append({"template": t, "example": x})
    save_table(pd.DataFrame(samples_rows), "04_template_samples")

    # Descriptor leakage rate
    def desc_leakage(row):
        if pd.isna(row["descriptor_tags_csv"]):
            return np.nan
        descs = [t.strip().lower() for t in str(row["descriptor_tags_csv"]).split(",") if t.strip()]
        text = str(row["user_text"]).lower()
        return float(np.mean([d in text for d in descs])) if descs else np.nan

    te["descriptor_leakage"] = te.apply(desc_leakage, axis=1)
    te["occasion_leakage"] = te.apply(
        lambda r: int(str(r["occasion_tag"]).lower() in str(r["user_text"]).lower())
        if pd.notna(r["occasion_tag"]) else np.nan,
        axis=1,
    )
    te["avoid_leakage"] = te.apply(
        lambda r: float(np.mean([
            t.strip().lower() in str(r["user_text"]).lower()
            for t in str(r["avoid_notes_csv"]).split(",") if t.strip()
        ])) if pd.notna(r["avoid_notes_csv"]) else np.nan,
        axis=1,
    )

    leak_summary = te[["descriptor_leakage", "occasion_leakage", "avoid_leakage"]].describe().round(3)
    save_table(leak_summary.reset_index(), "04_label_leakage_summary")
    s.bullet(f"Descriptor leakage rate (fraction of descriptors verbatim in text): mean **{te['descriptor_leakage'].mean():.2f}** — high means the encoder can solve much of the task by pattern-matching keywords.")
    s.bullet(f"Occasion leakage: mean **{te['occasion_leakage'].mean():.2f}**.")
    s.bullet(f"Avoid-tag leakage: mean **{te['avoid_leakage'].mean():.2f}**.")

    plt.figure(figsize=(8, 3.5))
    leak_long = te[["descriptor_leakage", "occasion_leakage", "avoid_leakage"]].melt(var_name="signal", value_name="leakage_rate").dropna()
    sns.boxplot(data=leak_long, x="leakage_rate", y="signal", color="C0")
    plt.title("Verbatim-leakage rate of structured tags into user_text")
    s.add_figure("Label leakage box plots", save_fig("04_label_leakage_box"))

    # Near-duplicate detection on user_text
    counts = te["user_text"].value_counts()
    near_dups = counts[counts > 1]
    s.bullet(f"Exact-duplicate user_text rows: **{int(near_dups.sum() - len(near_dups))}** rows participating in {len(near_dups)} duplicated strings.")
    if len(near_dups) > 0:
        save_table(near_dups.reset_index().rename(columns={"index": "user_text", "user_text": "n"}).head(50), "04_user_text_duplicates_top50")

    # Vocabulary statistics
    word_counts = Counter()
    for txt in te["user_text"].dropna().astype(str):
        for w in re.findall(r"[A-Za-z']+", txt.lower()):
            word_counts[w] += 1
    vocab_df = pd.DataFrame(word_counts.most_common(200), columns=["word", "n"])
    save_table(vocab_df, "04_top200_words_in_user_text")
    s.bullet(f"Unique words in user_text: **{len(word_counts):,}**; top words dominated by template glue (`I`, `for`, `something`, …).")

    # Save augmented training (with template + leakage features)
    save_intermediate(te, "training_examples_augmented_v2")


# ----------------------------------------------------------------------------
# Section 5–7: accord catalog, accord-note mapping, recipe defaults
# ----------------------------------------------------------------------------

def section_567_accord_recipes(canon: dict[str, pd.DataFrame]) -> None:
    s = section("5–7. Accord catalog, accord-note mapping, recipe defaults")

    accords = canon["accords"]
    an = canon["accord_note"]
    ar = canon["accord_recipe_default"]

    # 5. Accord category distribution
    cat_counts = accords["accord_category"].value_counts()
    save_table(cat_counts.reset_index().rename(columns={"index": "accord_category", "accord_category": "n"}), "05_accord_category_distribution")
    plt.figure(figsize=(7, 5))
    sns.barplot(x=cat_counts.head(20).values, y=cat_counts.head(20).index, color="C0")
    plt.title("Top-20 accord categories in catalog")
    s.add_figure("Top accord categories", save_fig("05_accord_category"))
    s.bullet(f"Accord catalog: **{len(accords)} entries** across **{accords['accord_category'].nunique()} categories**; 'Uncategorized' has **{int(cat_counts.get('Uncategorized', 0))}** entries — review if those should be tagged.")

    # 6. Accord-note structure
    npa = an.groupby("accord_id").size()
    apn = an.groupby("note_id").size()
    s.bullet(f"`accord_note` table: **{len(an):,}** edges over {an['accord_id'].nunique()} accords and {an['note_id'].nunique()} notes.")
    s.bullet(f"Notes per accord: mean **{npa.mean():.1f}**, median **{npa.median():.0f}**, min {npa.min()}, max {npa.max()}.")
    s.bullet(f"Accords per note: mean **{apn.mean():.2f}**, median **{apn.median():.0f}**, max {apn.max()} (=> some notes are extremely promiscuous).")

    fig, axes = plt.subplots(1, 2, figsize=(11, 3.5))
    sns.histplot(npa, bins=30, ax=axes[0], color="C0")
    axes[0].set_title("Notes per accord")
    sns.histplot(apn, bins=30, ax=axes[1], color="C0", log_scale=(False, True))
    axes[1].set_title("Accords per note (y log)")
    s.add_figure("accord-note degree distributions", save_fig("06_an_degrees"))

    # role/layer breakdown
    role_counts = an["note_role"].value_counts()
    layer_counts = an["layer"].value_counts()
    stab_counts = an["stability_class"].value_counts()
    save_table(role_counts.reset_index().rename(columns={"index": "note_role", "note_role": "n"}), "06_an_role_distribution")
    save_table(layer_counts.reset_index().rename(columns={"index": "layer", "layer": "n"}), "06_an_layer_distribution")
    save_table(stab_counts.reset_index().rename(columns={"index": "stability_class", "stability_class": "n"}), "06_an_stability_distribution")

    fig, axes = plt.subplots(1, 3, figsize=(13, 3.5))
    sns.barplot(x=role_counts.values, y=role_counts.index, ax=axes[0], color="C0")
    axes[0].set_title("Note role")
    sns.barplot(x=layer_counts.values, y=layer_counts.index, ax=axes[1], color="C0")
    axes[1].set_title("Layer (top/heart/base)")
    sns.barplot(x=stab_counts.values, y=stab_counts.index, ax=axes[2], color="C0")
    axes[2].set_title("Stability class")
    s.add_figure("accord_note role / layer / stability", save_fig("06_an_categorical"))

    # role x layer matrix
    rl = an.pivot_table(index="note_role", columns="layer", values="note_id", aggfunc="count", fill_value=0)
    save_table(rl.reset_index(), "06_role_x_layer")
    plt.figure(figsize=(7, 3.5))
    sns.heatmap(rl, annot=True, fmt="d", cmap="Blues")
    plt.title("Role × Layer counts in accord_note")
    s.add_figure("Role × Layer matrix", save_fig("06_role_x_layer_heatmap"))

    # numeric importance/presence/compatibility
    numeric_cols = ["importance_weight", "presence_prob", "compatibility_score"]
    save_table(an[numeric_cols].describe().round(3).reset_index(), "06_an_numeric_describe")
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.2))
    for ax, col in zip(axes, numeric_cols):
        sns.histplot(an[col], bins=30, ax=ax, color="C0")
        ax.set_title(col)
    s.add_figure("accord_note numeric features", save_fig("06_an_numeric"))

    # 7. Recipe defaults
    s.line("\n### Section 7 — accord_recipe_default")
    s.bullet(f"recipe_default rows: **{len(ar):,}** across **{ar['accord_id'].nunique()}** accords.")
    s.bullet(f"recipe versions present: {ar['recipe_version'].unique().tolist()}.")

    sum_per_accord = ar.groupby("accord_id")["default_pct_in_accord"].sum().round(3)
    save_table(sum_per_accord.reset_index(), "07_recipe_sum_per_accord")
    out_of_window = sum_per_accord[(sum_per_accord - 100).abs() > 0.5]
    s.bullet(f"Accords whose recipe sums **deviate from 100%**: {len(out_of_window)} → see table.")
    if len(out_of_window):
        save_table(out_of_window.reset_index(), "07_recipe_sum_outliers")
        s.bullet(f"  examples: {out_of_window.head(8).to_dict()}")

    layer_sum = ar.pivot_table(index="accord_id", columns="layer", values="default_pct_in_accord", aggfunc="sum", fill_value=0)
    save_table(layer_sum.reset_index(), "07_layer_total_per_accord")
    layer_describe = layer_sum.describe().round(2)
    save_table(layer_describe.reset_index(), "07_layer_total_describe")
    plt.figure(figsize=(8, 4))
    layer_sum_long = layer_sum.melt(var_name="layer", value_name="total_pct").dropna()
    sns.boxplot(data=layer_sum_long, x="total_pct", y="layer", color="C0")
    plt.title("Per-accord layer totals (claimed top25/heart45/base30)")
    s.add_figure("Layer total distributions per accord", save_fig("07_layer_totals_box"))

    # min/max windows
    ar["window_width"] = ar["max_pct_in_accord"] - ar["min_pct_in_accord"]
    ar["window_rel"] = ar["window_width"] / ar["default_pct_in_accord"].replace(0, np.nan)
    save_table(ar[["window_width", "window_rel"]].describe().round(3).reset_index(), "07_recipe_window_describe")
    plt.figure(figsize=(8, 3.5))
    sns.histplot(ar["window_rel"].dropna(), bins=40, color="C0")
    plt.title("Relative dosage window width  (max−min)/default")
    s.add_figure("Dosage window width", save_fig("07_window_width"))

    # min ≤ default ≤ max sanity
    ar["min_le_default"] = ar["min_pct_in_accord"] <= ar["default_pct_in_accord"]
    ar["default_le_max"] = ar["default_pct_in_accord"] <= ar["max_pct_in_accord"]
    bad = ar[~(ar["min_le_default"] & ar["default_le_max"])]
    s.bullet(f"Recipe rows that violate min ≤ default ≤ max: **{len(bad)}**.")
    if len(bad):
        save_table(bad, "07_recipe_window_violations")

    # default_pct distribution
    plt.figure(figsize=(8, 3.5))
    sns.histplot(ar["default_pct_in_accord"], bins=40, color="C0")
    plt.title("Distribution of default_pct_in_accord")
    s.add_figure("default_pct distribution", save_fig("07_default_pct"))

    # Notes per recipe
    per_acc_n_notes = ar.groupby("accord_id").size()
    s.bullet(f"Notes per recipe: mean **{per_acc_n_notes.mean():.1f}**, max **{per_acc_n_notes.max()}** (some accords are huge — investigate ACC-0097 with {int(per_acc_n_notes.get('ACC-0097', 0))} notes).")
    save_table(per_acc_n_notes.reset_index().rename(columns={0: "n_notes"}), "07_notes_per_recipe")


# ----------------------------------------------------------------------------
# Section 8: notes catalog & chemistry feature completeness
# ----------------------------------------------------------------------------

def section_8_notes(canon: dict[str, pd.DataFrame]) -> None:
    s = section("8. Notes catalog: chemistry & olfactory feature completeness")

    notes = canon["notes_master"].copy()
    s.bullet(f"`notes` (master) rows: **{len(notes):,}** total. Notes catalog is wider than rule-recipe usage.")

    cov = (notes.notna().mean().sort_values(ascending=False) * 100).round(2)
    cov_df = pd.DataFrame({"column": cov.index, "coverage_pct": cov.values})
    save_table(cov_df, "08_note_feature_coverage")
    plt.figure(figsize=(8, 9))
    sns.barplot(data=cov_df, x="coverage_pct", y="column", color="C0")
    plt.title("Feature coverage in notes (master) — % non-null per column")
    s.add_figure("Note feature coverage", save_fig("08_note_feature_coverage"))

    # Stub vs full
    notes["is_stub"] = notes[["chemical_name", "cas_number_clean", "molecular_weight", "logP", "boiling_point_c"]].isna().all(axis=1)
    s.bullet(f"Stub notes (no chemistry data at all): **{int(notes['is_stub'].sum())}** of {len(notes):,} ({notes['is_stub'].mean():.1%}).")
    s.bullet(f"Notes with full chemistry (chemical_name + CAS + MW + logP + BP): **{int((~notes['is_stub']).sum())}**.")

    # Categorical distributions
    for col, kmax in [("chemical_family", 25), ("odor_family", 20), ("volatility_class", 10), ("solubility", 10), ("natural_source", 30)]:
        if col not in notes.columns:
            continue
        cnt = notes[col].fillna("MISSING").value_counts().head(kmax)
        save_table(cnt.reset_index().rename(columns={"index": col, col: "n"}), f"08_notes_{col}_top{kmax}")
        plt.figure(figsize=(8, max(3, len(cnt) * 0.25)))
        sns.barplot(x=cnt.values, y=cnt.index, color="C0")
        plt.title(f"Top {kmax} {col} values in notes")
        s.add_figure(f"notes.{col} distribution", save_fig(f"08_notes_{col}"))

    # Numeric features
    num_cols = [c for c in ["molecular_weight", "boiling_point_c", "logP", "odor_threshold_mg_L", "substantivity_index", "tenacity_min_hrs", "tenacity_max_hrs", "flash_point_c"] if c in notes.columns]
    save_table(notes[num_cols].describe().round(3).reset_index(), "08_notes_numeric_describe")

    fig, axes = plt.subplots(2, 4, figsize=(15, 7))
    axes = axes.flatten()
    for ax, col in zip(axes, num_cols):
        sns.histplot(notes[col].dropna(), bins=30, ax=ax, color="C0")
        ax.set_title(f"{col} (n={notes[col].notna().sum()})")
    for ax in axes[len(num_cols):]:
        ax.axis("off")
    s.add_figure("Numeric note feature distributions", save_fig("08_notes_numeric_hist"))

    # Outliers (z>4) per numeric column
    outlier_rows = []
    for col in num_cols:
        x = notes[col].dropna()
        if x.std() == 0 or x.empty:
            continue
        z = (x - x.mean()) / x.std()
        out = notes.loc[z[z.abs() > 4].index, ["note_id", "note_name", col]]
        for _, r in out.iterrows():
            outlier_rows.append({"col": col, "note_id": r["note_id"], "note_name": r["note_name"], "value": r[col]})
    if outlier_rows:
        save_table(pd.DataFrame(outlier_rows), "08_notes_numeric_outliers")
        s.bullet(f"|z|>4 numeric outliers: **{len(outlier_rows)}** — review for entry errors.")

    # CAS coverage and uniqueness
    cas = notes["cas_number_clean"].dropna()
    s.bullet(f"CAS coverage: **{len(cas):,}** notes have a CAS ({len(cas) / len(notes):.1%}).")
    s.bullet(f"CAS uniqueness: **{cas.nunique()}** unique CAS strings.")
    dup_cas = cas[cas.duplicated(keep=False)]
    if len(dup_cas):
        dup_cas_df = notes[notes["cas_number_clean"].isin(dup_cas)][["note_id", "note_name", "cas_number_clean"]].sort_values("cas_number_clean")
        save_table(dup_cas_df, "08_duplicate_cas_notes")
        s.bullet(f"Notes sharing a CAS with another note: **{len(dup_cas_df)}** rows — these likely refer to the same molecule with different names.")

    # CAS regex sanity
    cas_pat = re.compile(r"^\d{1,7}-\d{2}-\d$")
    bad_cas = notes[notes["cas_number_clean"].notna() & ~notes["cas_number_clean"].astype(str).str.strip().str.match(cas_pat)]
    s.bullet(f"Malformed CAS strings: **{len(bad_cas)}**.")
    if len(bad_cas):
        save_table(bad_cas[["note_id", "note_name", "cas_number_clean"]], "08_malformed_cas")

    # tenacity_min vs max sanity
    if "tenacity_min_hrs" in notes.columns and "tenacity_max_hrs" in notes.columns:
        bad_t = notes[(notes["tenacity_min_hrs"] > notes["tenacity_max_hrs"])][["note_id", "note_name", "tenacity_min_hrs", "tenacity_max_hrs"]]
        s.bullet(f"Notes with tenacity_min > tenacity_max: **{len(bad_t)}**.")
        if len(bad_t):
            save_table(bad_t, "08_tenacity_anomalies")

    save_intermediate(notes, "notes_master_augmented")


# ----------------------------------------------------------------------------
# Section 9: cross-source consistency (the 50/446 problem)
# ----------------------------------------------------------------------------

def section_9_cross_source(canon: dict[str, pd.DataFrame]) -> None:
    s = section("9. Cross-source consistency: rule-recipe notes vs real-perfume notes")

    an = canon["accord_note"]
    pn = canon["perfume_note"]
    notes = canon["notes_master"]

    rule_notes = set(an["note_id"].unique())
    real_notes = set(pn["note_id"].unique())
    catalog = set(notes["note_id"].unique())

    overlap_rr = rule_notes & real_notes
    rule_only = rule_notes - real_notes
    real_only = real_notes - rule_notes

    s.bullet(f"Catalog notes total: **{len(catalog):,}**.")
    s.bullet(f"In rule recipes (`accord_note`): **{len(rule_notes):,}**.")
    s.bullet(f"In real perfumes (`perfume_note`): **{len(real_notes):,}**.")
    s.bullet(f"**Overlap (in both)**: **{len(overlap_rr):,}**.")
    s.bullet(f"Rule-only (note appears in rule recipes but never in any real perfume): **{len(rule_only):,}**.")
    s.bullet(f"Real-only (note appears in real perfumes but never in any rule recipe): **{len(real_only):,}**.")

    # Save lists for the bridge-table preprocessing step
    save_table(notes[notes["note_id"].isin(rule_only)][["note_id", "note_name", "normalized_note_name", "chemical_family", "odor_family"]], "09_rule_only_notes")
    save_table(notes[notes["note_id"].isin(real_only)][["note_id", "note_name", "normalized_note_name", "chemical_family", "odor_family"]], "09_real_only_notes")
    save_table(notes[notes["note_id"].isin(overlap_rr)][["note_id", "note_name", "normalized_note_name", "chemical_family", "odor_family"]], "09_overlap_notes")

    # Counts in each side weighted by rows
    rule_volume = an["note_id"].value_counts()
    real_volume = pn["note_id"].value_counts()
    bridge = pd.DataFrame({
        "note_id": list(catalog),
    })
    bridge = bridge.merge(notes[["note_id", "note_name", "normalized_note_name"]], on="note_id", how="left")
    bridge["in_rule"] = bridge["note_id"].isin(rule_notes)
    bridge["in_real"] = bridge["note_id"].isin(real_notes)
    bridge["rule_volume"] = bridge["note_id"].map(rule_volume).fillna(0).astype(int)
    bridge["real_volume"] = bridge["note_id"].map(real_volume).fillna(0).astype(int)
    bridge["status"] = bridge.apply(
        lambda r: "BOTH" if r["in_rule"] and r["in_real"]
        else "RULE_ONLY" if r["in_rule"]
        else "REAL_ONLY" if r["in_real"]
        else "ORPHAN_CATALOG",
        axis=1,
    )
    save_table(bridge.sort_values(["status", "note_id"]), "09_note_bridge_table")

    # Pie / bar of the status
    plt.figure(figsize=(7, 3.5))
    sns.countplot(data=bridge, x="status", order=["BOTH", "RULE_ONLY", "REAL_ONLY", "ORPHAN_CATALOG"], color="C0")
    plt.title("Note presence: rule-recipe space vs real-perfume space")
    s.add_figure("Note status across rule/real spaces", save_fig("09_note_status"))

    # The same analysis for accord_id
    pa = canon["perfume_accord"]
    rule_accords = set(an["accord_id"].unique())
    real_accords = set(pa["accord_id"].unique())
    s.bullet(f"Accords in rule recipes: **{len(rule_accords)}**; accords in real perfumes: **{len(real_accords)}**; overlap: **{len(rule_accords & real_accords)}**; rule-only: **{len(rule_accords - real_accords)}**; real-only: **{len(real_accords - rule_accords)}**.")
    a_bridge = canon["accords"][["accord_id", "accord_name", "accord_category"]].copy()
    a_bridge["in_rule"] = a_bridge["accord_id"].isin(rule_accords)
    a_bridge["in_real"] = a_bridge["accord_id"].isin(real_accords)
    a_bridge["status"] = a_bridge.apply(
        lambda r: "BOTH" if r["in_rule"] and r["in_real"]
        else "RULE_ONLY" if r["in_rule"]
        else "REAL_ONLY" if r["in_real"]
        else "CATALOG_ONLY",
        axis=1,
    )
    save_table(a_bridge.sort_values(["status", "accord_id"]), "09_accord_bridge_table")
    plt.figure(figsize=(7, 3.5))
    sns.countplot(data=a_bridge, x="status", order=["BOTH", "RULE_ONLY", "REAL_ONLY", "CATALOG_ONLY"], color="C0")
    plt.title("Accord presence: rule-recipe space vs real-perfume space")
    s.add_figure("Accord status across rule/real spaces", save_fig("09_accord_status"))


# ----------------------------------------------------------------------------
# Section 10: real-perfume catalog properties
# ----------------------------------------------------------------------------

def section_10_perfumes(canon: dict[str, pd.DataFrame]) -> None:
    s = section("10. Real-perfume catalog (Sauvage / Bleu de Chanel / etc.)")

    pf = canon["perfumes"]
    pa = canon["perfume_accord"]
    pn = canon["perfume_note"]
    s.bullet(f"Perfumes: **{len(pf)}** entries, {pf['brand'].nunique()} brands, {pf['fragrance_family'].nunique()} families.")

    fam_counts = pf["fragrance_family"].fillna("MISSING").value_counts().head(20)
    plt.figure(figsize=(8, 5))
    sns.barplot(x=fam_counts.values, y=fam_counts.index, color="C0")
    plt.title("Top-20 fragrance families in real-perfume catalog")
    s.add_figure("Top fragrance families", save_fig("10_perfume_family"))
    save_table(fam_counts.reset_index().rename(columns={"index": "fragrance_family", "fragrance_family": "n"}), "10_perfume_family")

    brand_counts = pf["brand"].fillna("MISSING").value_counts().head(25)
    save_table(brand_counts.reset_index().rename(columns={"index": "brand", "brand": "n"}), "10_perfume_brand_top25")
    plt.figure(figsize=(8, 5))
    sns.barplot(x=brand_counts.values, y=brand_counts.index, color="C0")
    plt.title("Top-25 brands in catalog")
    s.add_figure("Top brands", save_fig("10_perfume_brand"))

    gender_counts = pf["gender"].fillna("MISSING").value_counts()
    long_counts = pf["longevity"].fillna("MISSING").value_counts()
    sill_counts = pf["sillage"].fillna("MISSING").value_counts()
    save_table(pd.concat({
        "gender": gender_counts, "longevity": long_counts, "sillage": sill_counts}).reset_index(name="n").rename(columns={"level_0": "field", "level_1": "value"}), "10_perfume_meta_counts")

    # accords and notes per perfume
    apf = pa.groupby("perfume_id").size()
    npf = pn.groupby("perfume_id").size()
    s.bullet(f"Accords per perfume: mean **{apf.mean():.2f}**, median {apf.median():.0f}, max {apf.max()}.")
    s.bullet(f"Notes per perfume: mean **{npf.mean():.2f}**, median {npf.median():.0f}, max {npf.max()}.")
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.5))
    sns.histplot(apf, bins=20, ax=axes[0], color="C0"); axes[0].set_title("Accords per perfume")
    sns.histplot(npf, bins=20, ax=axes[1], color="C0"); axes[1].set_title("Notes per perfume")
    s.add_figure("Accords/notes per perfume", save_fig("10_perfume_degrees"))

    # Note position distribution
    pos_counts = pn["position"].fillna("MISSING").value_counts()
    save_table(pos_counts.reset_index().rename(columns={"index": "position", "position": "n"}), "10_perfume_note_position")
    s.bullet(f"perfume_note position counts: {pos_counts.to_dict()}.")

    # Accord rank distribution
    rank_counts = pa["accord_rank"].value_counts().sort_index()
    save_table(rank_counts.reset_index().rename(columns={"index": "accord_rank", "accord_rank": "n"}), "10_perfume_accord_rank")


# ----------------------------------------------------------------------------
# Section 11: reference-perfume label quality
# ----------------------------------------------------------------------------

def section_11_reference_quality(canon: dict[str, pd.DataFrame]) -> None:
    s = section("11. Reference-perfume label quality (the 1.9% problem)")

    te = canon["training_examples"]
    pa = canon["perfume_accord"]
    perfume_accords = pa.groupby("perfume_id")["accord_id"].apply(set).to_dict()

    has_ref = te["target_perfume_id_reference"].notna()
    n_ref = has_ref.sum()
    matches_primary = 0
    matches_any = 0
    detail_rows = []
    for _, row in te[has_ref].iterrows():
        ref = row["target_perfume_id_reference"]
        primary = row["target_accord_id_primary"]
        secondary = row["target_accord_id_secondary"]
        ref_accords = perfume_accords.get(ref, set())
        m_primary = primary in ref_accords
        m_secondary = secondary in ref_accords if pd.notna(secondary) else False
        m_any = m_primary or m_secondary
        if m_primary:
            matches_primary += 1
        if m_any:
            matches_any += 1
        detail_rows.append({"request_id": row["request_id"], "perfume_id": ref, "primary_accord": primary, "secondary_accord": secondary, "primary_in_ref": m_primary, "any_in_ref": m_any, "ref_accord_count": len(ref_accords)})
    detail = pd.DataFrame(detail_rows)
    save_table(detail, "11_reference_perfume_match_detail")
    s.bullet(f"Examples with reference perfume: **{n_ref:,}**.")
    s.bullet(f"Reference perfume's accord list contains the labeled **primary** accord: **{matches_primary} ({matches_primary/n_ref:.2%})**.")
    s.bullet(f"Reference contains **either primary or secondary**: **{matches_any} ({matches_any/n_ref:.2%})**.")
    plt.figure(figsize=(6, 3))
    sns.countplot(data=detail, x="primary_in_ref", color="C3")
    plt.title("Does the reference perfume contain the labeled primary accord?")
    s.add_figure("Reference primary-accord match", save_fig("11_reference_match"))

    # Distribution of ref accord count
    plt.figure(figsize=(7, 3))
    sns.histplot(detail["ref_accord_count"], bins=20, color="C0")
    plt.title("Number of accords in the referenced perfume")
    s.add_figure("Accord count of referenced perfumes", save_fig("11_ref_accord_count"))


# ----------------------------------------------------------------------------
# Section 12: bigram / co-occurrence matrices
# ----------------------------------------------------------------------------

def section_12_bigrams(canon: dict[str, pd.DataFrame]) -> None:
    s = section("12. Conditional distributions (descriptor / occasion / region / age / gender / background → primary accord)")

    te = canon["training_examples"].copy()
    accords = canon["accords"].set_index("accord_id")["accord_name"].to_dict()

    # Build a long descriptor table
    desc_long_rows = []
    for _, row in te.iterrows():
        if pd.isna(row["descriptor_tags_csv"]):
            continue
        for d in str(row["descriptor_tags_csv"]).split(","):
            d = d.strip()
            if d:
                desc_long_rows.append({"descriptor": d, "primary_accord_id": row["target_accord_id_primary"]})
    desc_long = pd.DataFrame(desc_long_rows)
    desc_long["primary_accord_name"] = desc_long["primary_accord_id"].map(accords)

    # Top-3 accord per descriptor
    top3 = (
        desc_long.groupby(["descriptor", "primary_accord_name"]).size().reset_index(name="n")
        .sort_values(["descriptor", "n"], ascending=[True, False])
        .groupby("descriptor").head(3)
    )
    save_table(top3, "12_descriptor_top3_accord")

    # Heatmap: descriptor x top-N most-frequent accord categories
    desc_cat_long = desc_long.merge(
        canon["accords"][["accord_id", "accord_category"]],
        left_on="primary_accord_id", right_on="accord_id", how="left",
    )
    pivot = desc_cat_long.pivot_table(index="descriptor", columns="accord_category", values="primary_accord_id", aggfunc="count", fill_value=0)
    # keep top-15 categories
    top_cats = pivot.sum().sort_values(ascending=False).head(15).index
    pivot_top = pivot[top_cats]
    save_table(pivot_top.reset_index(), "12_descriptor_x_accord_category")
    plt.figure(figsize=(11, 5))
    sns.heatmap(pivot_top, cmap="Blues", annot=True, fmt="d", cbar_kws={"label": "n examples"})
    plt.title("Descriptor × Accord-category co-occurrence in training_examples")
    s.add_figure("Descriptor × Accord-category heatmap", save_fig("12_descriptor_x_category"))

    # Helper function for arbitrary categorical → primary_accord_category
    def cat_x_category(field: str, fname: str, top_k_field: int = 15):
        rows = []
        for _, r in te.iterrows():
            rows.append({"field_value": r[field], "primary_accord_id": r["target_accord_id_primary"]})
        df_ = pd.DataFrame(rows).merge(
            canon["accords"][["accord_id", "accord_category"]], left_on="primary_accord_id", right_on="accord_id", how="left"
        )
        pv = df_.pivot_table(index="field_value", columns="accord_category", values="primary_accord_id", aggfunc="count", fill_value=0)
        cats = pv.sum().sort_values(ascending=False).head(15).index
        pv_top = pv[cats].sort_index()
        save_table(pv_top.reset_index().rename(columns={"field_value": field}), f"12_{fname}_x_accord_category")
        plt.figure(figsize=(11, max(3, len(pv_top) * 0.3)))
        sns.heatmap(pv_top, cmap="Blues", annot=True, fmt="d", cbar=False)
        plt.title(f"{field} × Accord-category counts")
        s.add_figure(f"{field} × accord_category", save_fig(f"12_{fname}_x_category"))

    cat_x_category("occasion_tag", "occasion")
    cat_x_category("background_tag", "background")
    cat_x_category("region", "region")
    cat_x_category("gender", "gender")
    cat_x_category("age_bucket", "agebucket")

    # Primary × secondary accord co-occurrence (for the label-correlation regulariser)
    pair = te[te["target_accord_id_secondary"].notna()].groupby(
        ["target_accord_id_primary", "target_accord_id_secondary"]
    ).size().reset_index(name="n").sort_values("n", ascending=False)
    save_table(pair, "12_primary_secondary_pair_counts")
    s.bullet(f"Distinct (primary, secondary) accord pairs: **{len(pair):,}**.")

    # Top 30 pairs heatmap
    top_pairs = pair.head(30).copy()
    top_pairs["primary"] = top_pairs["target_accord_id_primary"].map(accords)
    top_pairs["secondary"] = top_pairs["target_accord_id_secondary"].map(accords)
    save_table(top_pairs[["primary", "secondary", "n"]], "12_primary_secondary_top30")


# ----------------------------------------------------------------------------
# Section 13: avoid contradictions and exclusion patterns
# ----------------------------------------------------------------------------

def section_13_avoid(canon: dict[str, pd.DataFrame]) -> None:
    s = section("13. Avoid-notes patterns and contradictions")

    te = canon["training_examples"].copy()

    # contradictions: descriptor and avoid both contain the same token (e.g. user wants 'sweet' but avoids 'sweet')
    contradictions = []
    for _, r in te.iterrows():
        if pd.isna(r["avoid_notes_csv"]) or pd.isna(r["descriptor_tags_csv"]):
            continue
        descs = {t.strip().lower() for t in str(r["descriptor_tags_csv"]).split(",") if t.strip()}
        avoids = {t.strip().lower() for t in str(r["avoid_notes_csv"]).split(",") if t.strip()}
        clash = descs & avoids
        if clash:
            contradictions.append({"request_id": r["request_id"], "clash": ",".join(sorted(clash))})
    cdf = pd.DataFrame(contradictions)
    save_table(cdf, "13_descriptor_avoid_contradictions")
    s.bullet(f"Examples where the same token appears in both `descriptor_tags_csv` and `avoid_notes_csv` (e.g. user says 'sweet' but also lists 'sweet' as an avoid): **{len(cdf):,}** — these are dataset noise the loss should learn to suppress.")

    # avoid frequency vs how often that token is also a descriptor in the same row
    pivot_rows = []
    for _, r in te.iterrows():
        if pd.isna(r["avoid_notes_csv"]):
            continue
        descs = {t.strip().lower() for t in str(r["descriptor_tags_csv"]).split(",") if t.strip()} if pd.notna(r["descriptor_tags_csv"]) else set()
        for av in {t.strip().lower() for t in str(r["avoid_notes_csv"]).split(",") if t.strip()}:
            pivot_rows.append({"avoid_token": av, "descriptor_overlap": av in descs})
    pdf = pd.DataFrame(pivot_rows)
    overlap_rate = pdf.groupby("avoid_token")["descriptor_overlap"].mean().sort_values(ascending=False)
    save_table(overlap_rate.reset_index().rename(columns={"descriptor_overlap": "rate_appearing_as_descriptor_too"}), "13_avoid_token_overlap_with_descriptor")


# ----------------------------------------------------------------------------
# Section 14: stratification feasibility (by primary accord)
# ----------------------------------------------------------------------------

def section_14_strat(canon: dict[str, pd.DataFrame]) -> None:
    s = section("14. Train / val / test stratification feasibility")

    te = canon["training_examples"]
    pf = te["target_accord_id_primary"].value_counts()
    bins = [0, 1, 5, 10, 25, 50, 100, 250, 500, 100000]
    labels = ["1", "2-5", "6-10", "11-25", "26-50", "51-100", "101-250", "251-500", "501+"]
    bucketed = pd.cut(pf, bins=bins, labels=labels)
    counts = bucketed.value_counts().reindex(labels).fillna(0).astype(int)
    counts_df = pd.DataFrame({"examples_per_accord_bucket": counts.index.astype(str), "n_accords": counts.values})
    save_table(counts_df, "14_strat_bucket_counts")
    plt.figure(figsize=(8, 3.5))
    sns.barplot(x=counts.index, y=counts.values, color="C0")
    plt.xlabel("examples per accord (bucket)")
    plt.ylabel("# accords")
    plt.title("How many accords have how many examples?")
    s.add_figure("Examples-per-accord buckets", save_fig("14_strat_buckets"))

    s.bullet(f"Accords with < 10 examples: **{int((pf < 10).sum())}** — these cannot be cleanly stratified at 80/10/10 (need either pooling, oversampling, or excluding from validation).")
    s.bullet(f"Accords with 1 example: **{int((pf == 1).sum())}** — these will sit in only one of the three splits.")

    # If we were to do 80/10/10 stratified, what fraction of accords would have at least 1 val and 1 test example?
    feasible = int((pf >= 10).sum())
    s.bullet(f"Accords with ≥ 10 examples (clean 80/10/10 strat OK): **{feasible}**.")


# ----------------------------------------------------------------------------
# Section 15: edge cases and anomalies
# ----------------------------------------------------------------------------

def section_15_edges(canon: dict[str, pd.DataFrame]) -> None:
    s = section("15. Edge cases and anomalies")

    te = canon["training_examples"].copy()

    # Encoding artefacts: smart quotes, unusual whitespace, control chars
    suspicious = te[te["user_text"].astype(str).str.contains(r"[‘’“”—–]", regex=True)]
    s.bullet(f"user_text rows with curly quotes / em-dashes / en-dashes: **{len(suspicious):,}** (normalize during preprocessing).")

    # Repeated phrases (e.g., "I’m from UK. I’m from UK.")
    repeats = te[te["user_text"].astype(str).apply(lambda x: any(x.count(p) > 1 for p in re.findall(r"I’m from \w+\.", x)))]
    s.bullet(f"user_text rows with repeated regional clauses (likely templating bug): **{len(repeats):,}**.")
    if len(repeats):
        save_table(repeats[["request_id", "user_text"]].head(50), "15_repeated_phrase_examples")

    # Are any two rows identical besides request_id and timestamp?
    dup_keys = ["user_text", "age", "gender", "region", "background_tag", "occasion_tag", "descriptor_tags_csv", "avoid_notes_csv"]
    dup = te[te.duplicated(subset=dup_keys, keep=False)].sort_values(dup_keys)
    s.bullet(f"Rows that are identical on all input fields (apart from request_id, created_at, target/feedback): **{len(dup):,}**.")
    if len(dup):
        save_table(dup.head(100), "15_duplicate_input_rows_top100")

    # created_at sanity
    te["created_at_parsed"] = pd.to_datetime(te["created_at"], errors="coerce", utc=True)
    bad_dt = int(te["created_at_parsed"].isna().sum())
    s.bullet(f"Unparseable `created_at` values: **{bad_dt}**.")
    if not te["created_at_parsed"].isna().all():
        plt.figure(figsize=(8, 3))
        sns.histplot(te["created_at_parsed"].dropna(), bins=40, color="C0")
        plt.title("created_at distribution (timestamps)")
        s.add_figure("created_at distribution", save_fig("15_created_at"))
        save_table(te["created_at_parsed"].describe().reset_index(), "15_created_at_describe")

    # Age vs age_bucket consistency
    def expected_bucket(age):
        if pd.isna(age):
            return None
        if age <= 17:
            return "<18"
        if age <= 24:
            return "18-24"
        if age <= 34:
            return "25-34"
        if age <= 44:
            return "35-44"
        return "45+"

    te["expected_age_bucket"] = te["age"].apply(expected_bucket)
    bad_age = te[te["age_bucket"] != te["expected_age_bucket"]]
    s.bullet(f"Rows where `age_bucket` doesn't match `age`: **{len(bad_age):,}**.")
    if len(bad_age):
        save_table(bad_age[["request_id", "age", "age_bucket", "expected_age_bucket"]].head(50), "15_age_bucket_mismatch")


# ----------------------------------------------------------------------------
# Section 16: ratings & accepted-flag conditional patterns
# ----------------------------------------------------------------------------

def section_16_feedback(canon: dict[str, pd.DataFrame]) -> None:
    s = section("16. Feedback signal: rating & accepted_flag conditional patterns")

    te = canon["training_examples"].copy()
    has_rating = te["user_rating_1_5"].notna()
    has_accept = te["accepted_flag"].notna()
    s.bullet(f"Ratings present: **{int(has_rating.sum())} ({has_rating.mean():.1%})**; accepted flags present: **{int(has_accept.sum())} ({has_accept.mean():.1%})**.")

    if has_rating.any():
        # Rating x background_tag
        rb = te[has_rating].groupby("background_tag")["user_rating_1_5"].agg(["mean", "count"]).round(3)
        save_table(rb.reset_index(), "16_rating_by_background")
        # Rating x region
        rr = te[has_rating].groupby("region")["user_rating_1_5"].agg(["mean", "count"]).round(3)
        save_table(rr.reset_index(), "16_rating_by_region")
        # Rating x age_bucket
        ra = te[has_rating].groupby("age_bucket")["user_rating_1_5"].agg(["mean", "count"]).round(3)
        save_table(ra.reset_index(), "16_rating_by_age_bucket")

        plt.figure(figsize=(8, 4))
        sns.boxplot(data=te[has_rating], x="background_tag", y="user_rating_1_5", color="C0")
        plt.xticks(rotation=30, ha="right")
        plt.title("Rating distribution by background_tag")
        s.add_figure("Rating × background_tag", save_fig("16_rating_x_background"))

    if has_accept.any():
        ab = te[has_accept].groupby("background_tag")["accepted_flag"].agg(["mean", "count"]).round(3)
        save_table(ab.reset_index(), "16_accept_by_background")


# ----------------------------------------------------------------------------
# Section 17: notes_v1 secondary table — note_accord_usage cross-check
# ----------------------------------------------------------------------------

def section_17_note_accord_usage(canon: dict[str, pd.DataFrame]) -> None:
    s = section("17. Cross-check: notes_v1 `note_accord_usage` vs master `accord_note`")
    nau = canon["note_accord_usage"]
    an = canon["accord_note"]
    s.bullet(f"`note_accord_usage` rows: **{len(nau):,}**.")
    s.bullet(f"`accord_note` rows: **{len(an):,}**.")

    nau_set = set(zip(nau["note_id"], nau["accord_id"]))
    an_set = set(zip(an["note_id"], an["accord_id"]))
    common = nau_set & an_set
    only_nau = nau_set - an_set
    only_an = an_set - nau_set
    s.bullet(f"Pairs in both: **{len(common):,}**; only in note_accord_usage: **{len(only_nau):,}**; only in accord_note: **{len(only_an):,}**.")
    if only_nau:
        save_table(pd.DataFrame(list(only_nau), columns=["note_id", "accord_id"]).head(200), "17_pairs_only_in_note_accord_usage")
    if only_an:
        save_table(pd.DataFrame(list(only_an), columns=["note_id", "accord_id"]).head(200), "17_pairs_only_in_accord_note")


# ----------------------------------------------------------------------------
# Section 18: real-world layer position vs rule layer
# ----------------------------------------------------------------------------

def section_18_layer_reality_check(canon: dict[str, pd.DataFrame]) -> None:
    s = section("18. Layer-reality check: real perfumes vs rule recipes")

    pn = canon["perfume_note"]
    real_layers = pn["position"].fillna("MISSING").value_counts(normalize=True).round(3)
    save_table(real_layers.reset_index().rename(columns={"index": "position", "position": "share"}), "18_real_perfume_layer_share")

    an = canon["accord_note"]
    rule_layers = an["layer"].fillna("MISSING").value_counts(normalize=True).round(3)
    save_table(rule_layers.reset_index().rename(columns={"index": "layer", "layer": "share"}), "18_rule_recipe_layer_share")
    s.bullet(f"Real perfume note layer share: {real_layers.to_dict()}.")
    s.bullet(f"Rule recipe layer share: {rule_layers.to_dict()}.")
    s.bullet("Rule recipes are heavily base-skewed; real perfumes are roughly even — confirms the layer prior in the rule formula doesn't reflect commercial perfume composition.")


# ----------------------------------------------------------------------------
# Section 19: descriptor_synonyms / occasion_synonyms feasibility
# ----------------------------------------------------------------------------

def section_19_synonyms(canon: dict[str, pd.DataFrame]) -> None:
    s = section("19. Synonym tables — coverage of phrasings actually seen in user_text")

    desc_syn = canon["descriptor_synonyms"]
    occ_syn = canon["occasion_synonyms"]
    te = canon["training_examples"]

    # Compute how many user_text rows match a synonym phrase but the canonical descriptor isn't currently in descriptor_tags_csv
    desc_phrases = desc_syn.dropna(subset=["phrase"])[["canonical_descriptor", "phrase"]].copy()
    desc_phrases["phrase_lc"] = desc_phrases["phrase"].astype(str).str.lower()
    additions = []
    for _, r in te.iterrows():
        text = str(r["user_text"]).lower()
        existing = {t.strip().lower() for t in str(r["descriptor_tags_csv"]).split(",") if t.strip()}
        for _, dp in desc_phrases.iterrows():
            if dp["phrase_lc"] and dp["phrase_lc"] in text and dp["canonical_descriptor"].lower() not in existing:
                additions.append({"request_id": r["request_id"], "phrase": dp["phrase"], "canonical_descriptor": dp["canonical_descriptor"]})
    add_df = pd.DataFrame(additions)
    save_table(add_df, "19_descriptor_synonym_recoverable_additions")
    s.bullet(f"Potential additional descriptor labels recoverable from user_text via synonyms (currently missing from descriptor_tags_csv): **{len(add_df):,}** rows.")
    if len(add_df):
        save_table(add_df.groupby("canonical_descriptor").size().reset_index(name="n").sort_values("n", ascending=False), "19_descriptor_synonym_top_additions")


# ----------------------------------------------------------------------------
# Final report rendering
# ----------------------------------------------------------------------------

def render_report() -> None:
    md = ["# Comprehensive EDA Report — Perfumery ML Project",
          "",
          "Generated by `eda/run_eda.py` on 2026-05-05.",
          "",
          "All artefacts live under `eda/figures/` and `eda/tables/`.",
          "",
          "## Table of contents",
          ""]
    for i, sec in enumerate(REPORT_SECTIONS, 1):
        anchor = sec.title.lower().replace(" ", "-").replace(",", "").replace(":", "").replace("(", "").replace(")", "").replace("/", "")
        md.append(f"{i}. [{sec.title}](#{anchor})")
    md.append("")

    for sec in REPORT_SECTIONS:
        md.append(f"## {sec.title}")
        md.append("")
        md.extend(sec.body)
        md.append("")

    REPORT_PATH.write_text("\n".join(md), encoding="utf-8")
    print(f"\nReport written: {REPORT_PATH}")


# ----------------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------------

def main() -> int:
    print("=== loading workbooks ===")
    data = load_workbooks()
    canon = section_1_integrity(data)
    section_2_catalog(canon)
    section_3_training(canon)
    section_4_text(canon)
    section_567_accord_recipes(canon)
    section_8_notes(canon)
    section_9_cross_source(canon)
    section_10_perfumes(canon)
    section_11_reference_quality(canon)
    section_12_bigrams(canon)
    section_13_avoid(canon)
    section_14_strat(canon)
    section_15_edges(canon)
    section_16_feedback(canon)
    section_17_note_accord_usage(canon)
    section_18_layer_reality_check(canon)
    section_19_synonyms(canon)
    render_report()
    return 0


if __name__ == "__main__":
    sys.exit(main())
