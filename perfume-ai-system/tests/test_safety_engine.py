"""Task 3 — safety engine. Every test breaches a limit on purpose and checks that the engine REJECTS, caps or
flags it with the right source row (CLAUDE.md: 'write tests that deliberately breach limits and confirm the
engine flags them'). Same input -> same output; the formula is never mutated; no LLM in Zone B."""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest

import load_data as ld
from zone_b_chemistry import formula_builder as fb
from zone_b_chemistry import safety_engine as se

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def data() -> ld.Data:
    return ld.load_all()


def F(*rows):
    return pd.DataFrame(list(rows), columns=["Note_Name", "CAS", "Pct"])


def pct(res: se.SafetyResult, name: str) -> float:
    return float(res.formula.set_index("Note_Name").loc[name, "Pct"])


# ----------------------------------------------------------------------------
# step 1 — UK/EU regulatory layer overrides IFRA
# ----------------------------------------------------------------------------

def test_lilial_is_rejected_by_uk_ban_even_though_ifra_allows_it(data):
    r = se.check_formula(F(("Lilial", "80-54-6", 1.0), ("Linalool", "78-70-6", 5.0)), data)
    assert r.verdict == "REJECT" and not r.safe
    rej = r.rejections.iloc[0]
    assert rej["Note_Name"] == "Lilial" and rej["Step"] == 1 and "regulatory_uk.csv" in rej["Source"] and "Annex II" in rej["Source"]
    assert any(f.code == "CATEGORY_PROHIBITION" for f in r.flags)          # IFRA's own view is recorded, not applied


@pytest.mark.parametrize("name,cas,used,expect", [
    ("Isoeugenol", "97-54-1", 0.05, 0.02),            # UK/EU 0.02 beats IFRA 0.11
    ("Hydroxycitronellal", "107-75-5", 1.5, 1.0),     # UK/EU 1.0 beats IFRA 2.1
    ("Methyl eugenol", "93-15-2", 0.02, 0.01),        # UK/EU 0.01 beats IFRA 0.011
])
def test_uk_restriction_is_the_binding_ceiling(data, name, cas, used, expect):
    r = se.check_formula(F((name, cas, used)), data)
    assert r.verdict == "ADJUSTED" and pct(r, name) == pytest.approx(expect)
    a = r.adjustments.iloc[0]
    assert a["Step"] == 1 and "regulatory_uk.csv" in a["Source"]
    assert "ifra_limits.csv" in r.ceilings.iloc[0]["Not_Binding"]          # the IFRA ceiling is listed as not binding


def test_costus_and_safrole_are_rejected(data):
    r = se.check_formula(F(("Costus", "8023-88-9", 0.5), ("Safrole", "94-59-7", 0.001)), data)
    assert r.verdict == "REJECT" and set(r.rejections["Note_Name"]) == {"Costus", "Safrole"}
    saf = r.rejections[r.rejections["Note_Name"] == "Safrole"]
    assert len(saf) == 2 and saf["Reason"].str.contains("AS SUCH").any()     # UK ban AND IFRA as-such, both recorded


# ----------------------------------------------------------------------------
# step 2 — IFRA restriction / prohibition / grade / specification
# ----------------------------------------------------------------------------

def test_ifra_restriction_caps_at_category_4(data):
    r = se.check_formula(F(("Coumarin", "91-64-5", 3.0)), data)
    assert r.verdict == "ADJUSTED" and pct(r, "Coumarin") == 1.5
    assert "IFRA_STD_023" in r.adjustments.iloc[0]["Source"] and "91-64-5" in r.pinned


def test_within_limit_passes_and_is_not_pinned(data):
    r = se.check_formula(F(("Coumarin", "91-64-5", 1.0), ("Linalool", "78-70-6", 5.0)), data)
    assert r.verdict == "PASS" and r.adjustments.empty and r.rejections.empty and "91-64-5" not in r.pinned
    assert r.provisional and any(f.code == "STEP0_NOT_IMPLEMENTED" for f in r.flags)


def test_exactly_at_limit_is_pinned(data):
    r = se.check_formula(F(("Coumarin", "91-64-5", 1.5)), data)
    assert r.verdict == "PASS" and "91-64-5" in r.pinned


def test_grade_scoped_prohibition_unknown_grade_rejects(data):
    r = se.check_formula(F(("Cade Oil", "8013-10-3", 1.0)), data)
    assert r.verdict == "REJECT" and "grade unknown" in r.rejections.iloc[0]["Reason"]


