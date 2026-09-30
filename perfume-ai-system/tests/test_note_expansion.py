"""The dataset2 expansion of 2026-09-23 (data/build_note_expansion.py).

What these lock down is not "the numbers are right" — a perfumer still has to sign the rows off — but that the
generator stayed inside its own rules: every added row cites a book, no row invents a CAS, the everyday-name table
never reaches dataset3, and the profile library's note columns resolve against dataset2 far better than before.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "data"))

import load_data as ld  # noqa: E402

GEN_TAG = "ai (2026-09-23) - book expansion"


@pytest.fixture(scope="module")
def data():
    return ld.load_all()


@pytest.fixture(scope="module")
def generated():
    add = pd.read_csv(ROOT / "data" / "note_additions.csv", dtype=str, keep_default_na=False)
    return add[add["Decided_By"].str.startswith(GEN_TAG)].reset_index(drop=True)


@pytest.fixture(scope="module")
def display_aliases():
    return pd.read_csv(ROOT / "data" / "note_display_aliases.csv", dtype=str, keep_default_na=False)


def test_generated_block_is_present_and_cited(generated):
    assert len(generated) == 40                       # 27 Curtis monographs + 9 Ohloff + 6 T&Y Ch 14 naturals
    assert (generated["Source"].str.strip() != "").all(), "every generated row must cite the book it came from"
    books = generated["Source"].str.contains("Curtis|Ohloff|Tisserand", case=False)
    assert books.all(), sorted(generated.loc[~books, "Note_Name"])


def test_olfactory_fields_are_complete(generated):
    """Curtis' note class, his 1-6 odour strength and his odour codes fill these for every row — the whole point
    of mining the monographs rather than adding bare names."""
    for col in ("Volatility_Class", "Odor_Strength", "Odor_Family", "Key_Nuances"):
        blank = generated.loc[generated[col].str.strip() == "", "Note_Name"]
        assert blank.empty, f"{col} empty for {list(blank)}"
    assert set(generated["Volatility_Class"]) <= {"Top", "Heart", "Base"}
    assert set(generated["Odor_Strength"]) <= {"Very strong", "Strong", "Medium", "Low"}


def test_no_cas_was_invented(generated):
    """A CAS is a safety join key. Every one here came from PubChem or from a project table; the six naturals that
    no source could verify carry a BLANK CAS and say so, because missing beats wrong."""
    blank = generated[generated["CAS"].str.strip() == ""]
    for r in blank.itertuples():
        assert "supplier CoA required" in r.Short_Description, f"{r.Note_Name} has no CAS and no explanation"
    for cas in generated.loc[generated["CAS"].str.strip() != "", "CAS"]:
        assert ld.is_valid_cas(cas), f"{cas} fails the CAS checksum"


def test_generated_rows_do_not_duplicate_dataset2(data, generated):
    names = list(data.notes["Note_Name"])
    for n in generated["Note_Name"]:
        assert names.count(n) == 1, f"{n} appears {names.count(n)} times in dataset2"


def test_display_aliases_never_touch_the_accords(display_aliases):
    """note_display_aliases.csv is read by data/build_profiles.py only. Renaming a note inside an accord would be a
    chemistry change, so these editorial names must not have leaked into the dataset3 alias table."""
    ds3 = pd.read_csv(ROOT / "data" / "note_name_aliases.csv", dtype=str, keep_default_na=False)
    applied_ds3 = set(ds3.loc[ds3["Apply"].str.strip().str.lower() == "yes", "Dataset3_Name"].str.casefold())
    editorial = display_aliases[display_aliases["Source"].str.startswith("editorial")]
    overlap = {n.casefold() for n in editorial["Everyday_Name"]} & applied_ds3
    assert not overlap, sorted(overlap)


def test_every_applied_alias_points_at_a_real_note(data, display_aliases):
    known = set(data.notes["Note_Name"])
    applied = display_aliases[display_aliases["Apply"].str.strip().str.lower() == "yes"]
    missing = [(r.Everyday_Name, r.Dataset2_Name) for r in applied.itertuples() if r.Dataset2_Name not in known]
    assert not missing, missing
    assert len(applied) >= 100


def test_recorded_gaps_are_deliberate(display_aliases):
    """A name we cannot answer is written down with its reason rather than guessed at."""
    gaps = display_aliases[display_aliases["Apply"].str.strip().str.lower() == "no"]
    assert len(gaps) >= 10
    assert (gaps["Dataset2_Name"].str.strip() == "").all()
    assert (gaps["Reason"].str.strip() != "").all()


def test_profile_note_columns_mostly_resolve(data):
    """Before the expansion 63 % of the library's note atoms matched a dataset2 material; the books and the
    everyday-name table took it past 90 %. This guards the floor, not the exact figure."""
    known = set(data.notes["Note_Name"])
    atoms = [a.strip() for col in ("Top_Notes", "Middle_Notes", "Base_Notes")
             for cell in data.perfumes[col] for a in str(cell).split(";") if a.strip()]
    assert atoms
    resolved = sum(1 for a in atoms if a in known) / len(atoms)
    assert resolved > 0.90, f"note-atom resolution fell to {resolved:.1%}"


def test_book_archetypes_use_catalogue_names_and_real_layers(data):
    """The five Curtis archetypes used to carry the book's own spellings ('Musk ketone') and placed materials by
    formula size. They now go through the same resolver and dataset2's Volatility_Class as every other profile."""
    known = set(data.notes["Note_Name"])
    arch = data.perfumes[data.perfumes["Perfume_ID"].str.startswith("A")]
    assert len(arch) == 5
    from build_profiles import _layer_map
    layer_of = _layer_map(data.notes)     # the same most-common-class rule the builder used
    atoms, resolved = 0, 0
    for r in arch.itertuples():
        for col, want in (("Top_Notes", "Top"), ("Middle_Notes", "Heart"), ("Base_Notes", "Base")):
            for a in [x.strip() for x in getattr(r, col).split(";") if x.strip()]:
                atoms += 1
                if a not in known:
                    # Curtis' compounded bases and grade spellings ('Muguet base', 'Bergamot Oil FCF') have no
                    # single dataset2 material. The documented fallback files them in the heart, the layer that
                    # makes the weakest claim about a material we cannot look up.
                    assert want == "Heart", f"{r.Profile_Name}: unknown {a!r} was filed under {want}, not Heart"
                    continue
                resolved += 1
                assert layer_of.get(a, want) == want, f"{r.Profile_Name}: {a} is {layer_of[a]}, filed under {want}"
    assert resolved / atoms > 0.75, f"only {resolved}/{atoms} archetype notes resolve"
    # the regression that prompted this: Curtis' own spelling used to survive into the library verbatim
    assert not any("Musk ketone" in str(c) for c in arch["Base_Notes"])
    assert any("Musk Ketone" in str(c) for c in arch["Base_Notes"])


