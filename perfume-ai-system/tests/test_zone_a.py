"""Tasks 5-6 — Zone A. The button path needs no API (Rule 9); the LLM is grounded in the catalogue (Rule 11) and
never produces a quantity; Zone B never imports Zone A (Rule 1)."""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest

import load_data as ld
from zone_a_llm.describer import FORBIDDEN, describe, template
from zone_a_llm.input_handler import Preferences, interpret, vocabulary
from zone_a_llm.llm_client import FakeClient, complete
from zone_a_llm.matcher import match, score_perfume, shortlist
from zone_b_chemistry.pipeline import perfume_to_accords, run_zone_b_for_perfume

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def data() -> ld.Data:
    return ld.load_all()


# ----------------------------------------------------------------------------
# input handler
# ----------------------------------------------------------------------------

def test_keyword_interpretation_uses_only_catalogue_vocabulary(data):
    # the deterministic path is now keywords + the lexicon datasheet (see tests/test_zone_a_input.py); both stay inside the vocabulary
    p = interpret("I want something fresh and woody for summer, not too sweet, for him — long lasting", data, log=False)
    assert p.source.startswith("keywords") and {"fresh", "woody"} <= set(p.accords) and p.avoid == ["sweet"]
    assert p.gender == "Men" and p.season == "Summer" and p.strength == 5
    v = vocabulary(data)
    assert set(p.accords) <= set(v["accords"])
    assert p.weights["fresh"] == p.weights["woody"] == 1.0          # words the customer actually typed outrank lexicon expansions


def test_longer_term_beats_its_prefix(data):
    p = interpret("fresh spicy please", data)
    assert p.accords == ["fresh spicy"]


def test_empty_text_is_reported_not_guessed(data):
    p = interpret("hello there", data)
    assert p.is_empty() and p.notes


def test_llm_answer_is_clamped_to_the_catalogue(data):
    fc = FakeClient(['{"accords": ["woody", "unicorn dust"], "family": "Nope", "gender": "Men", "season": "Summer", "strength": 9}'])
    p = interpret("woody please", data, client=fc, llm="always", log=False)     # llm="always": the deterministic pass already answered
    assert p.source.endswith("llm") and p.accords == ["woody"] and p.family in (None, "Woody") and p.strength is None
    assert any("unicorn dust" in n for n in p.notes) and any("Nope" in n for n in p.notes)


def test_llm_failure_falls_back_to_keywords(data):
    fc = FakeClient(["not json at all"])
    p = interpret("citrus and amber", data, client=fc, llm="always", log=False)
    assert set(p.accords[:2]) == {"amber", "citrus"}
    assert any("deterministic interpretation used" in n for n in p.notes)


def test_complete_never_raises():
    class Boom:
        def complete(self, *a, **k):
            raise RuntimeError("api down")
    assert complete(Boom(), "s", "u") == "" and complete(None, "s", "u") == ""


# ----------------------------------------------------------------------------
# matcher
# ----------------------------------------------------------------------------

def test_shortlist_is_deterministic_and_explained(data):
    p = Preferences(accords=["woody", "citrus"], gender="Men")
    a, b = shortlist(p, data, 5), shortlist(p, data, 5)
    assert [m.perfume_id for m in a] == [m.perfume_id for m in b]
    assert all(m.reasons for m in a) and a[0].score >= a[-1].score
    assert all(m.perfume_id in set(data.perfumes["Perfume_ID"]) for m in a)


def test_avoided_accord_is_penalised(data):
    row = data.perfumes[data.perfumes["Main_Accords"].str.contains("sweet", case=False)].iloc[0]
    s_ok, _ = score_perfume(row, Preferences(accords=[]))
    s_bad, why = score_perfume(row, Preferences(accords=[], avoid=["sweet"]))
    assert s_bad < s_ok and any("avoided" in w for w in why)


def test_llm_rerank_is_grounded(data):
    p = Preferences(accords=["fresh", "woody"], gender="Men")
    ids = [m.perfume_id for m in shortlist(p, data, 12)]
    good = FakeClient(['{"ranking": ["%s", "%s"], "why": "fits"}' % (ids[3], ids[0])])
    out = match(p, data, top_k=3, client=good)
    assert [m.perfume_id for m in out[:2]] == [ids[3], ids[0]] and out[0].rank_source == "llm"
    bad = FakeClient(['{"ranking": ["P999999"], "why": "invented"}'])
    out2 = match(p, data, top_k=3, client=bad)
    assert [m.perfume_id for m in out2] == ids[:3] and out2[0].rank_source == "deterministic"
    assert "Only recommend from this list" in good.calls[0][0]


# ----------------------------------------------------------------------------
# describer
# ----------------------------------------------------------------------------

def test_template_has_no_numbers_or_safety_words(data):
    for _, row in data.perfumes.head(50).iterrows():
        t = template(row)
        assert row["Profile_Name"] in t and not FORBIDDEN.search(t)


def test_llm_prose_with_quantities_is_replaced(data):
    row = data.perfumes.iloc[0]
    bad = FakeClient([f"{row['Profile_Name']} opens with 12% bergamot and is IFRA compliant."])
    assert describe(row, data, client=bad) == template(row)
    good = FakeClient([f"{row['Profile_Name']} is a bright, breezy scent that feels like a coastal morning. It settles into warm woods."])
    assert describe(row, data, client=good).startswith(row["Profile_Name"])


# ----------------------------------------------------------------------------
# zone boundary and the hand-off
# ----------------------------------------------------------------------------

def test_zone_b_never_imports_zone_a_or_an_llm():
    for f in (ROOT / "zone_b_chemistry").glob("*.py"):
        src = f.read_text(encoding="utf-8")
        assert not re.search(r"\b(anthropic|openai|zone_a_llm|llm_client)\b", src), f.name


def test_perfume_hand_off_to_zone_b(data):
    row = data.perfumes.iloc[0]
    names, weights, unmapped = perfume_to_accords(row, data)
    assert names and all(n in set(data.accords["Accord_Name"]) for n in names)
    assert list(weights.values())[0] == 1.0 and all(0 < w <= 1 for w in weights.values())
    out, un = run_zone_b_for_perfume(row, data, require_complete=False)
    assert out is not None and out.verdict in ("PASS", "REJECT", "INCOMPLETE") and un == unmapped