def test_grade_scoped_prohibition_with_grades(data):
    ok = se.check_formula(F(("Cade Oil", "8013-10-3", 1.0)), data, grades={"8013-10-3": "rectified"})
    assert ok.verdict == "PASS" and any(f.code == "SPECIFICATION" for f in ok.flags) and any(f.code == "GRADE_NOTE" for f in ok.flags)
    bad = se.check_formula(F(("Cade Oil", "8013-10-3", 1.0)), data, grades={"8013-10-3": "crude"})
    assert bad.verdict == "REJECT" and "prohibited" in bad.rejections.iloc[0]["Reason"]
    odd = se.check_formula(F(("Cade Oil", "8013-10-3", 1.0)), data, grades={"8013-10-3": "premium"})
    assert odd.verdict == "REJECT" and "not a recognised allowed grade" in odd.rejections.iloc[0]["Reason"]


def test_verbena_oil_banned_absolute_restricted(data):
    cas = data.ifra_limits.set_index("Material_Name").loc["Verbena absolute", "CAS"]
    assert se.check_formula(F(("Verbena", cas, 0.1)), data, grades={cas: "verbena oil"}).verdict == "REJECT"
    r = se.check_formula(F(("Verbena", cas, 0.1)), data, grades={cas: "absolute"})
    assert r.verdict in ("PASS", "ADJUSTED") and r.rejections.empty


def test_fig_leaf_absolute_is_rejected(data):
    r = se.check_formula(F(("Fig Leaf Absolute", "68916-52-9", 0.001)), data)
    assert r.verdict == "REJECT" and r.rejections["Source"].str.contains("IFRA_STD_142").any()


def test_any_cas_in_the_standard_matches(data):
    # HICC isomer 51414-25-6 is the second CAS of the HMPCC Standard and UK-banned
    r = se.check_formula(F(("Lyral isomer", "51414-25-6", 0.1)), data)
    assert r.verdict == "REJECT"


# ----------------------------------------------------------------------------
# concentrate fraction
# ----------------------------------------------------------------------------

def test_concentrate_fraction_relaxes_ifra_and_uk_caps_but_not_olfactory_caps(data):
    r = se.check_formula(F(("Coumarin", "91-64-5", 3.0), ("Isoeugenol", "97-54-1", 0.1), ("Vanillin", "121-33-5", 6.0)), data,
                         concentrate_fraction=0.15)
    assert pct(r, "Coumarin") == 3.0 and pct(r, "Isoeugenol") == 0.1        # 1.5/0.15 = 10, 0.02/0.15 = 0.133
    assert pct(r, "Vanillin") == 4.0                                        # olfactory cap is on the concentrate
    assert r.concentrate_fraction == 0.15


def test_concentrate_fraction_must_be_in_unit_interval(data):
    for bad in (0.0, -0.5, 1.5):
        with pytest.raises(ValueError):
            se.check_formula(F(("Coumarin", "91-64-5", 1.0)), data, concentrate_fraction=bad)


def test_prohibitions_ignore_dilution(data):
    assert se.check_formula(F(("Lilial", "80-54-6", 0.001)), data, concentrate_fraction=0.02).verdict == "REJECT"


# ----------------------------------------------------------------------------
# step 3 — group rules
# ----------------------------------------------------------------------------

def test_furocoumarin_sum_of_fractions_scales_the_members(data):
    lim = data.ifra_limits.set_index("CAS")["Category_4_Limit"]
    berg, lemon = 0.9 * lim["8007-75-8"], 0.9 * lim["8008-56-8"]           # each within its own limit, sum 1.8 > 1
    r = se.check_formula(F(("Bergamot Oil", "8007-75-8", berg), ("Lemon Oil", "8008-56-8", lemon)), data)
    assert r.verdict == "ADJUSTED"
    total = pct(r, "Bergamot Oil") / lim["8007-75-8"] + pct(r, "Lemon Oil") / lim["8008-56-8"]
    assert total == pytest.approx(1.0, abs=1e-3)
    assert (r.adjustments["Step"] == 3).all() and {"8007-75-8", "8008-56-8"} <= r.pinned


def test_table_2_phototoxic_materials_are_not_in_the_furocoumarin_sum(data):
    # methyl N-methylanthranilate is phototoxic in its own right; its share must not be scaled by the citrus sum
    r = se.check_formula(F(("Bergamot Oil", "8007-75-8", 0.4), ("Lemon Oil", "8008-56-8", 2.0), ("Dimethyl anthranilate", "85-91-6", 0.05)), data)
    assert pct(r, "Dimethyl anthranilate") == 0.05
    assert not any(a["Note_Name"] == "Dimethyl anthranilate" and a["Step"] == 3 for _, a in r.adjustments.iterrows())


def test_oakmoss_plus_treemoss_sum(data):
    r = se.check_formula(F(("Oakmoss Absolute", "90028-68-5", 0.08), ("Tree Moss", "90028-67-4", 0.08)), data)
    assert pct(r, "Oakmoss Absolute") + pct(r, "Tree Moss") == pytest.approx(0.1, abs=1e-6)
    assert any("oakmoss_treemoss" in a for a in r.adjustments["Source"])