def test_cas_conflicts_were_reported_not_silently_accepted(data):
    """Five book materials have a CAS that dataset2 had already given to a DIFFERENT note — always a natural
    carrying its chief constituent's number ('Cinnamon' holding cinnamaldehyde's 104-55-2). The generator refuses
    to alias onto those and writes them out for a human instead."""
    conflicts = pd.read_csv(ROOT / "data" / "reference" / "note_expansion_cas_conflicts.csv",
                            dtype=str, keep_default_na=False)
    assert len(conflicts) == 5
    assert set(conflicts["Dataset2_Holder"]) == {"Cedarwood", "Cinnamon", "Eucalyptus", "Apple", "Fig Leaf"}
    for r in conflicts.itertuples():
        holders = set(data.notes.loc[data.notes["CAS"] == r.CAS, "Note_Name"])
        # the natural still holds the CAS, and the book material was NOT added under it — adding a second row on a
        # contested number would have grown the shared-CAS hazard instead of reporting it
        assert r.Dataset2_Holder in holders
        assert r.Book_Name not in set(data.notes["Note_Name"]), f"{r.Book_Name} was added despite the conflict"
    # the engine treats the natural as if it were the pure constituent, which is STRICTER than the truth — the
    # defect can only make a formula over-cautious, never unsafe. That is why it is a report, not a blocker.
