"""Task 2 — formula builder + Carles accord study.

Golden case: Jean Carles' own chypre (pp.6-7) must come out as 20/5 | 15/5 | 30/20/5. Deliberate breaches: an
unplaceable note, a conflicting dataset2 entry, an empty layer, a single-layer accord — each must be FLAGGED, never
crash, never be dropped silently. Same input (in any row order) -> identical formula. No LLM anywhere in Zone B."""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest

import load_data as ld
from zone_b_chemistry import accord_study as st
from zone_b_chemistry import formula_builder as fb

ROOT = Path(__file__).resolve().parents[1]


# ----------------------------------------------------------------------------
# synthetic fixtures (small, fully controlled)
# ----------------------------------------------------------------------------

def notes_table(rows):
    """rows: (Note_ID, Note_Name, CAS, Volatility_Class, Odor_Strength)"""
    df = pd.DataFrame(rows, columns=["Note_ID", "Note_Name", "CAS", "Volatility_Class", "Odor_Strength"])
    df["CAS_Valid"] = df["CAS"].map(ld.is_valid_cas)
    df["Odor_Threshold_mg_L"] = ""
    return df


def accord_table(rows, accord_id="ACC-T", accord_name="Test"):
    """rows: (Note_Name, Note_Role, Layer, Importance_Weight, Typical_Presence, Blend_Compatibility)"""
    df = pd.DataFrame(rows, columns=["Note_Name", "Note_Role", "Layer", "Importance_Weight", "Typical_Presence", "Blend_Compatibility"])
    df.insert(0, "Accord_ID", accord_id)
    df.insert(1, "Accord_Name", accord_name)
    df["Note_ID"] = ["N-" + str(i) for i in range(len(df))]
    df["Stability_Class"] = "High"
    return df


CARLES_NOTES = notes_table([
    ("C1", "Sweet Orange", "8008-57-9", "Top", "Medium"),
    ("C2", "Bergamot", "8007-75-8", "Top", "Medium"),
    ("C3", "Rose Abs.", "8007-01-0", "Heart", "Medium"),
    ("C4", "Civet Abs. 10% solution", "", "Heart", "Medium"),
    ("C5", "Oakmoss Abs.", "90028-68-5", "Base", "Medium"),
    ("C6", "Ambergris 162B", "", "Base", "Medium"),
    ("C7", "Musk Ketone", "81-14-1", "Base", "Medium"),
])
# Importance_Weight x Typical_Presence reproduces Carles' parts: 4:1 (top), 3:1 (heart), 6:4:1 (base)
CARLES_ACCORD = accord_table([
    ("Sweet Orange", "Driver", "Top", 4, 1.0, 1.0), ("Bergamot", "Modifier", "Top", 1, 1.0, 1.0),
    ("Rose Abs.", "Support", "Heart", 3, 1.0, 1.0), ("Civet Abs. 10% solution", "Modifier", "Heart", 1, 1.0, 1.0),
    ("Oakmoss Abs.", "Driver", "Base", 5, 0.6, 1.0), ("Ambergris 162B", "Driver", "Base", 4, 0.5, 1.0),
    ("Musk Ketone", "Modifier", "Base", 1, 0.5, 1.0),
], "ACC-CHYPRE", "Carles chypre")
CARLES_EXPECTED = {"Sweet Orange": 20.0, "Bergamot": 5.0, "Rose Abs.": 15.0, "Civet Abs. 10% solution": 5.0,
                   "Oakmoss Abs.": 30.0, "Ambergris 162B": 20.0, "Musk Ketone": 5.0}


@pytest.fixture(scope="module")
def data() -> ld.Data:
    return ld.load_all()


def pct(result: fb.FormulaResult) -> dict[str, float]:
    return dict(zip(result.formula["Note_Name"], result.formula["Pct"]))


# ----------------------------------------------------------------------------
# golden case
# ----------------------------------------------------------------------------

