"""CAS audit (Step 2): a checksum-failing CAS is corrected only when two independent sources agree,
pasted-on-unrelated-notes CAS never count as evidence, and the build refuses a stale or invalid correction.
Runs offline from the PubChem cache written by `python data/verify_cas.py`."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "data"))

import build_datasets as bd  # noqa: E402
import load_data as ld  # noqa: E402
import verify_cas as vc  # noqa: E402


@pytest.fixture(scope="module")
def table():
    return vc.audit(offline=True)


@pytest.fixture(scope="module")
def corrections():
    return pd.read_csv(vc.OUT_CSV, dtype=str, keep_default_na=False)


def _row(table, note, bad):
    sub = table[(table["Note_Name"] == note) & (table["Bad_CAS"] == bad)]
    assert len(sub) == 1, f"{note} / {bad} not in audit table"
    return sub.iloc[0]


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------

def test_typo_neighbours_are_valid_and_one_edit_away():
    n = vc.typo_neighbours("9000-64-2")
    assert "9000-64-0" in n                      # Tolu balsam: check digit slipped
    assert all(ld.is_valid_cas(c) for c in n)
    assert "9000-64-2" not in n


def test_shared_cas_detector_separates_paste_errors_from_variants():
    notes = pd.read_csv(vc.NOTES_CSV, dtype=str, keep_default_na=False).drop_duplicates()
    notes["valid"] = notes["CAS"].map(ld.is_valid_cas)
    conflicts = vc.shared_cas_conflicts(notes)
    assert "54464-57-2" in conflicts             # Iso E Super's CAS on Timber Silk / Safraleine / Norlimbanol
    assert "8000-27-9" in conflicts              # cedarwood's CAS on Cade Oil / Juniper Tar
    assert "33704-61-9" in conflicts             # Cashmeran's CAS on Habanolide
    assert "8007-75-8" not in conflicts          # Bergamot / Bergamot Oil / Bergamot Oil FCF — grade variants
    assert "542-46-1" not in conflicts           # Civetone / Civettone — spelling variant


# ----------------------------------------------------------------------------
# decisions
# ----------------------------------------------------------------------------

def test_every_fix_is_checksum_valid_and_doubly_sourced(table):
    fix = table[table["Action"] == "FIX"]
    assert len(fix) > 0
    assert fix["Corrected_CAS"].map(ld.is_valid_cas).all()
    for r in fix.itertuples(index=False):
        tags = {t for t in r.Evidence.split(",") if t and not t.endswith("?")}
        origins = {"official" if t.startswith("project:ifra") else t.split(":")[0] for t in tags}
        assert len(origins) >= 2, f"{r.Note_Name}: {r.Evidence}"
    assert (table.loc[table["Action"] == "FLAG", "Corrected_CAS"] == "").all()


@pytest.mark.parametrize("note,bad,fixed", [
    ("Norlimbanol", "104979-41-3", "70788-30-6"),   # IFRA-derived table + PubChem + same note
    ("Safraleine", "102353-43-9", "54440-17-4"),    # safety_caps + PubChem
    ("Styrax", "9000-19-6", "8046-19-3"),           # official IFRA table + same note + sibling
    ("Tolu Balsam", "9000-64-2", "9000-64-0"),      # one-digit typo of the note's own valid CAS
    ("Vertofix", "55213-82-4", "32388-55-9"),       # PubChem + same note
])
def test_fixes(table, note, bad, fixed):
    r = _row(table, note, bad)
    assert (r["Action"], r["Corrected_CAS"]) == ("FIX", fixed)


def test_identical_paste_on_two_notes_is_not_corroboration(table):
    for note in ("Champaca Absolute", "Gardenia Absolute"):
        r = _row(table, note, "8006-71-5")
        assert r["Action"] == "FLAG" and r["Corrected_CAS"] == "" and r["Recommended_CAS"] == ""


def test_check_digit_repair_needs_distinct_digits_on_same_material(table):
    r = _row(table, "Palo Santo", "959130-05-6")      # sibling row carries 959130-05-5 -> body corroborated
    assert r["Action"] == "FLAG" and r["Recommended_CAS"] == "959130-05-3"
    assert "checkdigit" in r["Evidence"]


def test_suspect_same_note_cas_is_never_recommended(table):
    r = _row(table, "Ambermax", "71837-65-9")       # its only candidate, 68155-66-8, is pasted on Veramoss too
    assert r["Action"] == "FLAG" and r["Recommended_CAS"] == ""
    assert "suspect" in r["Detail"]


def test_generic_natural_names_are_not_sent_to_pubchem(table):
    r = _row(table, "Lotus", "8024-92-6")            # PubChem 'Lotus' is an unrelated compound
    assert "pubchem" not in r["Evidence"]


# ----------------------------------------------------------------------------
# build-time application
# ----------------------------------------------------------------------------

def test_apply_cas_corrections_replaces_and_keeps_source(monkeypatch, tmp_path):
    notes = pd.DataFrame({"Note_ID": ["NOTE-0395", "NOTE-0001"], "Note_Name": ["Tolu Balsam", "Rose"],
                          "CAS": ["9000-64-2", "8007-01-0"]})
    fx = pd.DataFrame({"Note_ID": ["NOTE-0395"], "Note_Name": ["Tolu Balsam"], "Bad_CAS": ["9000-64-2"],
                       "Corrected_CAS": ["9000-64-0"], "Apply": ["Yes"]})
    path = tmp_path / "fx.csv"
    fx.to_csv(path, index=False)
    monkeypatch.setattr(bd, "CAS_FIXES", path)
    out = bd.apply_cas_corrections(notes)
    assert list(out["CAS"]) == ["9000-64-0", "8007-01-0"]
    assert list(out["Source_CAS"]) == ["9000-64-2", "8007-01-0"]


@pytest.mark.parametrize("corrected,bad,match", [
    ("9000-64-2", "9000-64-2", "checksum"),        # correction itself fails the checksum
    ("9000-64-0", "9000-64-9", "stale"),           # no such row any more
])
def test_apply_cas_corrections_refuses_bad_or_stale_rows(monkeypatch, tmp_path, corrected, bad, match):
    notes = pd.DataFrame({"Note_ID": ["NOTE-0395"], "Note_Name": ["Tolu Balsam"], "CAS": ["9000-64-2"]})
    fx = pd.DataFrame({"Note_ID": ["NOTE-0395"], "Note_Name": ["Tolu Balsam"], "Bad_CAS": [bad],
                       "Corrected_CAS": [corrected], "Apply": ["Yes"]})
    path = tmp_path / "fx.csv"
    fx.to_csv(path, index=False)
    monkeypatch.setattr(bd, "CAS_FIXES", path)
    with pytest.raises(ValueError, match=match):
        bd.apply_cas_corrections(notes)


def test_dataset2_on_disk_reflects_the_corrections_file(corrections):
    notes = pd.read_csv(vc.NOTES_CSV, dtype=str, keep_default_na=False)
    applied = corrections[corrections["Apply"] == "Yes"]
    for r in applied.itertuples(index=False):
        rows = notes[(notes["Note_ID"] == r.Note_ID) & (notes["Source_CAS"] == r.Bad_CAS)]
        assert len(rows) >= 1 and (rows["CAS"] == r.Corrected_CAS).all(), r.Note_Name
    changed = notes[notes["Source_CAS"] != notes["CAS"]]
    assert set(zip(changed["Note_ID"], changed["Source_CAS"])) == set(zip(applied["Note_ID"], applied["Bad_CAS"]))
