"""Curtis 1994 / Ohloff 2e integration: stability advisories, book accords, Curtis families, the Lyral CAS fix."""
from __future__ import annotations

import pandas as pd
import pytest

from zone_b_chemistry import book_accords as ba
from zone_b_chemistry import safety_engine as se
from zone_b_chemistry.invention import invent
from zone_b_chemistry.product_formulation import formulate_product
from zone_b_chemistry.stability import assess
import load_data as ld


@pytest.fixture(scope="module")
def data() -> ld.Data:
    return ld.load_all()


def F(*rows):
    return pd.DataFrame(list(rows), columns=["Note_Name", "CAS", "Pct"])


# ---------------------------------------------------------------------------------------------------------------
# stability (Curtis Ch 5-6 monographs, Ch 11-12)
# ---------------------------------------------------------------------------------------------------------------

def test_schiff_base_colour_needs_an_amine_and_a_carbonyl(data):
    both = assess(F(("Citral", "5392-40-5", 2.0), ("Methyl Anthranilate", "134-20-3", 3.0), ("Sandalwood Oil", "8006-87-9", 95.0)), data, water_pct=8.5, alcohol_pct=79.0)
    codes = {f.code for f in both}
    assert "SCHIFF_BASE_COLOUR" in codes and next(f for f in both if f.code == "SCHIFF_BASE_COLOUR").severity == "WARNING"
    only_carbonyl = assess(F(("Citral", "5392-40-5", 2.0), ("Sandalwood Oil", "8006-87-9", 98.0)), data, water_pct=8.5, alcohol_pct=79.0)
    assert "SCHIFF_BASE_COLOUR" not in {f.code for f in only_carbonyl}
    assert "LIGHT_SENSITIVE" in {f.code for f in only_carbonyl}                     # citral darkens in daylight (Curtis p.183)


def test_water_drives_ester_hydrolysis_and_terpene_haze_advisories(data):
    f = F(("Lemon Oil", "8008-56-8", 30.0), ("Linalyl Acetate", "115-95-7", 30.0), ("Sandalwood Oil", "8006-87-9", 40.0))
    dry = assess(f, data, water_pct=5.0, alcohol_pct=85.0)
    assert "ESTER_HYDROLYSIS" not in {x.code for x in dry} and "TERPENE_SOLUBILITY" not in {x.code for x in dry}
    wet = assess(f, data, water_pct=30.0, alcohol_pct=60.0)             # a 67 % alcohol cologne: haze and hydrolysis (Curtis p.526, p.561)
    by = {x.code: x for x in wet}
    assert by["ESTER_HYDROLYSIS"].severity == "WARNING" and "Linalyl Acetate" in by["ESTER_HYDROLYSIS"].materials
    assert by["TERPENE_SOLUBILITY"].severity == "WARNING" and "Lemon Oil" in by["TERPENE_SOLUBILITY"].materials
    mid = assess(f, data, water_pct=12.0, alcohol_pct=78.0)
    assert {x.code: x.severity for x in mid}.get("ESTER_HYDROLYSIS") == "INFO"
    # salicylates / benzoates are not in Curtis' hydrolysis examples and are not flagged
    ok = assess(F(("Benzyl Salicylate", "118-58-1", 50.0), ("Sandalwood Oil", "8006-87-9", 50.0)), data, water_pct=30.0, alcohol_pct=60.0)
    assert "ESTER_HYDROLYSIS" not in {x.code for x in ok}


def test_product_layer_carries_the_stability_advisories(data):
    f = F(("Musk Ketone", "81-14-1", 1.0), ("Eugenol", "97-53-0", 1.0), ("Sandalwood Oil", "8006-87-9", 98.0))
    p = formulate_product(f, data, product_type="Eau de toilette", concentrate_pct=10)
    codes = {x.code for x in p.stability}
    assert {"LIGHT_SENSITIVE", "IRON_SENSITIVE"} <= codes
    assert any("STABILITY" in line for line in p.summary().splitlines())
    p2 = formulate_product(f, data, product_type="Eau de toilette", concentrate_pct=10, uv_absorber=False)
    assert next(x for x in p2.stability if x.code == "LIGHT_SENSITIVE").severity == "WARNING"