def test_carles_chypre_is_reproduced_exactly():
    r = fb.build_formula(CARLES_ACCORD, CARLES_NOTES)
    assert r.complete and r.total_pct == 100.0
    assert pct(r) == CARLES_EXPECTED
    assert r.layers.set_index("Layer")["Achieved_Pct"].to_dict() == {"Top": 25.0, "Heart": 20.0, "Base": 55.0}


def test_formula_from_parts_matches_carles_notation():
    df = st.carles_chypre().to_percent()
    assert dict(zip(df["Note_Name"], df["Pct"])) == CARLES_EXPECTED
    assert df["Pct"].sum() == 100.0


# ----------------------------------------------------------------------------
# determinism and purity
# ----------------------------------------------------------------------------

def test_same_input_any_order_same_formula(data):
    rows, _ = fb.accord_rows_for(data.accords, ["Fougere"])
    a = fb.build_formula(rows, data.notes)
    b = fb.build_formula(rows.sample(frac=1, random_state=3), data.notes.sample(frac=1, random_state=5))
    pd.testing.assert_frame_equal(a.formula, b.formula)
    assert [str(f) for f in a.flags] == [str(f) for f in b.flags]


def test_inputs_are_not_mutated():
    acc, notes = CARLES_ACCORD.copy(), CARLES_NOTES.copy()
    fb.build_formula(acc, notes)
    pd.testing.assert_frame_equal(acc, CARLES_ACCORD)
    pd.testing.assert_frame_equal(notes, CARLES_NOTES)


def test_zone_b_imports_no_llm():
    for name in ("formula_builder.py", "accord_study.py"):
        src = (ROOT / "zone_b_chemistry" / name).read_text(encoding="utf-8")
        assert not re.search(r"\b(anthropic|openai|zone_a_llm|requests|urllib)\b", src), name


# ----------------------------------------------------------------------------
# the deliberate breaches — flag, never crash, never drop silently
# ----------------------------------------------------------------------------

def test_unplaceable_note_is_flagged_and_listed_not_dropped():
    acc = pd.concat([CARLES_ACCORD, accord_table([("Unicorn Tears", "Support", "Heart", 3, 1.0, 1.0)], "ACC-CHYPRE", "Carles chypre")],
                    ignore_index=True)
    r = fb.build_formula(acc, CARLES_NOTES)
    assert not r.complete
    errs = [f for f in r.flags if f.code == "UNPLACEABLE"]
    assert len(errs) == 1 and errs[0].note == "Unicorn Tears" and errs[0].severity == "ERROR"
    assert list(r.unplaced["Note_Name"]) == ["Unicorn Tears"] and "not in dataset2" in r.unplaced["Reason"].iloc[0]
    assert r.total_pct == 100.0 and len(r.formula) == 7           # the rest is still a complete formula
    assert not r.trace.loc[r.trace["Note_Name"] == "Unicorn Tears", "Placed"].iloc[0]


def test_invalid_volatility_class_is_unplaceable():
    notes = pd.concat([CARLES_NOTES, notes_table([("X", "Mystery", "", "Middle", "Medium")])], ignore_index=True)
    acc = pd.concat([CARLES_ACCORD, accord_table([("Mystery", "Support", "Heart", 3, 1.0, 1.0)], "ACC-CHYPRE", "Carles chypre")], ignore_index=True)
    r = fb.build_formula(acc, notes)
    assert any(f.code == "UNPLACEABLE" and "Volatility_Class" in f.message for f in r.flags)
    assert r.total_pct == 100.0


def test_all_notes_unplaceable_gives_empty_formula_with_errors():
    acc = accord_table([("Nothing", "Driver", "Base", 5, 1.0, 1.0)])
    r = fb.build_formula(acc, CARLES_NOTES)
    assert len(r.formula) == 0 and r.total_pct == 0.0 and len(r.errors()) == 1 and len(r.unplaced) == 1


