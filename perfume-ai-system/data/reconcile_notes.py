"""Reconcile dataset3 (accords) note names against dataset2 (notes) — Rule 10 of CLAUDE.md.

    python data/reconcile_notes.py            # print the reconciliation table, refresh note_name_aliases.csv

Every accord note must exist in dataset2 by name. This script finds the names that do not,
proposes the closest dataset2 name for each, scores the proposal, and writes the result to
`note_name_aliases.csv`, which `build_datasets.build_accords()` applies at build time.

Tiers (column `Tier`):
  AUTO      confidence >= 0.90 and unambiguous  -> Apply=Yes written automatically
  REVIEW    plausible but a material/grade/CAS difference or several candidates -> Apply=No, human decides
  NO_MATCH  nothing plausible in dataset2       -> Apply=No; the note must be ADDED to dataset2

Rows whose `Decided_By` is `human` are never overwritten by a re-run; everything else is
regenerated. Deterministic: same CSVs -> same table. No LLM anywhere.

Matching is name-based (Rule 10) but every decision is *checked* against dataset2's own
metadata (CAS, Chemical_Name) — e.g. "Benzaldehyde" maps to dataset2 "Almond" only because
that row's Chemical_Name is "Benzaldehyde" and its CAS is 100-52-7.
"""
from __future__ import annotations

import difflib
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
NOTES_CSV = HERE / "dataset2_notes.csv"
ACCORDS_CSV = HERE / "dataset3_accords.csv"
ALIASES_CSV = HERE / "note_name_aliases.csv"

AUTO_MIN = 0.90          # Apply=Yes at or above this, when unambiguous
REVIEW_MIN = 0.60        # below this -> NO_MATCH
FUZZY_MIN = 0.85         # string similarity needed before a fuzzy hit is even shown as REVIEW

# Tokens that describe a preparation grade of the same botanical, not a different material.
GRADE_TOKENS = {"oil", "essential", "eo", "absolute", "abs", "co2", "extract", "resin", "resinoid",
                "concrete", "butter", "tincture", "crystals", "crystal"}
# Dosage / usage-level qualifiers found in accord names ("Cade Oil (Low)", "Geosmin Trace").
DOSAGE_TOKENS = {"low", "high", "trace", "traces"}
# Tokens that mark an accord / base / reconstitution rather than a single material.
ACCORD_TOKENS = {"accord", "note", "base", "replacer", "synthetic", "blend", "reconstitution"}

# Documented perfumery synonyms, applied token-wise to BOTH sides before comparing.
# (source: standard trade usage — olibanum is the Latin/trade name of frankincense (Boswellia);
#  orris is the rhizome of Iris pallida/germanica; phenyl ethyl alcohol == phenethyl alcohol, CAS 60-12-8)
SYNONYMS = [
    (r"\bolibanum\b", "frankincense"),
    (r"\biris\b", "orris"),
    (r"\bphenyl ethyl\b", "phenethyl"),
]

# Reference CAS numbers for single chemicals / oils named in dataset3 but not in dataset2.
# Used ONLY to confirm a match against a dataset2 row that carries the same CAS — never to invent one.
REFERENCE_CAS = {
    "benzaldehyde": ("100-52-7", "benzaldehyde CAS 100-52-7"),
    "hexyl acetate": ("142-92-7", "hexyl acetate CAS 142-92-7"),
    "eucalyptol": ("470-82-6", "eucalyptol (1,8-cineole) CAS 470-82-6"),
    "menthol": ("89-78-1", "menthol CAS 89-78-1"),
    "gamma undecalactone": ("104-67-6", "gamma-undecalactone (Aldehyde C-14 so-called) CAS 104-67-6"),
    "gamma nonalactone": ("104-61-0", "gamma-nonalactone (Aldehyde C-18 so-called) CAS 104-61-0"),
    "phenethyl alcohol": ("60-12-8", "phenethyl alcohol CAS 60-12-8"),
    "peppermint oil": ("8006-90-4", "peppermint oil (Mentha piperita) CAS 8006-90-4"),
    "ambrette seed oil": ("8015-62-1", "ambrette seed oil (Abelmoschus moschatus) CAS 8015-62-1"),
    "geosmin": ("19700-21-1", "geosmin CAS 19700-21-1"),
    "costus oil": ("8023-88-9", "costus root oil CAS 8023-88-9"),
}

