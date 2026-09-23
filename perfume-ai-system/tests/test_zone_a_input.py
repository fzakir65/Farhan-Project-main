"""Zone A human-input layer: the lexicon datasheet, negation / strength qualifiers, the questionnaire, and the logs."""
from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd
import pytest

import load_data as ld
from zone_a_llm.input_handler import Preferences, interpret, vocabulary
from zone_a_llm.lexicon import Lexicon
from zone_a_llm.llm_client import FakeClient
from zone_a_llm.matcher import match
from zone_a_llm.questionnaire import answer, load_questionnaire, parse_answers


@pytest.fixture(scope="module")
def data() -> ld.Data:
    return ld.load_all()


@pytest.fixture(scope="module")
def lx() -> Lexicon:
    return Lexicon.load()


# ---------------------------------------------------------------------------------------------------------------
# the datasheet itself
# ---------------------------------------------------------------------------------------------------------------

def test_lexicon_is_a_real_datasheet_and_every_term_is_a_catalogue_term(data, lx):
    df = pd.read_csv(Path(ld.DATA_DIR) / "user_lexicon.csv", dtype=str, keep_default_na=False)
    assert len(df) >= 500
    assert set(df["Kind"]) >= {"everyday language", "material (Ohloff family)", "perfumery descriptor", "strength"}
    assert (df["Source"] != "").all() and (df["Decided_By"] != "").all()          # every row is attributable
    terms = set(vocabulary(data)["accords"])
    for r in df.itertuples():
        for item in str(r.Accord_Terms).split(";"):
            if ":" in item:
                assert item.rsplit(":", 1)[0] in terms, f"{r.Phrase}: {item}"
    assert (df["Source"].str.contains("Curtis")).any() and (df["Source"].str.contains("Ohloff")).any()   # book-sourced rows exist


def test_everyday_words_reach_catalogue_terms(lx):
    for phrase, expected in (("ocean", "aquatic"), ("cookies", "gourmand"), ("clean laundry", "clean"), ("campfire", "smoky"),
                             ("old books", "powdery"), ("pine forest", "coniferous"), ("baby powder", "powdery"), ("espresso", "coffee")):
        assert expected in lx.apply(phrase).weights, phrase


def test_negation_and_strength_qualifiers(lx):
    h = lx.apply("a dark smoky leather for winter nights, no florals")
    assert "floral" in h.avoid and "floral" not in h.weights and "smoky" in h.weights
    h2 = lx.apply("sweet vanilla like cookies, not too strong")
    assert h2.strength == 2 and "vanilla" in h2.weights                      # 'strong' inside 'not too strong' is the qualifier
    h3 = lx.apply("something very strong please")
    assert h3.strength == 5
    h4 = lx.apply("I hate patchouli")
    assert h4.avoid == {"patchouli"}                                          # the negation window catches 'hate'
    h5 = lx.apply("clean laundry and a bit of musk")
    assert not h5.avoid and {"clean", "musky"} <= set(h5.weights)             # no false negation


def test_lexicon_is_deterministic_and_never_needs_an_llm(lx):
    a = lx.apply("beachy salty ocean vibe, not too strong")
    b = lx.apply("beachy salty ocean vibe, not too strong")
    assert a.weights == b.weights and a.strength == b.strength == 2


# ---------------------------------------------------------------------------------------------------------------
# interpret(): keywords + lexicon, LLM only as a fallback
# ---------------------------------------------------------------------------------------------------------------

def test_interpret_uses_the_lexicon_without_any_client(data):
    p = interpret("beachy salty ocean vibe", data, log=False)
    assert {"aquatic", "marine", "salty"} <= set(p.accords) and p.source == "keywords+lexicon"
    assert p.weights and p.accords[0] == max(p.weights, key=p.weights.get)
    assert p.trace                                                            # every match is explained