def test_conflicting_dataset2_rows_pick_valid_cas_and_flag():
    notes = pd.concat([CARLES_NOTES, notes_table([("C7", "Musk Ketone", "81-14-2", "Heart/Base", "Medium")])], ignore_index=True)
    r = fb.build_formula(CARLES_ACCORD, notes)
    row = r.formula[r.formula["Note_Name"] == "Musk Ketone"].iloc[0]
    assert row["CAS"] == "81-14-1" and row["Layer"] == "Base"            # checksum-valid row wins
    assert any(f.code == "NOTE_CONFLICT" and f.note == "Musk Ketone" for f in r.flags)


def test_two_layer_note_follows_accord_layer_when_allowed_else_neediest():
    notes = notes_table([("A", "Alpha", "", "Base", "Medium"), ("B", "Beta", "", "Top/Heart", "Medium"), ("G", "Gamma", "", "Top", "Medium")])
    acc = accord_table([("Alpha", "Driver", "Base", 5, 1.0, 1.0), ("Beta", "Support", "Heart", 3, 1.0, 1.0), ("Gamma", "Support", "Top", 3, 1.0, 1.0)])
    r = fb.build_formula(acc, notes)
    assert r.formula.set_index("Note_Name").loc["Beta", "Layer"] == "Heart"
    acc2 = accord_table([("Alpha", "Driver", "Base", 5, 1.0, 1.0), ("Beta", "Support", "Base", 3, 1.0, 1.0), ("Gamma", "Support", "Top", 3, 1.0, 1.0)])
    r2 = fb.build_formula(acc2, notes)
    assert r2.formula.set_index("Note_Name").loc["Beta", "Layer"] == "Heart"   # Base not allowed; Heart is empty -> neediest
    assert "furthest below its target" in r2.trace.set_index("Note_Name").loc["Beta", "Placement_Reason"]


def test_dataset2_class_overrides_accord_layer_and_says_so():
    acc = CARLES_ACCORD.copy()
    acc.loc[acc["Note_Name"] == "Rose Abs.", "Layer"] = "Top"
    r = fb.build_formula(acc, CARLES_NOTES)
    assert r.formula.set_index("Note_Name").loc["Rose Abs.", "Layer"] == "Heart"
    assert any(f.code == "LAYER_OVERRIDDEN" and f.note == "Rose Abs." for f in r.flags)


def test_empty_layer_is_redistributed_heart_capped_and_flagged():
    acc = CARLES_ACCORD[CARLES_ACCORD["Layer"] != "Top"]                   # no top notes at all
    r = fb.build_formula(acc, CARLES_NOTES)
    L = r.layers.set_index("Layer")["Applied_Pct"]
    assert L["Top"] == 0.0 and L["Heart"] == 25.0 and L["Base"] == 75.0    # 20 + 25*20/75 = 26.7 -> capped at 25, excess to Base
    codes = {f.code for f in r.flags}
    assert {"EMPTY_LAYER", "LAYER_OUT_OF_RANGE"} <= codes                  # Base 75 > 65 is reported, not hidden
    assert r.total_pct == 100.0


def test_no_base_notes_is_a_warning_not_a_crash():
    acc = CARLES_ACCORD[CARLES_ACCORD["Layer"] != "Base"]
    r = fb.build_formula(acc, CARLES_NOTES)
    assert r.total_pct == 100.0
    assert any(f.code == "LAYER_OUT_OF_RANGE" and "no Base" in f.message for f in r.flags)
    assert r.layers.set_index("Layer")["Applied_Pct"]["Heart"] <= 25.0


def test_single_layer_accord_is_flagged_for_shape():
    acc = CARLES_ACCORD[CARLES_ACCORD["Layer"] == "Base"]
    r = fb.build_formula(acc, CARLES_NOTES)
    assert any(f.code == "ACCORD_SINGLE_LAYER" for f in r.flags)


# ----------------------------------------------------------------------------
# weighting rules
# ----------------------------------------------------------------------------

