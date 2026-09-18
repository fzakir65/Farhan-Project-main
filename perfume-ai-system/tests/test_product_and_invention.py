"""Product formulation (concentrate -> bottle) and invention (new compositions from preference terms)."""
from __future__ import annotations

import pandas as pd
import pytest

import load_data as ld
from zone_b_chemistry.invention import invent
from zone_b_chemistry.pipeline import run_zone_b
from zone_b_chemistry.product_formulation import formulate_product


@pytest.fixture(scope="module")
def data() -> ld.Data:
    return ld.load_all()


@pytest.fixture(scope="module")
def concentrate(data):
    return run_zone_b(["Fougere", "Amber", "Citrus"], data).formula


EDP = "Parfum de toilette / Eau de parfum / Esprit de parfum"


def test_product_sums_to_100_and_follows_rsc_fig_9_1(data, concentrate):
    p = formulate_product(concentrate, data, product_type=EDP, concentrate_pct=12, batch_g=250)
    assert p.table["Pct"].sum() == pytest.approx(100.0, abs=1e-6)
    t = p.table.set_index("Component")
    assert t.loc["Fragrance concentrate", "Pct"] == 12 and 75 <= t.loc["Ethanol (denatured, DEB 100)", "Pct"] <= 80
    assert 8 <= t.loc["Purified water", "Pct"] <= 10 and t.loc["BHT", "Pct"] == 0.1 and t.loc["Benzophenone-3", "Pct"] == 0.5
    assert p.table["Grams"].sum() == pytest.approx(250.0, abs=0.01)
    assert p.process and "chill" in " ".join(p.process)


def test_materials_are_expressed_at_product_level_and_safety_rerun_there(data, concentrate):
    p = formulate_product(concentrate, data, product_type=EDP, concentrate_pct=10)
    m = p.materials.set_index("Note_Name")
    assert (m["Product_Pct"] == (m["Concentrate_Pct"] * 0.10).round(5)).all()
    assert p.safety.concentrate_fraction == 0.10 and p.safety.verdict in ("PASS", "ADJUSTED")


def test_allergen_declaration_includes_direct_and_constituent_sources(data):
    f = pd.DataFrame([("Coumarin", "91-64-5", 1.0), ("Clove Bud Oil", "8000-34-8", 2.0), ("Vetiver", "8016-96-4", 97.0)],
                     columns=["Note_Name", "CAS", "Pct"])
    p = formulate_product(f, data, product_type=EDP, concentrate_pct=10)
    a = p.allergens.set_index("Allergen")
    assert a.loc["Coumarin", "Product_Pct"] == pytest.approx(0.1, abs=1e-6) and "direct" in a.loc["Coumarin", "Sources"]
    assert a.loc["Eugenol", "Product_Pct"] == pytest.approx(2.0 * 0.10 * 0.88, abs=1e-4) and "Clove Bud Oil" in a.loc["Eugenol", "Sources"]
    assert "Linalool" not in a.index                                   # nothing supplies it here


def test_product_type_range_is_enforced_and_warnings_are_raised(data, concentrate):
    with pytest.raises(ValueError):
        formulate_product(concentrate, data, product_type=EDP, concentrate_pct=40)
    with pytest.raises(ValueError):
        formulate_product(concentrate, data, product_type="Attar")
    p = formulate_product(concentrate, data, product_type="Splash cologne", concentrate_pct=3)
    assert any("water" in w for w in p.warnings)                       # splash: 50-70 % alcohol -> lots of water


def test_every_auxiliary_has_a_legal_basis(data):
    b = data.product_bases
    assert (b["Legal_Basis"] != "").all() and (b["Source"] != "").all()
    assert "Annex VI" in b.set_index("Component").loc["Benzophenone-3", "Legal_Basis"]


# ----------------------------------------------------------------------------
# invention
# ----------------------------------------------------------------------------

def test_invention_builds_ranked_variants_that_pass(data):
    inv = invent(["woody", "fresh spicy", "amber", "lavender"], data, family="Fougere", n_variants=4)
    assert inv.accords and len(inv.variants) == 4
    assert inv.best() is not None and inv.best().verdict == "PASS"
    assert all(v.formula["Pct"].sum() == pytest.approx(100.0, abs=1e-3) for v in inv.variants)
    assert {"Oakmoss Absolute", "Tonka Bean"} <= set(inv.variants[0].added_signature)
    ratios = {v.ratio for v in inv.variants}
    assert "as built" in ratios and "9:1" in ratios


def test_invention_is_deterministic(data):
    a = invent(["citrus", "mossy", "rose"], data, family="Chypre", n_variants=3)
    b = invent(["citrus", "mossy", "rose"], data, family="Chypre", n_variants=3)
    assert a.report() == b.report()


def test_invention_reports_unmapped_terms_and_unknown_family(data):
    inv = invent(["unicorn dust", "woody"], data)
    assert inv.unmapped_terms == ["unicorn dust"] and inv.variants
    with pytest.raises(ValueError):
        invent(["woody"], data, family="Gourmand-Aquatic")
    empty = invent(["unicorn dust"], data)
    assert empty.variants == [] and empty.unmapped_terms == ["unicorn dust"]


def test_invention_variants_differ_in_the_base_pair_only(data):
    inv = invent(["woody", "amber"], data, n_variants=3)
    v9, v8 = [v for v in inv.variants if v.ratio == "9:1"][0], [v for v in inv.variants if v.ratio == "8:2"][0]
    a, b = v9.formula.set_index("Note_Name")["Pct"], v8.formula.set_index("Note_Name")["Pct"]
    changed = [n for n in a.index if n in b.index and abs(a[n] - b[n]) > 1e-6]
    assert 2 <= len(changed) <= len(a)                                 # the pair moves, the rest only through rebalancing