def test_interpret_calls_the_llm_only_when_the_deterministic_passes_find_nothing(data):
    client = FakeClient(['{"accords": ["woody"], "family": null, "gender": null, "season": null, "avoid": [], "strength": null}'] * 2)
    p = interpret("something fresh and woody for summer", data, client=client, log=False)
    assert not client.calls                                                   # the lexicon answered; no call was made
    p2 = interpret("zzz qqq", data, client=client, log=False)
    assert client.calls and "woody" in p2.accords and p2.source.endswith("llm")


def test_llm_terms_are_clamped_and_ranked_below_the_explicit_words(data):
    client = FakeClient(['{"accords": ["woody", "unicorn tears"], "avoid": [], "family": null, "gender": null, "season": null, "strength": null}'])
    p = interpret("qqq", data, client=client, llm="always", log=False)
    assert "woody" in p.accords and not any("unicorn" in a for a in p.accords)
    assert p.weights["woody"] == 0.5                                          # an LLM suggestion never outweighs a typed word


def test_free_text_reaches_a_sensible_match(data):
    p = interpret("beachy salty ocean vibe", data, log=False)
    names = [m.accords for m in match(p, data, top_k=3)]
    assert any({"marine", "salty"} & set(a) for a in names)


# ---------------------------------------------------------------------------------------------------------------
# the questionnaire
# ---------------------------------------------------------------------------------------------------------------

def test_questionnaire_datasheet(data):
    qs = load_questionnaire()
    assert len(qs) >= 8 and sum(len(q.options) for q in qs) >= 60
    terms = set(vocabulary(data)["accords"])
    for q in qs:
        assert q.type in ("single", "multi") and q.options
        for o in q.options:
            for t, w in o.pairs:
                assert t in terms and 0 < w <= 1
            for a in o.avoid:
                assert a in terms


def test_answers_accumulate_into_preferences():
    qs = load_questionnaire()
    p = answer(parse_answers("Q1=b;Q2=d;Q3=d;Q4=i,r,y;Q5=a;Q6=c;Q7=a"), qs, log=False)
    assert {"leather", "amber", "oud"} <= set(p.accords[:6])
    assert {"sweet", "gourmand", "caramel"} <= set(p.avoid) and not ({"sweet"} & set(p.accords))
    assert p.gender == "Men" and p.season == "Winter" and p.strength == 3
    assert p.weights[p.accords[0]] == 1.0 and p.trace and p.source == "questionnaire"


def test_questionnaire_is_deterministic_and_respects_max_picks():
    qs = load_questionnaire()
    a = answer({"Q4": ["b", "c", "m", "z"]}, qs, log=False)                    # Q4 allows 3
    b = answer({"Q4": ["b", "c", "m", "z"]}, qs, log=False)
    assert a.weights == b.weights
    assert "sandalwood" not in a.accords                                      # the 4th pick is dropped, not silently merged
    bad = answer({"Q9": ["a"], "Q1": ["zz"]}, qs, log=False)
    assert bad.is_empty() and len(bad.notes) >= 2                             # unknown ids are reported, never fatal


def test_questionnaire_feeds_the_matcher(data):
    p = answer(parse_answers("Q2=b;Q3=a;Q4=b,c;Q8=a"), log=False)
    ms = match(p, data, top_k=3)
    assert ms and any({"marine", "aquatic", "salty", "citrus"} & set(m.accords) for m in ms)


# ---------------------------------------------------------------------------------------------------------------
# the log / review loop
# ---------------------------------------------------------------------------------------------------------------

def test_input_log_is_written_and_feeds_the_review_loop(data, tmp_path, monkeypatch):
    import zone_a_llm.input_log as il
    log = tmp_path / "input_log.csv"
    monkeypatch.setattr(il, "log_path", lambda: log)
    interpret("beachy salty ocean vibe with zzzq", data)
    rows = list(csv.DictReader(open(log, encoding="utf-8")))
    assert len(rows) == 1
    r = rows[0]
    assert r["Text"].startswith("beachy") and "aquatic" in r["Final_Terms"] and "zzzq" in r["Unmatched"]
    assert r["Source"] == "keywords+lexicon" and r["LLM_Terms"] == ""