def test_stability_never_changes_a_percentage(data):
    f = F(("Citral", "5392-40-5", 2.0), ("Indole", "120-72-9", 0.2), ("Sandalwood Oil", "8006-87-9", 97.8))
    before = f["Pct"].tolist()
    assess(f, data, water_pct=30.0, alcohol_pct=60.0)
    assert f["Pct"].tolist() == before


# ---------------------------------------------------------------------------------------------------------------
# book accords (Curtis floral bases, Ohloff basic accords, Curtis type formulas)
# ---------------------------------------------------------------------------------------------------------------

def test_curtis_bases_resolve_against_the_catalogue(data):
    for base in ("Rose", "Jasmin", "Lily-of-the-Valley", "Carnation", "Orange Blossom", "Violet", "Tuberose"):
        rows, unresolved = ba.curtis_base_rows(base, data)
        assert len(rows) >= 12 and set(rows["Layer"]) <= {"Top", "Heart", "Base"}
        assert len(unresolved) <= 1, (base, unresolved)                 # Rosacene (Rose) is the only material the catalogue lacks
    rose, _ = ba.curtis_base_rows("Rose", data, skeleton=3)
    r = rose.set_index("Note_Name")
    assert r.loc["Geraniol", "Typical_Presence"] == 1.0                   # 37 parts = the largest -> presence 1
    assert r.loc["Citronellol", "Typical_Presence"] == pytest.approx(27 / 37, abs=1e-3)
    assert "Phenylacetic Acid" not in r.index                             # skeleton 3 has none; skeleton 2 has 7 parts of a 10 % solution
    rose2, _ = ba.curtis_base_rows("Rose", data, skeleton=2)
    assert rose2.set_index("Note_Name").loc["Phenylacetic Acid", "Typical_Presence"] == pytest.approx(0.7 / 64, abs=1e-3)   # dilution honoured


def test_ohloff_accords_and_term_matching(data):
    rows, unresolved = ba.ohloff_accord_rows("Rose", data)
    assert rows["Note_Name"].tolist() == ["Phenethyl Alcohol", "Citronellol", "Damascenone"] and rows["Importance_Weight"].tolist() == [5, 3, 3]
    assert not unresolved
    assert ba.match_term("muguet") == ("curtis", "Lily-of-the-Valley") and ba.match_term("fresh peach") == ("ohloff", "Peach")
    assert ba.match_term("woody") is None


def test_curtis_type_formula_expands_its_floral_bases(data):
    rows, unresolved = ba.curtis_formula_rows("Basic Chypre-type perfume", data)
    names = set(rows["Note_Name"])
    assert {"Bergamot Oil FCF", "Sandalwood Oil", "Oakmoss Absolute", "Musk Ketone"} <= names
    assert "Geraniol" in names and "Benzyl Acetate" in names               # from the expanded Rose / Jasmin bases
    assert rows.set_index("Note_Name").loc["Bergamot Oil FCF", "Typical_Presence"] == 1.0
    small, _ = ba.curtis_formula_rows("Basic Chypre-type perfume", data, base_top_n=3)
    assert len(small) < len(rows)


def test_invention_falls_back_to_a_book_accord_for_an_unmapped_term(data):
    inv = invent(["peach"], data, n_variants=1)
    assert any("Ohloff" in a for a in inv.accords) and "peach" not in inv.unmapped_terms
    inv2 = invent(["peach"], data, n_variants=1, book_accords="never")
    assert not inv2.variants and "peach" in inv2.unmapped_terms


def test_invention_rebuilds_without_a_banned_book_material(data):
    # the 1994 muguet base is built on Lyral (HICC), banned in the UK/EU: the inventor drops it, says so, and still delivers
    inv = invent(["muguet"], data, n_variants=1, book_accords="always")
    assert inv.variants and inv.variants[0].removed_banned == ["Lyral"]
    assert inv.variants[0].verdict == "PASS"
    assert "Lyral" not in set(inv.variants[0].formula["Note_Name"])


