"""Step 3 baseline checks: the book-derived reference tables are well-formed and cited, the IFRA selection gap
is closed, and the new load_data checks (physics plausibility, shared-CAS hazard, Carles cross-check,
product dilution table) fire on deliberate breaches and stay quiet on sound data."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import load_data as ld

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "data" / "reference"


@pytest.fixture(scope="module")
def data() -> ld.Data:
    return ld.load_all()


def _csv(name: str) -> pd.DataFrame:
    return pd.read_csv(REF / name, dtype=str, keep_default_na=False)


# ----------------------------------------------------------------------------
# reference tables (Carles 1961, RSC 1999)
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["carles_volatility_table.csv", "carles_formulas.csv", "carles_family_signatures.csv",
                                  "carles_chypre_compatibility.csv", "carles_student_accords.csv", "rsc_physical_properties.csv"])
def test_every_reference_row_is_cited(name):
    df = _csv(name)
    assert len(df) > 0 and (df["Source"] != "").all()


def test_carles_volatility_table_maps_only_to_real_dataset2_names(data):
    t = _csv("carles_volatility_table.csv")
    assert set(t["Carles_Class"]) == {"Top", "Modifier", "Base"}
    mapped = set(t["Dataset2_Name"]) - {""}
    assert mapped <= set(data.notes["Note_Name"])
    assert len(mapped) >= 35


def test_carles_chypre_formula_is_complete_and_sums_to_100():
    f = _csv("carles_formulas.csv")
    f["Layer_Pct"] = f["Layer_Pct"].astype(float)
    f["Parts"] = f["Parts"].astype(float)
    per_layer = f.drop_duplicates("Layer").set_index("Layer")["Layer_Pct"]
    assert per_layer.to_dict() == {"Top": 25.0, "Heart": 20.0, "Base": 55.0}    # Carles pp.6-7
    assert (f["Parts"] > 0).all()
    assert per_layer["Base"] > per_layer["Top"] > per_layer["Heart"] or per_layer["Base"] > per_layer["Heart"]


def test_student_accords_are_oakmoss_musk_bases():
    a = _csv("carles_student_accords.csv")
    a["Parts"] = a["Parts"].astype(float)
    for (key, var), g in a.groupby(["Accord_Key", "Variant"]):
        mats = " ".join(g["Material"]).lower()
        assert "oak" in mats and "musk" in mats, (key, var)
        assert len(g) == int(g["N_Products"].iloc[0])
        assert g.loc[g["Material"].str.lower().str.contains("oak"), "Parts"].iloc[0] >= g["Parts"].min()
    assert a.groupby(["Accord_Key", "Variant"]).ngroups >= 30


def test_family_signatures_cover_the_four_carles_families():
    s = _csv("carles_family_signatures.csv")
    assert set(s["Family"]) == {"Chypre", "Fougere", "Foin", "Trefle"}
    fougere = set(s.loc[s["Family"] == "Fougere", "Material"].str.lower())
    assert {"lavender", "coumarin"} <= fougere and any("moss" in m for m in fougere)


# ----------------------------------------------------------------------------
# IFRA selection gap closed
# ----------------------------------------------------------------------------

def test_fig_leaf_absolute_and_methylcoumarins_are_in_ifra_limits(data):
    df = data.ifra_limits.set_index("Material_Name")
    assert df.loc["Fig leaf absolute", "IFRA_Type"] == "Prohibition" and df.loc["Fig leaf absolute", "Phototoxic"] == "Yes"
    assert df.loc["6-Methylcoumarin", "IFRA_Type"] == "Prohibition"
    assert df.loc["7-Methylcoumarin", "IFRA_Type"] == "Prohibition"
    r = df.loc["7-Methoxycoumarin"]
    assert r["IFRA_Type"] == "Prohibition_Restriction" and r["Prohibition_Scope"] == "as_such"
    assert r["Category_4_Limit"] == pytest.approx(0.01)
    assert df.loc["2-Hexenal", "Category_4_Limit"] == pytest.approx(0.0077)
    assert len(data.ifra_limits) == 81


# ----------------------------------------------------------------------------
# product types (RSC Table A2) -> CONCENTRATE_FRACTION presets
# ----------------------------------------------------------------------------

def test_product_types_table(data):
    p = data.product_types
    assert len(p) == 7 and not [i for i in data.errors() if i.table == "product_types"]      # 6 RSC Table A2 rows + Poucher Formula VI after-shave
    assert (p["Concentrate_Fraction_Min"] <= p["Concentrate_Fraction_Max"]).all()
    assert p["Concentrate_Fraction_Max"].max() == pytest.approx(0.30)     # extrait 15-30 %
    assert p.set_index("Product_Type").loc["Eau de toilette", "Concentrate_Fraction_Min"] == pytest.approx(0.04)


def test_product_types_rejects_bad_range(tmp_path):
    bad = pd.DataFrame({"Product_Type": ["X"], "Concentrate_Min_Pct": ["40"], "Concentrate_Max_Pct": ["10"],
                        "Alcohol_Pct_Range": [""], "Source": ["test"]})
    path = tmp_path / "product_types.csv"
    bad.to_csv(path, index=False)
    _, issues = ld.load_product_types(path)
    assert any(i.severity == "ERROR" and "not 0 < min <= max" in i.message for i in issues)


# ----------------------------------------------------------------------------
# physics plausibility of Volatility_Class
# ----------------------------------------------------------------------------

def _notes_csv(tmp_path, rows):
    cols = ["Note_ID", "Note_Name", "Chemical_Name", "CAS", "Volatility_Class", "Odor_Strength", "Accords_Used_In",
            "Boiling_Point_C", "Tenacity_hrs"]
    df = pd.DataFrame(rows, columns=cols)
    path = tmp_path / "notes.csv"
    df.to_csv(path, index=False)
    return path


def test_physics_check_flags_gross_contradictions_only(tmp_path):
    path = _notes_csv(tmp_path, [
        ("N1", "Fake Top", "x", "", "Top", "Medium", "", "310", "24"),       # a 'top' that boils at 310 and lasts a day
        ("N2", "Fake Base", "y", "", "Base", "Medium", "", "150", "1"),      # a 'base' gone in an hour
        ("N3", "Limonene", "Limonene", "138-86-3", "Top", "Medium", "", "176", "0.5–1"),
        ("N4", "Vetiver", "Vetiver", "8016-96-4", "Base", "Medium", "", "300", "24"),
    ])
    _, issues = ld.load_notes(path)
    flagged = {i.row for i in issues if "contradicts its physics" in i.message}
    assert flagged == {"N1", "N2"}


def test_physics_check_on_real_data_is_small(data):
    n = len([i for i in data.issues if "contradicts its physics" in i.message])
    assert n <= 25     # 17 today, all explainable (marine top notes, oils carrying a key molecule's BP)


# ----------------------------------------------------------------------------
# shared-CAS hazard
# ----------------------------------------------------------------------------

def test_same_material_heuristic():
    assert ld.same_material("Bergamot", "Citrus bergamia", "Bergamot Oil FCF", "Limonene rich")
    assert ld.same_material("Civetone", "Civetone", "Civettone", "Civetone")
    assert ld.same_material("Frankincense CO2", "Boswellia", "Olibanum Resinoid", "Boswellia carterii")
    assert ld.same_material("Toasted Sugar", "Cyclotene", "Cyclotene", "Cyclotene")
    assert not ld.same_material("Cade Oil", "Phenolic tar", "Cedarwood", "Cedrol")
    assert not ld.same_material("Iso E Super", "Iso E Super", "Safraleine", "Safraleine")


def test_shared_cas_conflicts_on_real_data(data):
    shared = data.shared_cas
    assert "54464-57-2" not in shared                                       # Iso E Super's CAS removed from Safraleine etc. (2026-09-18)
    assert "8000-27-9" not in shared                                        # cade / juniper tar fixed to 8013-10-3 (2026-09-16)
    assert len(shared) <= 10                                                # what remains is listed in data.shared_cas
    assert set(data.notes.loc[data.notes["Note_Name"].isin(["Cade Oil", "Juniper Tar"]), "CAS"]) == {"8013-10-3"}
    assert "8007-75-8" not in shared and "8016-36-2" not in shared          # bergamot variants; frankincense/olibanum
    assert any("shared by unrelated notes" in i.message for i in data.warnings())


# ----------------------------------------------------------------------------
# Carles cross-check
# ----------------------------------------------------------------------------

def test_carles_cross_check_reports_but_does_not_change_dataset2(data):
    dis = data.carles_disagreements
    assert set(dis.columns) >= {"Material", "Dataset2_Name", "Carles_Class", "Dataset2_Classes", "Source"}
    assert 0 < len(dis) <= 15
    # dataset2 is untouched: the disagreeing notes still carry their own class
    for r in dis.itertuples(index=False):
        assert set(data.notes.loc[data.notes["Note_Name"] == r.Dataset2_Name, "Volatility_Class"]) == set(r.Dataset2_Classes.split("/"))
    assert any("disagrees with Carles" in i.message for i in data.warnings())