def test_driver_gets_more_than_support_more_than_modifier():
    p = pct(fb.build_formula(CARLES_ACCORD, CARLES_NOTES))
    assert p["Oakmoss Abs."] > p["Ambergris 162B"] > p["Musk Ketone"]
    assert p["Rose Abs."] > p["Civet Abs. 10% solution"]


def test_strong_material_is_damped_to_half():
    notes = CARLES_NOTES.copy()
    notes.loc[notes["Note_Name"] == "Ambergris 162B", "Odor_Strength"] = "Strong"
    r = fb.build_formula(CARLES_ACCORD, notes)
    p = pct(r)
    # oakmoss 3.0 : ambergris 2.0*0.5 : musk 0.5 -> 55 * (3, 1, 0.5)/4.5
    assert p["Ambergris 162B"] == pytest.approx(55 * 1.0 / 4.5, abs=1e-3)
    assert any(f.code == "ODOR_DAMPED" and f.note == "Ambergris 162B" for f in r.flags)
    assert r.total_pct == 100.0


def test_low_blend_compatibility_scales_the_share():
    acc = CARLES_ACCORD.copy()
    acc.loc[acc["Note_Name"] == "Bergamot", "Blend_Compatibility"] = 0.5
    r = fb.build_formula(acc, CARLES_NOTES)
    assert pct(r)["Bergamot"] == pytest.approx(25 * 0.5 / 4.5, abs=1e-3)
    assert any(f.code == "LOW_COMPATIBILITY" for f in r.flags)


def test_role_weight_mismatch_is_reported_but_weight_is_used():
    acc = CARLES_ACCORD.copy()
    acc.loc[acc["Note_Name"] == "Bergamot", "Note_Role"] = "Driver"          # a 'Driver' with weight 1
    r = fb.build_formula(acc, CARLES_NOTES)
    assert any(f.code == "ROLE_WEIGHT_MISMATCH" for f in r.flags)
    assert pct(r) == CARLES_EXPECTED


# ----------------------------------------------------------------------------
# several accords, duplicates
# ----------------------------------------------------------------------------

def test_same_note_in_two_accords_is_one_material_with_summed_weight():
    second = accord_table([("Bergamot", "Driver", "Top", 4, 1.0, 1.0)], "ACC-2", "Citrus lift")
    r = fb.build_formula(pd.concat([CARLES_ACCORD, second], ignore_index=True), CARLES_NOTES)
    assert (r.formula["Note_Name"] == "Bergamot").sum() == 1
    p = pct(r)
    assert p["Bergamot"] == pytest.approx(25 * 5 / 9, abs=1e-3) and p["Sweet Orange"] == pytest.approx(25 * 4 / 9, abs=1e-3)
    assert r.formula.set_index("Note_Name").loc["Bergamot", "Accords"] == "Carles chypre; Citrus lift"


def test_accord_weights_are_respected():
    second = accord_table([("Bergamot", "Driver", "Top", 4, 1.0, 1.0)], "ACC-2", "Citrus lift")
    r = fb.build_formula(pd.concat([CARLES_ACCORD, second], ignore_index=True), CARLES_NOTES, accord_weights={"ACC-2": 0.25})
    assert pct(r)["Bergamot"] == pytest.approx(25 * 2 / 6, abs=1e-3)      # 1 + 4*0.25 = 2 of 6 top parts


def test_exact_duplicate_rows_are_ignored_and_variants_flagged():
    dup = pd.concat([CARLES_ACCORD, CARLES_ACCORD.iloc[[0]]], ignore_index=True)     # exact repeat of Sweet Orange
    r = fb.build_formula(dup, CARLES_NOTES)
    assert pct(r) == CARLES_EXPECTED and any(f.code == "DUPLICATE_ROW" for f in r.flags)
    var = pd.concat([CARLES_ACCORD, accord_table([("Bergamot", "Support", "Top", 3, 1.0, 1.0)], "ACC-CHYPRE", "Carles chypre")], ignore_index=True)
    r2 = fb.build_formula(var, CARLES_NOTES)
    assert any(f.code == "DUPLICATE_NOTE_IN_ACCORD" and f.severity == "WARNING" for f in r2.flags)
    assert pct(r2)["Bergamot"] == pytest.approx(25 * 3 / 7, abs=1e-3)    # the stronger statement (w3) is kept, not summed