def test_curtis_family_sketch_is_a_signature(data):
    inv = invent(["citrus"], data, family="eau de cologne", n_variants=1)
    # Neroli is already in the Citrus accord, so the signature adds only what the structure lacks
    assert inv.variants and {"Lavender Oil", "Rosemary Oil", "Thyme Oil", "Benzoin Siam"} <= set(inv.variants[0].added_signature)
    assert "Neroli Oil" in set(inv.variants[0].formula["Note_Name"])
    with pytest.raises(ValueError):
        invent(["citrus"], data, family="no such family", n_variants=1)


def test_lyral_now_carries_the_hicc_cas_and_is_rejected(data):
    lyral = data.notes[data.notes["Note_Name"] == "Lyral"]
    assert len(lyral) and set(lyral["CAS"]) == {"31906-04-4"}
    r = se.check_formula(F(("Lyral", "31906-04-4", 2.0), ("Sandalwood Oil", "8006-87-9", 98.0)), data)
    assert r.verdict == "REJECT" and "Lyral" in set(r.rejections["Note_Name"])


def test_ohloff_usage_levels_agree_with_the_potency_classes(data):
    chk = data.ohloff_potency_check
    assert len(chk) >= 15 and chk["Agrees"].all(), chk[~chk["Agrees"]]


# ---------------------------------------------------------------------------------------------------------------
# Tisserand & Young second-source tables (dermal maxima advisory, Chapter 14 sources)
# ---------------------------------------------------------------------------------------------------------------

def test_tisserand_advisory_reports_but_never_caps(data):
    assert len(data.tisserand_maxima) >= 60 and (data.tisserand_maxima["TY_Max_Pct"] > 0).all()
    r = se.check_formula(F(("Clove Bud Oil", "8000-34-8", 1.5), ("Sandalwood Oil", "8006-87-9", 98.5)), data)
    adv = [x for x in r.flags if x.code == "TY_ADVISORY" and x.note == "Clove Bud Oil"]
    assert adv and adv[0].severity == "WARNING" and "0.5 %" in adv[0].message and "PDF p." in adv[0].source
    assert float(r.formula.set_index("Note_Name").loc["Clove Bud Oil", "Pct"]) == 1.5      # the advisory changed nothing
    r10 = se.check_formula(F(("Clove Bud Oil", "8000-34-8", 1.5), ("Sandalwood Oil", "8006-87-9", 98.5)), data, concentrate_fraction=0.10)
    assert not [x for x in r10.flags if x.code == "TY_ADVISORY" and x.note == "Clove Bud Oil"]   # 0.15 % on skin is under 0.5 %


def test_tisserand_advisory_matches_the_form_of_the_note(data):
    # the Lavandin profile only states a maximum for the ABSOLUTE (0.03 %): it must not judge Lavandin Oil
    r = se.check_formula(F(("Lavandin Oil", "91722-69-9", 5.0), ("Sandalwood Oil", "8006-87-9", 95.0)), data)
    assert not [x for x in r.flags if x.code == "TY_ADVISORY" and x.note == "Lavandin Oil"]
    r2 = se.check_formula(F(("Lavender Absolute", "8000-28-0", 1.0), ("Sandalwood Oil", "8006-87-9", 99.0)), data)
    assert [x for x in r2.flags if x.code == "TY_ADVISORY" and x.note == "Lavender Absolute"]


def test_chapter14_sources_agree_with_the_profile_parse():
    import pandas as pd
    from pathlib import Path
    ch14 = pd.read_csv(Path("data/reference/tisserand_ch14_sources.csv"), dtype=str, keep_default_na=False)
    cons = pd.read_csv(Path("data/constituents.csv"), dtype=str, keep_default_na=False)
    assert len(ch14) > 1500
    eug = ch14[(ch14["Constituent_CAS"] == "97-53-0") & (ch14["Natural"] == "Clove bud")]
    assert len(eug) == 1 and float(eug["Max_Pct"].iloc[0]) == float(cons[(cons["Natural_CAS"] == "8000-34-8") & (cons["Constituent_CAS"] == "97-53-0")]["Typical_Max_Pct"].iloc[0])


