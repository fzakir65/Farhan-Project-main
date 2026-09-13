"""Task 1 tests: the loader reads every table, the rule tables agree with the official
IFRA 51st Amendment, the UK/EU layer overrides IFRA where it should, and deliberate
breaches in the data are caught (CLAUDE.md: "write tests that deliberately breach
limits and confirm the engine flags them")."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

import pandas as pd
import pytest

import load_data as ld

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = ROOT / "data" / "reference" / "ifra_51st_standards_overview.csv"


@pytest.fixture(scope="module")
def data() -> ld.Data:
    return ld.load_all()


@pytest.fixture(scope="module")
def official() -> pd.DataFrame:
    return pd.read_csv(OFFICIAL, skiprows=2, dtype=str, keep_default_na=False).set_index("Key")


def _errors(data: ld.Data, table: str) -> list[ld.Issue]:
    return [i for i in data.errors() if i.table == table]


# ----------------------------------------------------------------------------
# loading
# ----------------------------------------------------------------------------

def test_every_table_loads_with_required_columns(data):
    for table, cols in ld.REQUIRED_COLUMNS.items():
        df = getattr(data, table)
        assert len(df) > 0, table
        assert set(cols) <= set(df.columns), table


def test_expected_row_counts(data):
    assert len(data.perfumes) == 450
    assert len(data.notes) == 720          # exact duplicates are only *reported* at this stage
    assert len(data.accords) == 1518
    assert len(data.ifra_limits) == 76
    assert len(data.group_rules) == 8
    assert len(data.regulatory) >= 50
    assert len(data.safety_caps) == 30
    assert len(data.reaction_rules) == 5


def test_load_is_deterministic():
    a, b = ld.load_all(), ld.load_all()
    assert [str(i) for i in a.issues] == [str(i) for i in b.issues]
    pd.testing.assert_frame_equal(a.ifra_limits.drop(columns=["All_CAS_List", "Type_Parts"]),
                                  b.ifra_limits.drop(columns=["All_CAS_List", "Type_Parts"]))


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("cas,ok", [
    ("78-70-6", True), ("91-64-5", True), ("80-54-6", True), ("8007-75-8", True), ("23696-85-7", True),
    ("78-70-7", False), ("66355-00-4", False), ("-", False), ("", False), (None, False), ("abc", False),
])
def test_cas_checksum(cas, ok):
    assert ld.is_valid_cas(cas) is ok


def test_normalizers():
    assert ld.normalize_layer("Top / Heart") == "Top/Heart"
    assert ld.normalize_layer("base") == "Base"
    assert ld.normalize_name("  Iso  E Super ") == "iso e super"
    assert ld.split_multi("a; b ;; c") == ["a", "b", "c"]
    assert ld.split_cas_list("1-11-1|2-22-2") == ["1-11-1", "2-22-2"]


# ----------------------------------------------------------------------------
# rule tables must be internally clean and agree with the official IFRA table
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("table", ["ifra_limits", "group_rules", "regulatory", "safety_caps", "reaction_rules"])
def test_rule_tables_have_no_errors(data, table):
    assert _errors(data, table) == [], "\n".join(map(str, _errors(data, table)))


def test_every_ifra_row_matches_the_official_standard(data, official):
    # Locate the official Standard by the row's CAS (independently of IFRA_Key), then compare everything.
    cas2key = {}
    for key, o in official.iterrows():
        for cas in re.findall(r"\d{2,7}-\d{2}-\d", o["CAS numbers"]):
            cas2key.setdefault(cas, key)
    for _, r in data.ifra_limits.iterrows():
        assert cas2key.get(r["CAS"]) == r["IFRA_Key"], f"{r['Material_Name']}: CAS {r['CAS']} belongs to {cas2key.get(r['CAS'])}"
        o = official.loc[r["IFRA_Key"]]
        assert r["IFRA_Type"].upper() == o["IFRA Standard type"], r["Material_Name"]
        official_cas = re.findall(r"\d{2,7}-\d{2}-\d", o["CAS numbers"])
        assert r["All_CAS_List"] == official_cas, r["Material_Name"]
        raw = o["Category 4 (%)"].strip().replace(",", ".")
        if r["IFRA_Key"] in {"IFRA_STD_179"}:          # 'See Notebox' -> limit taken from the Standard's notes
            assert r["Category_4_Limit"] == 0.01
            assert "0.01%" in o["Restricted ingredients: notes"]
        elif re.fullmatch(r"[0-9.]+", raw):
            assert r["Category_4_Limit"] == pytest.approx(float(raw)), r["Material_Name"]
        else:
            assert pd.isna(r["Category_4_Limit"]), r["Material_Name"]
        intrinsic = o["Intrinsic property driving the risk management measure"].upper()
        assert (r["Phototoxic"] == "Yes") == ("PHOTOTOXICITY" in intrinsic), r["Material_Name"]


def test_own_phototoxic_materials_are_table_2_plus_verbena(data):
    own = data.ifra_limits[(data.ifra_limits["Phototoxic"] == "Yes")
                           & ~data.ifra_limits["Notes"].str.contains("Furocoumarin")]
    table_2 = {"15323-35-0", "85-91-6", "93-08-3", "91722-29-1", "41270-80-8"}
    verbena = {"85116-63-8"}    # phototoxicity drives the OIL prohibition; absolute restricted
    assert set(own["CAS"]) == table_2 | verbena
    assert own["Notes"].str.contains("NOT part of furocoumarin sum").all()
    furo = data.ifra_limits[data.ifra_limits["Notes"] == "Furocoumarin"]
    assert len(furo) == 8 and (furo["Phototoxic"] == "Yes").all()


def test_prohibition_scope_is_set_exactly_where_needed(data):
    df = data.ifra_limits
    with_p = df["IFRA_Type"].str.contains("Prohibition")
    assert (df.loc[with_p, "Prohibition_Scope"] != "").all()
    assert (df.loc[~with_p, "Prohibition_Scope"] == "").all()
    by = df.set_index("Material_Name")["Prohibition_Scope"]
    assert by["Lilial"] == "category" and by["Safrole"] == "as_such"
    assert by["Peru balsam"] == "grade" and by["Costus root oil"] == "all"
    # safrole: direct addition is BANNED on the regulatory side, natural ceiling lives on the IFRA side
    reg = data.regulatory.set_index("CAS").loc["94-59-7"]
    assert reg["Status"] == "BANNED" and pd.isna(reg["Fine_Fragrance_Limit_Pct"])


def test_audit_corrections_are_in_place(data):
    by_name = data.ifra_limits.set_index("Material_Name")
    assert by_name.loc["Lilial", "Category_4_Limit"] == pytest.approx(1.4)          # was 0.06
    assert by_name.loc["Raspberry ketone", "Category_4_Limit"] == pytest.approx(1)  # was 0.27
    assert "Ambrettolide" not in by_name.index                                      # had no IFRA Standard
    assert by_name.loc["Tagetes oil", "IFRA_Type"] == "Prohibition_Restriction_Specification"
    for added in ("Methyl heptine carbonate", "Methyl octine carbonate", "Costus root oil", "Styrax",
                  "Musk ambrette", "Jasmine absolute (grandiflorum)", "Methyl eugenol", "HICC (Lyral)"):
        assert added in by_name.index, added


def test_furocoumarin_group_is_exactly_the_eight_oils(data):
    g = data.group_rules.set_index("Group_Name").loc["furocoumarin_ncs"]
    names = g["Members_Names"].split("|")
    assert len(names) == 8
    for n in ("Angelica root oil", "Bergamot oil expressed", "Bitter orange peel oil expressed", "Cumin oil",
              "Grapefruit oil expressed", "Lemon oil cold pressed", "Lime oil expressed", "Rue oil"):
        assert n in names, n
    # own-phototoxicity materials must NOT be in the sum (Guidance s1.6.1.2)
    for cas in ("15323-35-0", "85-91-6", "93-08-3", "91722-29-1"):
        assert cas not in g["Members_CAS_List"], cas
    assert g["Limit"] == pytest.approx(1.0)


def test_regulatory_layer_overrides_ifra_where_expected(data):
    ov = data.regulatory_overrides.set_index("CAS")
    assert ov.loc["80-54-6", "Overrides_IFRA"]           # Lilial: IFRA 1.4 vs UK/EU ban
    assert ov.loc["31906-04-4", "Overrides_IFRA"]        # HICC
    assert ov.loc["119-84-6", "Overrides_IFRA"]          # Dihydrocoumarin
    assert ov.loc["107-75-5", "UK_EU_Limit"] == pytest.approx(1.0) and ov.loc["107-75-5", "Overrides_IFRA"]
    assert ov.loc["97-54-1", "UK_EU_Limit"] == pytest.approx(0.02) and ov.loc["97-54-1", "Overrides_IFRA"]
    assert not ov.loc["83-66-9", "Overrides_IFRA"]       # Musk ambrette: IFRA prohibits it too -> agreement
    assert not ov.loc["8023-88-9", "Overrides_IFRA"]     # Costus: agreement


def test_banned_catalogue_notes_are_flagged(data):
    banned = set(data.notes_regulated.loc[data.notes_regulated["Status"] == "BANNED", "CAS"])
    assert {"80-54-6", "8023-88-9", "81-15-2"} <= banned   # Lilial, Costus, Musk xylene are in dataset2


def test_safety_caps_never_contradict_ifra_or_uk_law(data):
    # Costus removed, Styrax lowered to 0.6 (< 0.64), cinnamon split, nutmeg/saffron lowered
    assert _errors(data, "safety_caps") == []
    caps = data.safety_caps.set_index("Material_Name")["Max_Safe_Percent"]
    assert "Costus Oil" not in caps.index
    assert caps["Styrax Resinoid"] < 0.64
    assert caps["Cinnamon Bark Oil"] <= 0.25 / 0.65 + 1e-9    # ~65-75% cinnamic aldehyde vs 0.25% limit


# ----------------------------------------------------------------------------
# known catalogue defects must be *reported* (not silently accepted)
# ----------------------------------------------------------------------------

def test_known_catalogue_gaps_are_reported(data):
    assert any("fails the CAS checksum" in i.message for i in _errors(data, "notes"))
    assert len(data.unmatched_accord_notes) > 0
    assert any("not in dataset2" in i.message for i in _errors(data, "accords"))
    shifted = [i for i in data.warnings() if i.table == "perfumes" and "shifted" in i.message]
    assert len(shifted) == 10


def test_perfume_column_shift_was_repaired(data):
    r = data.perfumes.set_index("Perfume_ID").loc["P000291"]
    assert r["Gender"] == ""
    assert r["Season"].startswith("Spring")
    assert r["Description"].startswith("Clean powdery iris")
    assert r["Sillage_Score"] == ld.SILLAGE_SCORE["moderate"]


def test_perfume_scores_and_lists(data):
    p = data.perfumes
    assert p["Longevity_Score"].dropna().between(1, 5).all()
    assert p["Sillage_Score"].dropna().between(1, 5).all()
    assert p["Longevity_Score"].notna().mean() > 0.95
    assert isinstance(p.loc[0, "Top_Notes_List"], list)


# ----------------------------------------------------------------------------
# deliberate breaches: the validator must catch each one
# ----------------------------------------------------------------------------

def _data_copy_with(tmp_path: Path, table: str, mutate) -> ld.Data:
    """Copy data/ to tmp, apply `mutate(df) -> df` to one CSV, load from the copy."""
    dst = tmp_path / "data"
    shutil.copytree(ROOT / "data", dst)
    path = dst / ld.FILES[table]
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    mutate(df).to_csv(path, index=False)
    return ld.load_all(dst)


def _append(df: pd.DataFrame, row: dict) -> pd.DataFrame:
    return pd.concat([df, pd.DataFrame([{c: row.get(c, "") for c in df.columns}])], ignore_index=True)


def test_breach_cap_above_ifra_limit(tmp_path):
    d = _data_copy_with(tmp_path, "safety_caps", lambda df: _append(df, {
        "Material_Name": "Coumarin", "CAS": "91-64-5", "Max_Safe_Percent": "5", "Reason": "test", "Provisional": "No"}))
    assert any("exceeds IFRA Cat 4 limit 1.5" in i.message for i in _errors(d, "safety_caps"))


def test_breach_cap_on_ifra_prohibited_material(tmp_path):
    d = _data_copy_with(tmp_path, "safety_caps", lambda df: _append(df, {
        "Material_Name": "Costus Oil", "CAS": "8023-88-9", "Max_Safe_Percent": "1", "Reason": "test", "Provisional": "No"}))
    msgs = [i.message for i in _errors(d, "safety_caps")]
    assert any("IFRA-prohibited" in m for m in msgs) and any("BANNED" in m for m in msgs)


def test_breach_cap_above_uk_limit(tmp_path):
    d = _data_copy_with(tmp_path, "safety_caps", lambda df: _append(df, {
        "Material_Name": "Isoeugenol", "CAS": "97-54-1", "Max_Safe_Percent": "0.1", "Reason": "test", "Provisional": "No"}))
    assert any("exceeds UK/EU limit 0.02" in i.message for i in _errors(d, "safety_caps"))


def test_breach_ifra_type_vocabulary(tmp_path):
    def mutate(df):
        df.loc[df["Material_Name"] == "Coumarin", "IFRA_Type"] = "Restricted"
        return df
    d = _data_copy_with(tmp_path, "ifra_limits", mutate)
    assert any("IFRA_Type" in i.message for i in _errors(d, "ifra_limits"))


def test_breach_restriction_without_limit(tmp_path):
    def mutate(df):
        df.loc[df["Material_Name"] == "Coumarin", "Category_4_Limit"] = ""
        return df
    d = _data_copy_with(tmp_path, "ifra_limits", mutate)
    assert any("Restriction without a numeric" in i.message for i in _errors(d, "ifra_limits"))


def test_breach_prohibition_with_limit(tmp_path):
    def mutate(df):
        df.loc[df["Material_Name"] == "Musk ambrette", "Category_4_Limit"] = "0.5"
        return df
    d = _data_copy_with(tmp_path, "ifra_limits", mutate)
    assert any("pure Prohibition must not carry" in i.message for i in _errors(d, "ifra_limits"))


def test_breach_bad_cas_in_rule_table(tmp_path):
    def mutate(df):
        df.loc[df["Material_Name"] == "Coumarin", "CAS"] = "91-64-4"
        return df
    d = _data_copy_with(tmp_path, "ifra_limits", mutate)
    assert any("invalid CAS '91-64-4'" in i.message for i in _errors(d, "ifra_limits"))


def test_breach_banned_with_limit(tmp_path):
    def mutate(df):
        df.loc[df["CAS"] == "80-54-6", "Fine_Fragrance_Limit_Pct"] = "1.4"
        return df
    d = _data_copy_with(tmp_path, "regulatory", mutate)
    assert any("BANNED must not carry a limit" in i.message for i in _errors(d, "regulatory"))


def test_breach_prohibition_scope_missing(tmp_path):
    def mutate(df):
        df.loc[df["Material_Name"] == "Peru balsam", "Prohibition_Scope"] = ""
        return df
    d = _data_copy_with(tmp_path, "ifra_limits", mutate)
    assert any("Prohibition_Scope must be one of" in i.message for i in _errors(d, "ifra_limits"))


def test_breach_group_with_single_member(tmp_path):
    def mutate(df):
        df.loc[df["Group_Name"] == "mhc_moc", "Members_CAS"] = "111-12-6"
        return df
    d = _data_copy_with(tmp_path, "group_rules", mutate)
    assert any("at least two member CAS" in i.message for i in _errors(d, "group_rules"))


def test_missing_file_gives_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="build_datasets"):
        ld.load_all(tmp_path)


def test_main_exit_code_reflects_errors(capsys):
    rc = ld.main([])
    out = capsys.readouterr().out
    assert "DATA REPORT" in out
    assert rc == 2   # the catalogue currently has known ERROR-level defects; flips to 0 once fixed