def test_isomer_sum_rose_ketones(data):
    r = se.check_formula(F(("Damascenone", "23696-85-7", 0.03), ("Damascone alpha", "43052-87-5", 0.03)), data)
    assert pct(r, "Damascenone") + pct(r, "Damascone alpha") == pytest.approx(0.043, abs=1e-6)


# ----------------------------------------------------------------------------
# step 4 — olfactory caps; step 5 — reactions
# ----------------------------------------------------------------------------

def test_olfactory_cap_and_provisional_flag(data):
    r = se.check_formula(F(("Vanillin", "121-33-5", 6.0), ("Nutmeg Oil", "8008-45-5", 1.0)), data)
    assert pct(r, "Vanillin") == 4.0 and pct(r, "Nutmeg Oil") == 0.3
    assert any(f.code == "PROVISIONAL_CAP" and f.note == "Nutmeg Oil" for f in r.flags)


def test_vanillin_ethyl_vanillin_equivalence_rule(data):
    r = se.check_formula(F(("Vanillin", "121-33-5", 3.0), ("Ethyl Vanillin", "121-32-4", 1.0)), data)
    v, e = pct(r, "Vanillin"), pct(r, "Ethyl Vanillin")
    assert v + 3 * e == pytest.approx(4.0, abs=1e-3) and v / e == pytest.approx(3.0, abs=1e-3)   # Pct rounded to 4 dp
    assert any("Ch 7 p.141" in a for a in r.adjustments["Source"])


def test_non_numeric_reaction_rule_is_flagged_not_applied(data):
    r = se.check_formula(F(("Indole", "120-72-9", 0.2), ("Skatole", "83-34-1", 0.1)), data)
    assert r.verdict == "PASS" and any(f.code == "REACTION" and f.severity == "WARNING" for f in r.flags)


# ----------------------------------------------------------------------------
# visibility, determinism, purity
# ----------------------------------------------------------------------------

def test_note_without_cas_is_unverified_not_passed_silently(data):
    r = se.check_formula(F(("Mystery Base", "", 2.0)), data)
    assert any(f.code == "NO_CAS" and f.severity == "WARNING" for f in r.flags) and any("UNVERIFIED" in l for l in r.log)


def test_every_adjustment_cites_a_table_and_every_log_line_is_traceable(data):
    r = se.check_formula(F(("Coumarin", "91-64-5", 3.0), ("Isoeugenol", "97-54-1", 0.05), ("Vanillin", "121-33-5", 6.0)), data)
    assert r.adjustments["Source"].str.contains(r"\.csv").all()
    assert r.log[-1].startswith("VERDICT")


def test_deterministic_and_pure(data):
    f = F(("Coumarin", "91-64-5", 3.0), ("Bergamot Oil", "8007-75-8", 1.0), ("Vanillin", "121-33-5", 6.0), ("Lemon Oil", "8008-56-8", 3.0))
    a = se.check_formula(f, data)
    b = se.check_formula(f.sample(frac=1, random_state=11), data)
    pd.testing.assert_frame_equal(a.formula, b.formula)
    assert a.log == b.log and [str(x) for x in a.flags] == [str(x) for x in b.flags]
    pd.testing.assert_frame_equal(f, F(("Coumarin", "91-64-5", 3.0), ("Bergamot Oil", "8007-75-8", 1.0), ("Vanillin", "121-33-5", 6.0), ("Lemon Oil", "8008-56-8", 3.0)))


def test_zone_b_safety_imports_no_llm():
    src = (ROOT / "zone_b_chemistry" / "safety_engine.py").read_text(encoding="utf-8")
    assert not re.search(r"\b(anthropic|openai|zone_a_llm|requests|urllib)\b", src)


# ----------------------------------------------------------------------------
# end to end with the builder
# ----------------------------------------------------------------------------

def test_builder_output_goes_straight_into_the_engine(data):
    rows, _ = fb.accord_rows_for(data.accords, ["Fougere", "Amber", "Citrus"])
    built = fb.build_formula(rows, data.notes)
    r = se.check_formula(built.formula, data)
    assert r.verdict == "ADJUSTED"
    assert pct(r, "Coumarin") == 1.5 and pct(r, "Oakmoss Absolute") == 0.1
    assert r.total_pct < 100 and set(r.formula.columns) >= {"Note_Name", "CAS", "Layer", "Input_Pct", "Pct"}


def test_every_real_accord_runs_through_the_engine(data):
    verdicts = {}
    for aid, g in data.accords.groupby("Accord_ID"):
        built = fb.build_formula(g, data.notes)
        if len(built.formula):
            r = se.check_formula(built.formula, data)
            verdicts[r.verdict] = verdicts.get(r.verdict, 0) + 1
            assert r.formula["Pct"].le(r.formula["Input_Pct"] + 1e-9).all(), aid     # safety only ever lowers
    assert sum(verdicts.values()) >= 200 and verdicts.get("REJECT", 0) >= 1          # e.g. the Costus accords
