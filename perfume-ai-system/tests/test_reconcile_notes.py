"""Note-name reconciliation (Rule 10): the reconciler is deterministic, only applies unambiguous
matches, never maps a material onto a different one with a different safety outcome, and the build
refuses an alias that points outside dataset2."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "data"))

import build_datasets as bd  # noqa: E402
import reconcile_notes as rn  # noqa: E402


@pytest.fixture(scope="module")
def frames():
    notes = pd.read_csv(rn.NOTES_CSV, dtype=str, keep_default_na=False)
    accords = pd.read_csv(rn.ACCORDS_CSV, dtype=str, keep_default_na=False)
    return notes, accords


@pytest.fixture(scope="module")
def table(frames):
    notes, accords = frames
    return rn.reconcile(notes, accords)


@pytest.fixture(scope="module")
def aliases():
    return pd.read_csv(rn.ALIASES_CSV, dtype=str, keep_default_na=False)


def _row(table, name):
    sub = table[table["Dataset3_Name"] == name]
    assert len(sub) == 1, f"{name!r} not in reconciliation table"
    return sub.iloc[0]


# ----------------------------------------------------------------------------
# normalisation
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("a,b", [
    ("Frankincense CO₂", "Frankincense CO2"),          # unicode subscript
    ("Ylang-Ylang Extra", "Ylang Ylang Extra"),        # hyphen vs space
    ("Aldehyde C-12 Lauric", "Aldehyde C12 Lauric"),   # hyphen next to a digit
    ("IsoButyl Quinoline", "Isobutyl Quinoline"),      # casing
    ("  Lemon  Oil ", "lemon oil"),                    # whitespace
])
def test_key_equates_spelling_variants(a, b):
    assert rn.key(a) == rn.key(b)


def test_core_strips_grade_but_not_plant_part():
    assert rn.core("Myrrh Resinoid") == "myrrh"
    assert rn.core("Cade Oil (Low)") == "cade"
    assert rn.core("Cinnamon Bark Oil") == "cinnamon bark"     # bark != leaf: never stripped


# ----------------------------------------------------------------------------
# the table
# ----------------------------------------------------------------------------

def test_deterministic(frames):
    notes, accords = frames
    a, b = rn.reconcile(notes, accords), rn.reconcile(notes, accords)
    pd.testing.assert_frame_equal(a, b)


def test_every_auto_row_is_unambiguous_and_points_into_dataset2(table, frames):
    notes, _ = frames
    auto = table[table["Tier"] == "AUTO"]
    assert len(auto) > 0
    assert auto["Dataset2_Name"].isin(set(notes["Note_Name"])).all()
    assert (auto["Confidence"].astype(float) >= rn.AUTO_MIN).all()
    assert (auto["Apply"] == "Yes").all()
    assert (table.loc[table["Tier"] != "AUTO", "Apply"] == "No").all()


@pytest.mark.parametrize("d3,d2,rule", [
    ("Frankincense CO₂", "Frankincense CO2", "exact_normalized"),
    ("Pepper Black", "Black Pepper", "word_order"),
    ("Guaiac Wood", "Guaiacwood", "spacing_variant"),
    ("Cade Oil (Low)", "Cade Oil", "dosage_qualifier"),
    ("Iris", "Iris (Orris)", "parenthetical_qualifier"),
    ("Benzaldehyde", "Almond", "chemical_name"),            # dataset2 Almond IS benzaldehyde 100-52-7
    ("Peppermint Oil", "Mint Oil", "reference_cas"),        # 8006-90-4 confirmed on the dataset2 row
    ("Geranium Oil", "Geranium", "grade_suffix"),
    ("Patchouli Absolute", "Patchouli Oil", "grade_suffix"),  # Patchouli & Patchouli Oil share 8014-09-3
])
def test_auto_matches(table, d3, d2, rule):
    r = _row(table, d3)
    assert (r["Tier"], r["Dataset2_Name"], r["Rule"]) == ("AUTO", d2, rule)


def test_cinnamon_bark_is_never_mapped_to_leaf(table, frames):
    """Bark oil is ~70 % cinnamic aldehyde (cap 0.3 %); leaf oil is eugenol-rich (cap 2 %). Since 2026-09-18 a
    'Cinnamon Bark Oil' row exists (note_additions.csv) so the name resolves exactly and leaves the unmatched table;
    the guard itself is checked by hiding that row: the reconciler must then NOT offer the leaf oil."""
    notes, accords = frames
    assert "Cinnamon Bark Oil" not in set(table["Dataset3_Name"])
    t2 = rn.reconcile(notes[notes["Note_Name"] != "Cinnamon Bark Oil"], accords)
    for name in ("Cinnamon Bark Oil", "Cinnamon Bark"):
        r = _row(t2, name)
        assert r["Apply"] == "No" and r["Dataset2_Name"] != "Cinnamon Leaf Oil"


def test_natural_grade_does_not_auto_collapse_onto_a_molecule_standin(table, frames):
    """dataset2 'Vanilla' is vanillin (121-33-5) — 'Vanilla Absolute' must not be auto-mapped onto it. A real
    'Vanilla Absolute' row now exists, so the name resolves; hide it and the guard must still hold."""
    notes, accords = frames
    assert "Vanilla Absolute" not in set(table["Dataset3_Name"])
    t2 = rn.reconcile(notes[notes["Note_Name"] != "Vanilla Absolute"], accords)
    r2 = _row(t2, "Vanilla Absolute")
    assert r2["Tier"] == "REVIEW" and "stand-in" in r2["Reason"]


def test_ambiguous_grades_go_to_review(table):
    r = _row(table, "Myrrh Absolute")           # Myrrh / Oil / Resin / Resinoid carry two different CAS
    assert r["Tier"] == "REVIEW"
    assert "Myrrh Oil" in r["Candidates"]


def test_weak_string_similarity_is_not_offered(table):
    r = _row(table, "Milk Lactone")             # 0.80 similar to 'Maple Lactone' — a different molecule
    assert r["Tier"] == "NO_MATCH" and r["Dataset2_Name"] == ""


# ----------------------------------------------------------------------------
# the alias file and its application at build time
# ----------------------------------------------------------------------------

def test_alias_file_matches_current_datasets(aliases, table):
    auto_rows = aliases[(aliases["Decided_By"] == "auto") & (aliases["Apply"] == "Yes")]
    assert (auto_rows["Tier"] == "AUTO").all()
    assert set(aliases["Dataset3_Name"]) >= set(table["Dataset3_Name"])


def test_human_decisions_survive_regeneration(tmp_path, table):
    existing = table.copy()
    row = existing.index[existing["Tier"] == "REVIEW"][0]
    existing.loc[row, ["Apply", "Decided_By", "Note"]] = ["Yes", "human", "confirmed by perfumer"]
    path = tmp_path / "aliases.csv"
    existing.to_csv(path, index=False, encoding="utf-8")
    merged = rn.merge_with_existing(table, path)
    kept = merged[merged["Dataset3_Name"] == existing.loc[row, "Dataset3_Name"]].iloc[0]
    assert (kept["Apply"], kept["Decided_By"], kept["Note"]) == ("Yes", "human", "confirmed by perfumer")
    assert len(merged) == len(table)


def test_apply_note_aliases_renames_and_reids(monkeypatch, tmp_path):
    notes = pd.DataFrame({"Note_Name": ["Black Pepper", "Cade Oil"], "Note_ID": ["NOTE-0053", "NOTE-0075"]})
    accords = pd.DataFrame({"Note_Name": ["Pepper Black", "Cade Oil (Low)", "Rose"],
                            "Note_ID": ["NOTE-0537", "NOTE-0583", "NOTE-0340"]})
    al = pd.DataFrame({"Dataset3_Name": ["Pepper Black", "Cade Oil (Low)"],
                       "Dataset2_Name": ["Black Pepper", "Cade Oil"], "Apply": ["Yes", "Yes"]})
    path = tmp_path / "aliases.csv"
    al.to_csv(path, index=False)
    monkeypatch.setattr(bd, "ALIASES", path)
    out = bd.apply_note_aliases(accords, notes)
    assert list(out["Note_Name"]) == ["Black Pepper", "Cade Oil", "Rose"]
    assert list(out["Note_ID"]) == ["NOTE-0053", "NOTE-0075", "NOTE-0340"]
    assert list(out["Source_Note_Name"]) == ["Pepper Black", "Cade Oil (Low)", "Rose"]
    assert list(out["Source_Note_ID"]) == ["NOTE-0537", "NOTE-0583", "NOTE-0340"]


def test_apply_note_aliases_refuses_unknown_target(monkeypatch, tmp_path):
    notes = pd.DataFrame({"Note_Name": ["Black Pepper"], "Note_ID": ["NOTE-0053"]})
    accords = pd.DataFrame({"Note_Name": ["Pepper Black"], "Note_ID": ["NOTE-0537"]})
    al = pd.DataFrame({"Dataset3_Name": ["Pepper Black"], "Dataset2_Name": ["Pepper, Black"], "Apply": ["Yes"]})
    path = tmp_path / "aliases.csv"
    al.to_csv(path, index=False)
    monkeypatch.setattr(bd, "ALIASES", path)
    with pytest.raises(ValueError, match="not in dataset2"):
        bd.apply_note_aliases(accords, notes)


def test_dataset3_on_disk_reflects_the_alias_file(frames, aliases):
    notes, accords = frames
    applied = aliases[aliases["Apply"] == "Yes"]
    renamed = accords[accords["Source_Note_Name"] != accords["Note_Name"]]
    edits = pd.read_csv(ROOT / "data" / "accord_edits.csv", dtype=str, keep_default_na=False)
    real_renames = set(applied.loc[applied["Dataset3_Name"] != applied["Dataset2_Name"], "Dataset3_Name"])   # self-maps are not renames
    assert set(renamed["Source_Note_Name"]) == real_renames | set(edits["Note_Name_From"])
    assert renamed["Note_Name"].isin(set(notes["Note_Name"])).all()
    assert renamed["Note_ID"].isin(set(notes["Note_ID"])).all()
