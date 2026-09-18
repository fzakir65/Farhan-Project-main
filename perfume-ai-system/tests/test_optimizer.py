"""Task 4 — optimizer + Zone B pipeline. Pinned materials never rise, the total returns to exactly 100, the safety
pass is re-run until stable, and a formula that cannot be normalised without breaching a ceiling is REJECTED."""
from __future__ import annotations

import pandas as pd
import pytest

import load_data as ld
from zone_b_chemistry import formula_builder as fb
from zone_b_chemistry import optimizer as op
from zone_b_chemistry import safety_engine as se
from zone_b_chemistry.pipeline import run_zone_b


@pytest.fixture(scope="module")
def data() -> ld.Data:
    return ld.load_all()


def F(*rows):
    return pd.DataFrame(list(rows), columns=["Note_Name", "CAS", "Layer", "Pct"])


def pct(res, name):
    return float(res.formula.set_index("Note_Name").loc[name, "Pct"])


def test_rebalances_to_100_with_pins_fixed(data):
    f = F(("Bergamot Oil", "8007-75-8", "Top", 25.0), ("Rose Absolute", "8007-01-0", "Heart", 20.0),
          ("Oakmoss Absolute", "90028-68-5", "Base", 10.0), ("Vetiver", "8016-96-4", "Base", 25.0), ("Iso E Super", "54464-57-2", "Base", 20.0))
    s = se.check_formula(f, data)
    r = op.optimize(s, data)
    assert r.verdict == "PASS" and r.total_pct == 100.0
    assert pct(r, "Oakmoss Absolute") == 0.1 and pct(r, "Bergamot Oil") == 0.4        # pinned at their ceilings
    assert r.formula.set_index("Note_Name")["Pinned"].to_dict()["Oakmoss Absolute"]
    # the removed Base mass went back into Base (Vetiver / Iso E Super), the removed Top mass has nowhere to go in Top
    assert pct(r, "Vetiver") + pct(r, "Iso E Super") == pytest.approx(55 - 0.1, abs=0.01) or \
        r.layers.set_index("Layer")["Pct"]["Base"] > 55
    assert r.safety.verdict == "PASS" and r.iterations == 1


def test_reject_from_safety_passes_through(data):
    f = F(("Lilial", "80-54-6", "Heart", 5.0), ("Vetiver", "8016-96-4", "Base", 95.0))
    r = op.optimize(se.check_formula(f, data), data)
    assert r.verdict == "REJECT" and r.iterations == 0 and "REJECT" in r.trace[0]


def test_loop_pins_newly_capped_materials_until_stable(data):
    # Oakmoss is cut 9.9 %; redistribution pushes Coumarin over 1.5 -> round 2 caps and pins it; Vetiver absorbs the rest
    f = F(("Oakmoss Absolute", "90028-68-5", "Base", 10.0), ("Coumarin", "91-64-5", "Base", 1.4),
          ("Vetiver", "8016-96-4", "Base", 88.6))
    r = op.optimize(se.check_formula(f, data), data)
    assert r.verdict == "PASS" and r.total_pct == 100.0 and r.iterations >= 2
    assert pct(r, "Coumarin") == 1.5 and pct(r, "Oakmoss Absolute") == 0.1
    assert pct(r, "Vetiver") == pytest.approx(98.4, abs=1e-3)
    assert any("pinning" in t for t in r.trace)


def test_everything_pinned_is_a_reject(data):
    f = F(("Oakmoss Absolute", "90028-68-5", "Base", 60.0), ("Coumarin", "91-64-5", "Base", 40.0))
    r = op.optimize(se.check_formula(f, data), data)
    assert r.verdict == "REJECT" and any("cannot normalise" in x for x in r.flags)
    assert pct(r, "Oakmoss Absolute") == 0.1 and pct(r, "Coumarin") == 1.5            # never raised above a ceiling


def test_heart_cap_holds_during_redistribution(data):
    # only Heart notes are free; the removed mass may lift Heart to 25 but not beyond -> REJECT rather than breach
    f = F(("Oakmoss Absolute", "90028-68-5", "Base", 76.0), ("Rose Absolute", "8007-01-0", "Heart", 24.0))
    r = op.optimize(se.check_formula(f, data), data)
    assert r.verdict == "REJECT"
    assert r.layers.set_index("Layer")["Pct"]["Heart"] <= 25.0 + 1e-6


def test_deterministic(data):
    f = F(("Bergamot Oil", "8007-75-8", "Top", 25.0), ("Rose Absolute", "8007-01-0", "Heart", 20.0),
          ("Oakmoss Absolute", "90028-68-5", "Base", 10.0), ("Vetiver", "8016-96-4", "Base", 45.0))
    a = op.optimize(se.check_formula(f, data), data)
    b = op.optimize(se.check_formula(f.sample(frac=1, random_state=2), data), data)
    pd.testing.assert_frame_equal(a.formula.reset_index(drop=True), b.formula.reset_index(drop=True))
    assert a.trace == b.trace


# ----------------------------------------------------------------------------
# pipeline
# ----------------------------------------------------------------------------

def test_pipeline_pass(data):
    out = run_zone_b(["Fougere", "Amber", "Citrus"], data)
    assert out.verdict == "PASS" and out.formula["Pct"].sum() == pytest.approx(100.0, abs=1e-6)
    L = out.optimized.layers.set_index("Layer")["Pct"]
    assert L["Heart"] <= 25.0 + 1e-6 and L["Base"] >= L["Top"] >= 0
    assert out.safety.verdict == "ADJUSTED" and out.optimized.safety.verdict == "PASS"
    assert "ZONE B: PASS" in out.report()


def test_pipeline_reject_on_banned_material(data):
    costus = data.accords[data.accords["Note_Name"] == "Costus"]["Accord_Name"].iloc[0]
    out = run_zone_b([costus], data, require_complete=False)
    assert out.verdict == "REJECT" and "Costus" in set(out.safety.rejections["Note_Name"])


def test_pipeline_incomplete_when_a_note_cannot_be_placed(data):
    acc = data.accords[data.accords["Note_Name"] == "Cannabis Accord"]["Accord_Name"].iloc[0]
    out = run_zone_b([acc], data)
    assert out.verdict == "INCOMPLETE" and len(out.build.unplaced) == 1 and out.safety is None
    out2 = run_zone_b([acc], data, require_complete=False)
    assert out2.verdict in ("PASS", "REJECT") and out2.safety is not None


def test_pipeline_unknown_accord_is_incomplete_not_ignored(data):
    out = run_zone_b(["Fougere", "Unicorn Dust"], data)
    assert out.verdict == "INCOMPLETE" and out.lookup_flags[0].code == "UNKNOWN_ACCORD"


def test_pipeline_over_all_accords_never_crashes(data):
    verdicts = {}
    for name in sorted(set(data.accords["Accord_Name"])):
        out = run_zone_b([name], data, require_complete=False)
        verdicts[out.verdict] = verdicts.get(out.verdict, 0) + 1
        if out.verdict == "PASS":
            assert out.formula["Pct"].sum() == pytest.approx(100.0, abs=1e-6), name
    assert verdicts.get("PASS", 0) > 150 and "REJECT" in verdicts