# Human-facing hints for REVIEW / NO_MATCH rows. They never change Apply — they tell the reviewer
# what the honest options are. (recommended dataset2 name or None, hint)
HINTS: dict[str, tuple[str | None, str]] = {
    "Vanilla Absolute": (None, "dataset2 'Vanilla' is a vanillin stand-in (121-33-5). Vanilla absolute is a natural "
                               "(CAS 8024-06-4) — add it to dataset2 rather than conflate 15 accord rows with vanillin."),
    "Cinnamon Bark Oil": (None, "DO NOT map to Cinnamon Leaf Oil: bark is ~70% cinnamic aldehyde (cap 0.3%) vs leaf "
                                "(cap 2%). safety_caps.csv already has a Cinnamon Bark Oil row — add the note to dataset2."),
    "Cinnamon Bark": (None, "same as Cinnamon Bark Oil — add to dataset2, never map to leaf."),
    "Cinnamon Oil": (None, "unspecified cinnamon oil: bark and leaf differ 6x in IFRA outcome. Ask the accord author; "
                           "if unknown, map to Cinnamon Bark Oil once added (conservative)."),
    "Clove Oil": ("Clove Bud Oil", "unspecified clove oil is bud oil in perfumery practice; dataset2 'Clove' is a eugenol stand-in."),
    "Costus Root": ("Costus", "costus is a root-only material; dataset2 'Costus' (8023-88-9) is the root oil. "
                              "UK/EU-banned — mapping it lets Zone B REJECT correctly."),
    "Frankincense Resin": ("Olibanum Resinoid", "resin ~ resinoid (Boswellia extract 89957-98-2); 'Frankincense' (8016-36-2) is the oil CAS."),
    "Myrrh Absolute": ("Myrrh", "Myrrh / Myrrh Resin / Myrrh Resinoid share 9000-45-7 (gum); Myrrh Oil is 8016-37-3."),
    "Patchouli Absolute": ("Patchouli Oil", None),
    "Sandalwood Mysore": ("Sandalwood", "Mysore = Santalum album (8006-87-9) = dataset2 'Sandalwood'; not Australian (S. spicatum)."),
    "Orris Concrete": ("Orris Butter", "orris butter IS the concrete (beurre d'iris); dataset2 Orris Butter 8002-73-1."),
    "Orris Resinoid": ("Orris Absolute", "resinoid ~ absolute grade; note Orris Absolute's CAS 8001-82-7 fails the checksum (Step 2)."),
    "Oakwood Extract": ("Oakwood Absolute", "extract vs absolute grade of the same material (91770-28-4)."),
    "Pink Pepper CO₂": ("Pink Pepper Oil", "dataset2 'Pink Pepper' carries 8015-91-6 (cinnamon leaf oil's CAS — a dataset2 defect); "
                                            "Pink Pepper Oil is what the accords already use (Step 2 fixes its CAS)."),
    "Civet Replacer": ("Civet (Synthetic)", "dataset2 uses 'Replacer' and '(Synthetic)' interchangeably (Ambergris Replacer, Musk (Synthetic))."),
    "White Musk": ("Musk (Synthetic)", "dataset2 'Musk (Synthetic)' is Galaxolide 1222-05-5 — the archetypal white musk."),
    "Powdery Musk": ("Musk (Synthetic)", "no dedicated powdery musk in dataset2; Galaxolide is the generic."),
    "Oud Accord": ("Oud Synthetic", "accord == reconstitution; dataset2 'Oud Synthetic' is the agarwood replacer (no CAS)."),
    "Ambergris Accord": ("Ambergris Replacer", "accord == reconstitution (Ambroxide blend, no CAS); 'Ambergris' is ambrein."),
    "Castoreum Accord": ("Castoreum Replacer", "accord == reconstitution; dataset3 already uses Castoreum Replacer 10x."),
    "Fig Leaf Accord": ("Fig Leaf Base", "accord == base (cis-3-hexenol blend, no CAS)."),
    "Rice Accord": ("Rice Steam Note", None),
    "Rice Powder Accord": ("Rice Steam Note", "powdery rice is closer to an iris/heliotrope accord; weak match."),
    "Gardenia Accord": ("Gardenia Absolute", "accord vs natural absolute (8006-71-5 fails checksum — Step 2)."),
    "Passionfruit Accord": ("Passionfruit Sulfide", "accord vs its key molecule blend."),
    "Mango Accord": ("Mango Lactone", "accord vs its key lactone."),
    "Green Mango Accord": ("Mango Lactone", "weak: green mango is greener/sulfurous."),
    "Apricot Accord": ("Apricot Lactone", "accord vs its key lactone (γ-octalactone 104-50-7)."),
    "Sugar Accord": ("Toasted Sugar", "dataset2 'Toasted Sugar' is cyclotene 80-71-7; also Maltol / Ethyl Maltol / Furaneol exist."),
    "Burnt Sugar Accord": ("Toasted Sugar", None),
    "Caramel Accord": ("Toasted Sugar", "or Ethyl Maltol / Furaneol — author's choice."),
    "Caramel Note": ("Toasted Sugar", None),
    "Strawberry": ("Strawberry Furanone", "or Aldehyde C16 Strawberry (77-83-8); the accord author should pick."),
    "Green Apple": ("Apple", "dataset2 'Apple' is hexyl acetate; green apple is usually a different ester set."),
    "Wormwood Accord": ("Artemisia Oil", "wormwood = Artemisia absinthium; dataset2 Artemisia Oil carries 8008-93-3 (and a bad 8007-43-2)."),
    "Peach Lactone": ("Aldehyde C-14", "'peach lactone' usually means γ-undecalactone 104-67-6 (Aldehyde C-14), sometimes γ-decalactone."),
    "Aldehyde C-12": ("Aldehyde C12 Lauric", "unqualified 'C-12' is lauric (dodecanal 112-54-9) by convention; MNA is always spelt out."),
    "Aldehydes": (None, "generic 'aldehydes' = the classic C10/C11/C12 trio; pick one or split the accord row."),
    "Violet Ionone": ("Ionone Alpha", "violet = ionones; α (127-41-3) is the classic violet, β (79-77-6) woodier; Methyl Ionone also present."),
    "Violet Ionones": ("Ionone Alpha", "as Violet Ionone."),
    "Violet": (None, "violet FLOWER note (ionone accord) — dataset2 only has Violet Leaf (a green note). Add or map to an ionone."),
    "Honey Accord": ("Honey", "dataset2 'Honey' is phenylacetic-acid-rich; its CAS 8006-66-2 fails the checksum (Step 2)."),
    "Saffron Accord": ("Saffron", "dataset2 'Saffron' is a safranal stand-in (116-26-7) — fine for an accord."),
    "Musk": ("Musk (Synthetic)", None),
    "Lily of the Valley": (None, "no muguet note in dataset2 (only single molecules: Hydroxycitronellal, Lilial, Lyral, Bourgeonal, Florol)."),
    "Ozonic Accord": (None, "dataset2 has Calone / Floralozone / Aquozone / Melonal but no generic ozonic base."),
    "Amber Accord": (None, "no generic 'Amber' in dataset2; candidates Ambermarine Base / Ambroxan / Cetalox — author's choice."),
    "Amberwood": (None, "trade-style generic; candidates Timber Silk / Iso E Super / Ambroxan — author's choice."),
}