def test_curtis_monographs_parsed_and_cross_checked(data):
    import pandas as pd
    from pathlib import Path
    mono = pd.read_csv(Path("data/reference/curtis_monographs.csv"), dtype=str, keep_default_na=False)
    assert len(mono) >= 200 and set(mono["Curtis_Note_Class"]) <= {"Top", "Middle", "Basic"}
    assert (mono["Intensity_1_6"] != "").mean() > 0.95                                  # the bold digit was found on nearly every monograph
    aur = mono[mono["Material"] == "Aurantiol"].iloc[0]
    assert aur["Curtis_Note_Class"] == "Basic" and aur["Intensity_1_6"] == "3" and "Schiff base" in aur["Chemical_Name"]      # PDF p.174, checked by eye
    cas = mono[mono["Material"] == "Cassia Oil, Rectified"].iloc[0]
    assert cas["Curtis_Note_Class"] == "Middle" and cas["Intensity_1_6"] == "3" and "iron" in cas["Stability"]                 # PDF p.263
    chk = data.curtis_check
    assert len(chk) >= 140 and chk["Intensity_Agrees"].all()                             # dosing classes agree with the book at the extremes
    assert (~chk["Layer_Agrees"]).sum() > 0                                              # the layer disagreements are real and reported, not hidden


def test_tisserand_advisory_never_uses_another_grade_of_a_shared_cas(data):
    # cinnamon bark and leaf share 8015-91-6: the bark figure (0.07 %) must not judge the leaf oil, and vice versa
    leaf = se.check_formula(F(("Cinnamon Leaf Oil", "8015-91-6", 0.29), ("Sandalwood Oil", "8006-87-9", 99.71)), data)
    assert not [x for x in leaf.flags if x.code == "TY_ADVISORY" and x.note == "Cinnamon Leaf Oil"]
    bark = se.check_formula(F(("Cinnamon Bark Oil", "8015-91-6", 0.29), ("Sandalwood Oil", "8006-87-9", 99.71)), data)
    assert [x for x in bark.flags if x.code == "TY_ADVISORY" and x.note == "Cinnamon Bark Oil" and "0.07" in x.message]


def test_book_decisions_are_applied_and_documented(data):
    import pandas as pd
    from pathlib import Path
    dec = pd.read_csv(Path("data/reference/book_review_decisions.csv"), dtype=str, keep_default_na=False)
    assert len(dec) >= 40 and set(dec["Decision"]) >= {"changed", "kept", "provisional cap"}
    n = data.notes
    assert set(n.loc[n["Note_Name"] == "Aldehyde C-14", "Volatility_Class"]) == {"Base"}          # changed: Curtis + BP 286-290 C
    assert set(n.loc[n["Note_Name"] == "Galbanum Resin", "Volatility_Class"]) == {"Base"}         # changed: the resinoid is a base note
    assert set(n.loc[n["Note_Name"] == "Benzyl Salicylate", "Volatility_Class"]) == {"Base"}      # kept: Carles beats Curtis
    assert set(n.loc[n["Note_Name"] == "Citral", "Volatility_Class"]) == {"Top"}                  # kept: consensus beats Curtis
    assert (data.curtis_check.loc[~data.curtis_check["Layer_Agrees"], "Decided"] != "").all()      # nothing left open
    caps = data.safety_caps.set_index("CAS")
    assert float(caps.loc["8022-56-8", "Max_Safe_Percent"]) == 0.4 and caps.loc["8022-56-8", "Provisional"] == "Yes"   # Dalmatian sage: thujone
    r = se.check_formula(F(("Sage", "8022-56-8", 5.0), ("Sandalwood Oil", "8006-87-9", 95.0)), data)
    assert float(r.formula.set_index("Note_Name").loc["Sage", "Pct"]) == 0.4                       # the cap acts; before it the oil was allowed at 100 %