def test_unknown_accord_name_is_flagged(data):
    rows, flags = fb.accord_rows_for(data.accords, ["Fougere", "Unicorn Dust"])
    assert len(rows) > 0 and [f.code for f in flags] == ["UNKNOWN_ACCORD"] and flags[0].accord == "Unicorn Dust"


# ----------------------------------------------------------------------------
# real data
# ----------------------------------------------------------------------------

def test_every_real_accord_builds_to_100_or_is_fully_unplaceable(data):
    for aid, g in data.accords.groupby("Accord_ID"):
        r = fb.build_formula(g, data.notes)
        if len(r.formula):
            assert round(r.total_pct, 3) == 100.0, aid
            L = r.layers.set_index("Layer")["Applied_Pct"]
            assert L["Heart"] <= 25.0 + 1e-9, aid                       # Carles' modifier cap always holds
        else:
            assert len(r.errors()) >= 1 and len(r.unplaced) == len(r.trace), aid
        assert len(r.trace) >= len(r.formula)


def test_real_fougere_has_carles_shape(data):
    rows, _ = fb.accord_rows_for(data.accords, ["Fougere"])
    r = fb.build_formula(rows, data.notes)
    L = r.layers.set_index("Layer")["Achieved_Pct"]
    assert r.complete and L["Base"] > L["Top"] > L["Heart"] - 1e-6 and abs(L.sum() - 100) < 1e-6
    names = set(r.formula["Note_Name"].str.lower())
    assert any("lavand" in n or "lavender" in n for n in names) and "coumarin" in names and any("oakmoss" in n for n in names)


# ----------------------------------------------------------------------------
# Carles accord study
# ----------------------------------------------------------------------------

def test_base_series_is_carles_five_ratios():
    s = st.base_series("Oakmoss Abs.", "Ambergris 162B")
    assert [tuple(p for _, p in a.base) for a in s] == [(9, 1), (8, 2), (7, 3), (6, 4), (5, 5)]


def test_study_variant_4_is_carles_chypre():
    df = st.study("Oakmoss Abs.", "Ambergris 162B", third=("Musk Ketone", 1),
                  modifiers=[("Rose Abs.", 3), ("Civet Abs. 10% solution", 1)], top=[("Sweet Orange", 4), ("Bergamot", 1)])
    v4 = df[df["Variant"] == 4]
    assert dict(zip(v4["Note_Name"], v4["Pct"])) == CARLES_EXPECTED
    assert df.groupby("Variant")["Pct"].sum().round(6).eq(100).all()


def test_substitution_series_swaps_one_material_keeping_parts():
    out = st.substitution_series(st.carles_chypre(), "Heart", "Rose Abs.", ["Rose Abs.", "Jasmine Abs.", "Orange Flower Abs."])
    assert [a.heart[0][0] for a in out] == ["Jasmine Abs.", "Orange Flower Abs."] and all(a.heart[0][1] == 3.0 for a in out)
    with pytest.raises(ValueError):
        st.substitution_series(st.carles_chypre(), "Top", "Rose Abs.", ["x"])


def test_student_accords_load_from_reference_table():
    t = pd.read_csv(ROOT / "data" / "reference" / "carles_student_accords.csv", dtype=str, keep_default_na=False)
    a = st.from_reference_table(t, "fc3_05", variant=2)
    assert a.base == (("Oak Moss Abs.", 7.0), ("Patchouli", 3.0), ("Musk Ketone", 1.0))
    assert a.to_percent()["Pct"].sum() == 100.0