# ----------------------------------------------------------------------------
# normalisation
# ----------------------------------------------------------------------------

def base_norm(s: str) -> str:
    """NFKC (CO₂ -> CO2), unify quotes/dashes, casefold, collapse whitespace."""
    s = unicodedata.normalize("NFKC", str(s or ""))
    s = s.replace("’", "'").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip().casefold()


def apply_synonyms(s: str) -> str:
    for pat, rep in SYNONYMS:
        s = re.sub(pat, rep, s)
    return s


def key(s: str, *, synonyms: bool = True) -> str:
    """Comparison key: base_norm + hyphens next to digits removed ('C-12'->'c12'), other hyphens -> space,
    punctuation dropped (parentheses kept), synonyms applied."""
    s = base_norm(s)
    s = re.sub(r"(?<=[a-z])-(?=\d)|(?<=\d)-(?=[a-z])", "", s)
    s = s.replace("-", " ").replace("/", " ")
    s = re.sub(r"[,.;:'\"]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return apply_synonyms(s) if synonyms else s


def strip_paren(s: str) -> str:
    return re.sub(r"\s*\([^)]*\)", "", s).strip()


def tokens(s: str) -> list[str]:
    return key(s).split()


def _strip_trailing(toks: list[str], vocab: set[str]) -> list[str]:
    toks = list(toks)
    while toks and toks[-1] in vocab:
        toks.pop()
    return toks


def key_no_dosage(s: str) -> str:
    """Remove '(Low)' / trailing 'Trace' style qualifiers."""
    toks = key(strip_paren_if(s, DOSAGE_TOKENS)).split()
    return " ".join(_strip_trailing(toks, DOSAGE_TOKENS))


def strip_paren_if(s: str, vocab: set[str]) -> str:
    """Remove a parenthetical only when its content is in `vocab` (so '(Orris)' survives, '(Low)' goes)."""
    def repl(m):
        return "" if key(m.group(1)) in vocab else m.group(0)
    return re.sub(r"\s*\(([^)]*)\)", repl, s).strip()


def core(s: str) -> str:
    """Botanical core: parentheticals, dosage and grade suffixes removed. 'Myrrh Resinoid' -> 'myrrh'."""
    toks = key(strip_paren(s)).split()
    toks = _strip_trailing(toks, GRADE_TOKENS | DOSAGE_TOKENS)
    return " ".join(toks)


def core_accord(s: str) -> str:
    toks = core(s).split()
    toks = [t for t in toks if t not in ACCORD_TOKENS]
    return " ".join(toks)


def singular(s: str) -> str:
    toks = key(s).split()
    if toks and toks[-1].endswith("s") and len(toks[-1]) > 3:
        toks[-1] = toks[-1][:-1]
    return " ".join(toks)


# ----------------------------------------------------------------------------
# matching
# ----------------------------------------------------------------------------

@dataclass
class Candidate:
    name: str
    cas: set[str]
    chemical_names: set[str]
    note_id: str
    d3_uses: int


@dataclass
class Match:
    d3_name: str
    d2_name: str | None
    confidence: float
    tier: str
    rule: str
    reason: str
    candidates: list[str] = field(default_factory=list)
    note: str = ""


def _load() -> tuple[pd.DataFrame, pd.DataFrame]:
    notes = pd.read_csv(NOTES_CSV, dtype=str, keep_default_na=False)
    accords = pd.read_csv(ACCORDS_CSV, dtype=str, keep_default_na=False)
    return notes, accords


def _original_names(accords: pd.DataFrame) -> pd.DataFrame:
    """dataset3 may already carry Source_Note_Name from a previous build — always reconcile the
    ORIGINAL workbook names, otherwise applied aliases would vanish from the table on the next run."""
    if "Source_Note_Name" in accords.columns:
        accords = accords.copy()
        accords["Note_Name"] = accords["Source_Note_Name"].where(accords["Source_Note_Name"] != "", accords["Note_Name"])
    return accords


def _catalogue(notes: pd.DataFrame, accords: pd.DataFrame) -> dict[str, Candidate]:
    uses = accords["Note_Name"].value_counts()
    cat: dict[str, Candidate] = {}
    for name, g in notes.groupby("Note_Name", sort=True):
        cas = {c for c in g["CAS"] if c and c.strip() not in {"-", "n/a", "na", "none", "unknown", "?"}}
        cat[name] = Candidate(name=name, cas=cas, chemical_names={key(c) for c in g["Chemical_Name"] if c},
                              note_id=g["Note_ID"].iloc[0], d3_uses=int(uses.get(name, 0)))
    return cat


def _standin_of(cand: Candidate, cat: dict[str, Candidate]) -> str | None:
    """If `cand` shares its CAS with another dataset2 note that is literally the molecule named in
    cand.Chemical_Name (e.g. Vanilla = Vanillin, 121-33-5), return that note's name."""
    for other in cat.values():
        if other.name != cand.name and other.cas and other.cas == cand.cas and key(other.name) in cand.chemical_names:
            return other.name
    return None


def _pick(cands: list[Candidate], d3_name: str) -> Candidate:
    """Deterministic tie-break among candidates that share one CAS: exact Chemical_Name match first,
    then the name dataset3 already uses most, then shortest, then alphabetical."""
    k = key(d3_name)
    return sorted(cands, key=lambda c: (k not in c.chemical_names, -c.d3_uses, len(c.name), c.name))[0]


def _resolve(d3_name: str, cands: list[Candidate], conf: float, rule: str, reason: str,
             cat: dict[str, Candidate]) -> Match:
    """Turn a candidate list into a Match, demoting to REVIEW when the choice is not unambiguous."""
    names = [c.name for c in cands]
    cas_sets = [frozenset(c.cas) for c in cands]
    if len(cands) == 1 or (all(cs for cs in cas_sets) and len(set(cas_sets)) == 1):
        pick = _pick(cands, d3_name)
        if len(cands) > 1:
            reason += f"; {len(cands)} dataset2 names share CAS {'/'.join(sorted(pick.cas))} — chose the one dataset3 already uses"
        standin = _standin_of(pick, cat)
        natural_grade = bool(set(tokens(d3_name)) & (GRADE_TOKENS - {"crystals", "crystal"}))
        if standin and natural_grade and rule not in {"chemical_name", "reference_cas"}:
            return Match(d3_name, pick.name, 0.75, "REVIEW", rule,
                         reason + f"; but dataset2 '{pick.name}' is a stand-in for the molecule {standin} "
                                  f"(same CAS) while '{d3_name}' names a natural grade", names)
        tier = "AUTO" if conf >= AUTO_MIN else "REVIEW"
        return Match(d3_name, pick.name, conf, tier, rule, reason, names)
    # several candidates with different chemistry
    hint = HINTS.get(d3_name)
    rec = hint[0] if hint and hint[0] in names else _pick(cands, d3_name).name
    return Match(d3_name, rec, min(conf, 0.65), "REVIEW", rule,
                 reason + f"; {len(cands)} dataset2 candidates with different CAS — human must choose", names)


def _names_related(a: str, b: str) -> bool:
    """A dataset2 CAS can be wrong (Bitter Orange Oil carries peppermint's 8006-90-4), so a CAS hit must
    also be name-consistent: some non-grade word of one name occurs inside the other."""
    ta = [t for t in tokens(a) if t not in GRADE_TOKENS]
    tb = [t for t in tokens(b) if t not in GRADE_TOKENS]
    ka, kb = " ".join(ta), " ".join(tb)
    return any(t in kb for t in ta) or any(t in ka for t in tb)


def match_name(d3_name: str, cat: dict[str, Candidate]) -> Match:
    by_key: dict[str, list[Candidate]] = {}
    for c in cat.values():
        by_key.setdefault(key(c.name), []).append(c)

    def find(fn_d3, fn_d2) -> list[Candidate]:
        target = fn_d3(d3_name)
        if not target:
            return []
        return [c for c in cat.values() if fn_d2(c.name) == target]

    synonym_used = apply_synonyms(key(d3_name, synonyms=False)) != key(d3_name, synonyms=False)
    syn_note = " (via documented synonym)" if synonym_used else ""
    cap = 0.95 if synonym_used else 1.0

    # R1 exact after normalisation (unicode, case, hyphen/space, punctuation)
    c = find(key, key)
    if c:
        return _resolve(d3_name, c, min(1.00, cap), "exact_normalized",
                        "identical after trimming, case-folding, unicode (CO₂→CO2) and hyphen normalisation" + syn_note, cat)
    # R2 spacing variant ("Guaiac Wood" / "Guaiacwood")
    c = find(lambda s: key(s).replace(" ", ""), lambda s: key(s).replace(" ", ""))
    if c:
        return _resolve(d3_name, c, min(0.95, cap), "spacing_variant", "identical once spaces are removed" + syn_note, cat)
    # R3 word order ("Pepper Black" / "Black Pepper")
    c = find(lambda s: " ".join(sorted(tokens(s))), lambda s: " ".join(sorted(tokens(s))))
    if c:
        return _resolve(d3_name, c, min(0.95, cap), "word_order", "same words in a different order" + syn_note, cat)
    # R4 plural / singular
    c = find(singular, singular)
    if c:
        return _resolve(d3_name, c, min(0.95, cap), "plural_variant", "singular/plural spelling variant" + syn_note, cat)
    # R5 dosage qualifier "(Low)", "Trace"
    c = find(key_no_dosage, key)
    if c and key_no_dosage(d3_name) != key(d3_name):
        return _resolve(d3_name, c, min(0.95, cap), "dosage_qualifier",
                        "usage-level qualifier removed — same material, the level is set by the formula builder" + syn_note, cat)
    # R6 parenthetical qualifier ("Iris" / "Iris (Orris)", "Musk" / "Musk (Synthetic)")
    c = find(lambda s: key(strip_paren(s)), lambda s: key(strip_paren(s)))
    if c:
        return _resolve(d3_name, c, min(0.90, cap), "parenthetical_qualifier",
                        "identical once the parenthetical qualifier is removed" + syn_note, cat)
    # R7 dataset3 name IS a dataset2 row's Chemical_Name ("Benzaldehyde" -> Almond)
    k_chem = " ".join(_strip_trailing(tokens(d3_name), {"crystals", "crystal"}))
    c = [cand for cand in cat.values() if k_chem in cand.chemical_names]
    if c:
        exact = [cand for cand in c if k_chem in cand.chemical_names]
        return _resolve(d3_name, exact, 0.95, "chemical_name",
                        f"dataset2 row's Chemical_Name is '{k_chem}' — the same substance" + syn_note, cat)
    # R8 reference CAS confirms a dataset2 row
    ref = REFERENCE_CAS.get(k_chem) or REFERENCE_CAS.get(key(d3_name))
    if ref:
        c = [cand for cand in cat.values() if ref[0] in cand.cas and _names_related(d3_name, cand.name)]
        if c:
            return _resolve(d3_name, c, 0.95, "reference_cas",
                            f"{ref[1]} — dataset2 row carries the same CAS" + syn_note, cat)
    # R9 grade suffix (Oil / Absolute / CO2 / Extract / Resin …) added or removed
    c = find(core, core)
    if c and core(d3_name):
        d3_grade = [t for t in tokens(strip_paren(d3_name)) if t in GRADE_TOKENS]
        return _resolve(d3_name, c, 0.90, "grade_suffix",
                        f"same botanical; grade suffix differs ({'/'.join(d3_grade) or 'none'} in dataset3)" + syn_note, cat)
    # R10 accord / base / replacer suffix
    c = find(core_accord, core_accord)
    if c and core_accord(d3_name):
        is_base = [cand for cand in c if not cand.cas or set(tokens(cand.name)) & ACCORD_TOKENS]
        if len(c) == 1 and is_base:
            return _resolve(d3_name, c, 0.85, "accord_to_base",
                            "accord/base suffix differs; dataset2 entry is itself a base (no CAS)", cat)
        if len(c) == 1:
            return _resolve(d3_name, c, 0.80, "accord_to_material",
                            f"accord suffix removed; dataset2 '{c[0].name}' is a material with a CAS "
                            f"(Chemical_Name: {'/'.join(sorted(c[0].chemical_names)) or 'none'})", cat)
        return _resolve(d3_name, c, 0.70, "accord_ambiguous", "accord suffix removed", cat)
    # R11 fuzzy fallback — never applied automatically
    keys = list(by_key)
    scored = sorted(((difflib.SequenceMatcher(None, key(d3_name), k2).ratio(), k2) for k2 in keys), reverse=True)[:3]
    top = [by_key[k2][0].name for _, k2 in scored]
    best = scored[0][0] if scored else 0.0
    hint = HINTS.get(d3_name)
    if best >= FUZZY_MIN:
        return Match(d3_name, hint[0] if hint and hint[0] else top[0], round(best * 0.75, 2), "REVIEW", "fuzzy",
                     f"string similarity {best:.2f} only — no rule matched", top)
    if hint and hint[0] and hint[0] in cat:
        return Match(d3_name, hint[0], 0.60, "REVIEW", "domain_hint",
                     "no rule matched; a documented perfumery convention suggests a candidate — human must confirm", top)
    return Match(d3_name, None, round(best * 0.5, 2), "NO_MATCH", "none",
                 "no dataset2 name is the same material — add the note to dataset2 (needs CAS + Volatility_Class)", top)


def reconcile(notes: pd.DataFrame | None = None, accords: pd.DataFrame | None = None) -> pd.DataFrame:
    if notes is None or accords is None:
        notes, accords = _load()
    accords = _original_names(accords)
    cat = _catalogue(notes, accords)
    d2_names = set(notes["Note_Name"])
    counts = accords["Note_Name"].value_counts()
    unmatched = sorted(n for n in counts.index if n not in d2_names)   # Rule 10: names must match EXACTLY

    rows = []
    for name in unmatched:
        m = match_name(name, cat)
        hint = HINTS.get(name)
        if hint and m.tier != "AUTO":
            if hint[0] and hint[0] in cat:
                m.d2_name = hint[0]
            if hint[1]:
                m.note = hint[1]
        rows.append({
            "Dataset3_Name": name,
            "Dataset2_Name": m.d2_name or "",
            "Dataset2_Note_ID": cat[m.d2_name].note_id if m.d2_name in cat else "",
            "Dataset2_CAS": "|".join(sorted(cat[m.d2_name].cas)) if m.d2_name in cat else "",
            "Confidence": f"{m.confidence:.2f}",
            "Tier": m.tier,
            "Rule": m.rule,
            "Reason": m.reason,
            "Candidates": "; ".join(m.candidates),
            "Rows_In_Accords": int(counts[name]),
            "Apply": "Yes" if m.tier == "AUTO" else "No",
            "Decided_By": "auto",
            "Note": m.note,
        })
    out = pd.DataFrame(rows)
    order = {"AUTO": 0, "REVIEW": 1, "NO_MATCH": 2}
    if len(out):
        out = out.sort_values(["Tier", "Rows_In_Accords", "Dataset3_Name"],
                              key=lambda s: s.map(order) if s.name == "Tier" else (-s if s.name == "Rows_In_Accords" else s)
                              ).reset_index(drop=True)
    return out


def merge_with_existing(fresh: pd.DataFrame, existing_path: Path = ALIASES_CSV) -> pd.DataFrame:
    """Keep every row a human has decided; regenerate the rest."""
    if not existing_path.exists():
        return fresh
    old = pd.read_csv(existing_path, dtype=str, keep_default_na=False)
    human = old[old["Decided_By"].str.lower().isin(["human", "ai"])]     # decided rows (human or AI) survive re-runs
    keep = fresh[~fresh["Dataset3_Name"].isin(set(human["Dataset3_Name"]))]
    merged = pd.concat([human[fresh.columns.intersection(human.columns)], keep], ignore_index=True)
    return merged


def to_markdown(df: pd.DataFrame) -> str:
    lines = []
    for tier, title in (("AUTO", "AUTO — applied"), ("REVIEW", "REVIEW — needs human decision"),
                        ("NO_MATCH", "NO MATCH — add to dataset2")):
        sub = df[df["Tier"] == tier]
        lines.append(f"\n### {title} ({len(sub)} names, {int(sub['Rows_In_Accords'].astype(int).sum())} accord rows)\n")
        lines.append("| dataset3 name | rows | dataset2 match | conf | rule | reason |")
        lines.append("|---|---:|---|---:|---|---|")
        for r in sub.itertuples(index=False):
            reason = r.Reason + (f" **→ {r.Note}**" if r.Note else "")
            lines.append(f"| {r.Dataset3_Name} | {r.Rows_In_Accords} | {r.Dataset2_Name or '—'} | {r.Confidence} | {r.Rule} | {reason} |")
    return "\n".join(lines)


def main() -> int:
    fresh = reconcile()
    merged = merge_with_existing(fresh)
    merged.to_csv(ALIASES_CSV, index=False, encoding="utf-8")
    print(to_markdown(merged))
    n_auto = (merged["Tier"] == "AUTO").sum()
    n_rev = (merged["Tier"] == "REVIEW").sum()
    n_no = (merged["Tier"] == "NO_MATCH").sum()
    print(f"\n{len(merged)} unmatched names: {n_auto} AUTO (applied), {n_rev} REVIEW, {n_no} NO_MATCH  -> {ALIASES_CSV.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
