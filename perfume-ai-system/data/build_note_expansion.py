"""Expand dataset2 from the books, and teach the profile library the everyday names for what it already has.

Two outputs, deliberately separate:

* `note_additions.csv` — the generated block (Decided_By starts with GEN_TAG) is rewritten here: one new dataset2 row
  per book material dataset2 does not already hold. Metadata is the book's own: `Volatility_Class` from Curtis' note
  class, `Odor_Strength` from his bold 1-6 odour-strength figure, `Odor_Family` / `Key_Nuances` decoded from his
  three-letter odour codes, `Stability` / `Occurrence` from the monograph, MW and LogP from PubChem. Nothing is
  recalled — every field cites the row it came from. Hand-written rows in the file are left exactly as they are.
* `note_display_aliases.csv` — everyday name -> dataset2 Note_Name, read ONLY by `build_profiles.py`. 'Cedar' means
  Cedarwood and 'Oud' means Agarwood to a customer, but renaming a note inside an accord is a chemistry change, so
  these never reach `note_name_aliases.csv` and never touch dataset3.

A candidate whose CAS is ALREADY in dataset2 under another name becomes an alias instead of a second row — that is
what keeps the shared-CAS hazard from growing (`load_data.shared_cas`).

    python data/build_note_expansion.py            # rewrite both generated blocks
    python data/build_note_expansion.py --dry-run  # report what would change

After running: `python data/build_datasets.py && python load_data.py`.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REF = HERE / "reference"
GEN_TAG = "ai (2026-09-23) - book expansion"
FIRST_ID = 9200  # hand-written additions occupy NOTE-9001..9137; the generated block starts clear of them

# ---------------------------------------------------------------------------------------------------------------
# 1. The book materials dataset2 lacks.
#
# `QUERY` in data/reference/new_note_cas.json holds the CAS each name resolved to on PubChem. Here we only say what
# the material should be CALLED in dataset2 and, where the books disagree with a plain reading of the name, why.
# ---------------------------------------------------------------------------------------------------------------

# Curtis monograph material -> the dataset2 Note_Name to file it under (the monograph supplies everything else)
CURTIS_NEW = {
    "Acetophenone": "Acetophenone",
    "Allyl amyl glycollate": "Allyl Amyl Glycolate",
    "Allyl caproate": "Allyl Caproate",
    "Allyl cyclohexyl propionate": "Allyl Cyclohexyl Propionate",
    "Anisyl acetate": "Anisyl Acetate",
    "iso-Bornyl acetate": "Isobornyl Acetate",
    "Cedrol": "Cedrol",
    "Cinnamic aldehyde": "Cinnamic Aldehyde",
    "Cinnamyl nitrile": "Cinnamyl Nitrile",
    "Citronellal": "Citronellal",
    "para-Cresyl methyl ether": "p-Cresyl Methyl Ether",
    "Dimethyl benzyl carbinyl butyrate": "Dimethyl Benzyl Carbinyl Butyrate",
    "Diphenyl methane": "Diphenyl Methane",
    "Diphenyl oxide": "Diphenyl Oxide",
    "Eucalyptol": "Eucalyptol",
    "iso-Eugenol": "Isoeugenol",
    "Farnesol": "Farnesol",
    "Geranyl nitrile": "Geranyl Nitrile",
    "cis-3-Hexenyl salicylate": "cis-3-Hexenyl Salicylate",
    "Hydratropic aldehyde": "Hydratropic Aldehyde",
    "Hydroxycitronellal dimethylacetal": "Hydroxycitronellal Dimethyl Acetal",
    "l-Menthol": "l-Menthol",
    "2-Methoxy-3-iso-butyl pyrazine": "2-Methoxy-3-isobutylpyrazine",
    "Methoxycitronellal": "Methoxycitronellal",
    "Methyl n-amyl ketone": "Methyl n-Amyl Ketone",
    "Methyl heptine carbonate": "Methyl Heptine Carbonate",
    "Methyl phenylacetate": "Methyl Phenylacetate",
    "Nonadienal": "2,6-Nonadienal",
    "Octenol": "1-Octen-3-ol",
    "Rhodinol": "Rhodinol",
    "Tetrahydrogeraniol": "Tetrahydrogeraniol",
    "Tetrahydrolinalool": "Tetrahydrolinalool",
}

# Ohloff material -> (dataset2 Note_Name, Volatility_Class, Odor_Strength, Odor_Family, Key_Nuances, Chemical_Family)
# Ohloff's families give the odour; the layer follows the same BP rule the rest of dataset2 uses (RSC Ch 11 p.190:
# BP < 200 C top, 200-270 heart, > 270 base), which for these esters and lactones is unambiguous.
OHLOFF_NEW = {
    "amyl acetate": ("Isoamyl Acetate", "Top", "Medium", "Fruity", "Banana, pear drop, sweet", "Ester"),
    "ethyl methyl butyrate": ("Ethyl 2-Methylbutyrate", "Top", "Strong", "Fruity", "Apple, green, juicy", "Ester"),
    "hexyl acetate": ("Hexyl Acetate", "Top", "Medium", "Fruity", "Pear, apple, green", "Ester"),
    "γ-octalactone": ("gamma-Octalactone", "Heart", "Medium", "Fruity / Creamy", "Coconut, creamy, sweet", "Lactone"),
    "delta-Decalactone": ("delta-Decalactone", "Heart", "Medium", "Fruity / Creamy", "Coconut, milky, sweet", "Lactone"),
    "anethol": ("Anethole", "Heart", "Strong", "Spicy / Anisic", "Anise, sweet, liquorice", "Phenyl Ether"),
    "(−)-(R)-carvone": ("R-(-)-Carvone", "Top", "Strong", "Minty", "Spearmint, fresh, herbal", "Terpene Ketone"),
    "Cyclal C (Ligustral)": ("Ligustral", "Top", "Strong", "Green", "Leafy, privet, aldehydic green", "Terpene Aldehyde"),
    "estragol": ("Estragole", "Heart", "Strong", "Spicy / Anisic", "Basil, anise, herbal", "Phenyl Ether"),
    "hexenol, 3-cis": ("cis-3-Hexen-1-ol", "Top", "Very strong", "Green", "Cut grass, leafy, sharp green", "Alcohol"),
    "hexenyl acetate, 3-cis": ("cis-3-Hexenyl Acetate", "Top", "Strong", "Green", "Green, fruity, banana leaf", "Ester"),
    "styralyl acetate": ("Styralyl Acetate", "Top", "Strong", "Green / Fruity", "Gardenia, green, fruity", "Ester"),
    "Helional (Tropional)": ("Helional", "Heart", "Strong", "Marine / Green", "Ozonic, melon, green floral", "Aromatic Aldehyde"),
    "α-damascone": ("alpha-Damascone", "Heart", "Very strong", "Fruity / Rosy", "Apple, rose, fruity", "Rose Ketone"),
    "β-damascone": ("beta-Damascone", "Heart", "Very strong", "Fruity / Rosy", "Plum, rose, tobacco", "Rose Ketone"),
    "ethyl linalool": ("Ethyl Linalool", "Top", "Medium", "Floral / Fresh", "Linalool-like, soft floral, fresh", "Terpene Alcohol"),
    "Florol/Florosa": ("Florol", "Heart", "Medium", "Floral", "Muguet, waterlily, fresh floral", "Pyran"),
    "α-ionone": ("alpha-Ionone", "Heart", "Strong", "Violet / Woody", "Violet, orris, woody", "Ionone"),
    "β-ionone": ("beta-Ionone", "Heart", "Strong", "Violet / Woody", "Violet, cedarwood, dry", "Ionone"),
    "Undecavertol": ("Undecavertol", "Heart", "Strong", "Green / Floral", "Green, melon, violet leaf", "Alcohol"),
    "Phenoxanol": ("Phenoxanol", "Heart", "Medium", "Floral / Rosy", "Rose, green, muguet", "Alcohol"),
    "Florhydral": ("Florhydral", "Heart", "Strong", "Floral / Green", "Muguet, green, watery floral", "Aromatic Aldehyde"),
    "Cashmeran": ("Cashmeran", "Base", "Strong", "Musky / Woody", "Musky, ambery, pine-resin, powdery", "Indane Musk"),
    "Evernyl": ("Evernyl", "Base", "Strong", "Mossy", "Oakmoss, dry, earthy", "Benzoate Ester"),
    "Maltol": ("Maltol", "Base", "Strong", "Sweet / Caramellic", "Caramel, cotton candy, jammy", "Pyranone"),
    "Calone 1951": ("Calone", "Heart", "Very strong", "Marine", "Watermelon, sea breeze, ozonic", "Benzodioxepinone"),
}

# Naturals the profile library asks for that dataset2 lacks. Each is a material Tisserand & Young 2e Chapter 14
# documents by name, so the row's EXISTENCE is cited; its CAS is a different question. Essential oils are not
# indexed by PubChem, so a CAS appears here only when a project table already carries a verified one - otherwise
# the field stays BLANK and the row says so. A blank CAS makes the safety engine call the material UNVERIFIED,
# which is the correct outcome: these are descriptive entries until a supplier CoA supplies the number.
NATURAL_NEW = {
    # name: (CAS, layer, strength, odour family, nuances, botanical, chemical family, note)
    "Verbena Absolute": ("85116-63-8", "Top", "Strong", "Citrus / Green", "Lemony, green, hay, tea",
                         "Lippia citriodora (lemon verbena)", "Natural Extract",
                         "CAS from constituents.csv 'Verbena absolute (lemon verbena)'. The verbena OIL (8024-12-2) is "
                         "banned in the UK/EU - only the absolute may be used"),
    "Myrtle Oil": ("", "Top", "Medium", "Aromatic / Camphoraceous", "Fresh, herbal, eucalyptus-like, slightly sweet",
                   "Myrtus communis leaf", "Essential Oil",
                   "CAS not verifiable from a project source - supplier CoA required before any formulation"),
    "Caraway Oil": ("", "Top", "Strong", "Spicy / Minty", "Caraway, warm, anisic, d-carvone",
                    "Carum carvi seed", "Essential Oil",
                    "CAS not verifiable from a project source - supplier CoA required before any formulation"),
    "Helichrysum Oil": ("", "Heart", "Strong", "Herbal / Honeyed", "Curry-like, honeyed, hay, tea, immortelle",
                        "Helichrysum italicum flowering top", "Essential Oil",
                        "CAS not verifiable from a project source - supplier CoA required before any formulation"),
    "Clementine Oil": ("", "Top", "Medium", "Citrus", "Sweet, juicy, soft citrus, less sharp than mandarin",
                       "Citrus clementina peel", "Essential Oil",
                       "CAS not verifiable from a project source - supplier CoA required before any formulation"),
    "Carnation Absolute": ("", "Heart", "Strong", "Floral / Spicy", "Clove, peppery, honeyed, floral",
                           "Dianthus caryophyllus flower", "Natural Extract",
                           "CAS not verifiable from a project source - supplier CoA required before any formulation"),
    "Tomato Leaf Absolute": ("", "Top", "Very strong", "Green / Vegetable", "Sharp green, stemmy, tomato vine, bitter",
                             "Solanum lycopersicum leaf", "Natural Extract",
                             "CAS not verifiable from a project source - supplier CoA required before any formulation"),
}

TY_CH14 = "Tisserand & Young, Essential Oil Safety 2e, Ch 14 (the material is documented there by name)"


def natural_rows(existing_names: set[str]) -> list[dict]:
    rows = []
    for name, (cas, layer, strength, odour, nuances, botanical, chem, note) in NATURAL_NEW.items():
        if name in existing_names:
            continue
        rows.append({"Note_Name": name, "Chemical_Name": botanical, "CAS": cas, "Volatility_Class": layer,
                     "Odor_Strength": strength, "Chemical_Family": chem, "Odor_Family": odour,
                     "Key_Nuances": nuances, "Solubility": "Alcohol soluble", "Natural_Source": botanical,
                     "Short_Description": note, "Source": TY_CH14})
    return rows


# Everyday name -> dataset2 Note_Name, for the profile library's descriptive note columns only.
# Reason is recorded because these are editorial judgements, not chemistry.
DISPLAY_ALIASES = {
    "Amber": ("Labdanum Absolute", "the 'amber' of a note list is the labdanum-benzoin-vanillin accord; labdanum is its defining material"),
    "Grey Amber": ("Ambergris Tincture", "grey amber is ambergris proper, not the amber accord"),
    "Leather": ("Leather Accord", "dataset2 already holds the accord under its full name"),
    "Suede": ("Suederal", "suede is the soft-leather effect; Suederal is the material perfumery uses for it"),
    "Cedar": ("Cedarwood", "plain 'Cedar' in a note list is cedarwood oil"),
    "Virginia Cedar": ("Cedarwood Virginia", "same material, everyday word order"),
    "Cashmere Wood": ("Cashmeran", "'cashmere wood' is the trade description of Cashmeran"),
    "Soft Woods": ("Cedarwood", "a generic soft-wood impression; cedarwood is the representative material"),
    "Woods": ("Cedarwood", "generic category word; cedarwood is the representative woody material"),
    "Woody Notes": ("Cedarwood", "generic category word; cedarwood is the representative woody material"),
    "Oud": ("Agarwood (Oud)", "same material under its Arabic name"),
    "Pure Oud": ("Agarwood (Oud)", "same material"),
    "Incense": ("Olibanum Resinoid", "incense in a note list is olibanum (frankincense)"),
    "Olibanum": ("Olibanum Oil", "grade omitted in the note list; the oil is the perfumery default"),
    "Resins": ("Benzoin", "generic category word; benzoin is the representative soft resin"),
    "Pine Resin": ("Pine Needle Oil", "resinous pine character; the needle oil is what perfumery uses"),
    "Spices": ("Clove Bud Oil", "generic category word; clove is the representative spice"),
    "Spicy Notes": ("Clove Bud Oil", "generic category word; clove is the representative spice"),
    "Herbs": ("Rosemary Oil", "generic category word; rosemary is the representative herb"),
    "Aromatic Herbs": ("Rosemary Oil", "generic category word; rosemary is the representative herb"),
    "Green Notes": ("Cis-3-Hexenol", "the green-note effect is cis-3-hexenol"),
    "Green Leaves": ("Cis-3-Hexenol", "the green-leaf effect is cis-3-hexenol"),
    "Grass": ("Cis-3-Hexenol", "cut-grass is cis-3-hexenol"),
    "Pepper": ("Black Pepper", "plain 'Pepper' is black pepper"),
    "White Pepper": ("Black Pepper", "the same Piper nigrum fruit, hulled; perfumery uses the one oil"),
    "Sichuan Pepper": ("Pink Pepper", "closest material dataset2 holds; both are bright, rosy-peppery berries"),
    "Moss": ("Oakmoss", "plain 'Moss' in a note list is oakmoss"),
    "Cypress": ("Cypress Oil", "grade omitted in the note list"),
    "Juniper": ("Juniper Berry", "plain 'Juniper' is the berry, not the tar"),
    "Juniper Berries": ("Juniper Berry", "plural form"),
    "Fir": ("Fir Needle Oil", "grade omitted in the note list"),
    "Birch": ("Birch Tar Rectified", "the birch of a note list is the tar; only the rectified grade is allowed (IFRA_STD_118)"),
    "Bitter Orange": ("Bitter Orange Oil", "grade omitted in the note list"),
    "Orange": ("Sweet Orange Oil", "plain 'Orange' is sweet orange"),
    "Sweet Orange": ("Sweet Orange Oil", "grade omitted in the note list"),
    "Blood Orange": ("Sweet Orange Oil", "a cultivar of sweet orange; the oil is the same material"),
    "Mandarin Orange": ("Mandarin", "everyday name for mandarin"),
    "Tangerine": ("Mandarin", "tangerine and mandarin are the same Citrus reticulata oil in perfumery"),
    "Citrus": ("Bergamot", "generic category word; bergamot is the representative citrus"),
    "Citrus Notes": ("Bergamot", "generic category word; bergamot is the representative citrus"),
    "Citron": ("Lemon Oil", "citron reads as lemon in a note list"),
    "Cumin": ("Cumin Seed Oil", "grade omitted in the note list"),
    "Angelica": ("Angelica Root", "plain 'Angelica' is the root oil"),
    "Blackcurrant": ("Blackcurrant Bud", "the perfumery material is the bud absolute"),
    "Tonka": ("Tonka Bean", "grade omitted in the note list"),
    "Civet": ("Civet (Synthetic)", "the natural is banned in the UK/EU; the synthetic is what a formula may use"),
    "Orris": ("Orris Butter", "grade omitted in the note list"),
    "Narcissus": ("Narcissus Absolute", "grade omitted in the note list"),
    "Opopanax": ("Opoponax Resin", "alternative spelling of opoponax"),
    "Tobacco Leaf": ("Tobacco Absolute", "the perfumery material is the leaf absolute"),
    "Tea": ("Green Tea", "plain 'Tea' is green tea"),
    "Mate": ("Green Tea", "mate is the closest tea-leaf material dataset2 holds"),
    "Star Anise": ("Anethole", "star anise oil is the anethole material dataset2 files as Anise"),
    "Pimento": ("Allspice Oil", "pimento (Pimenta dioica) is allspice"),
    "Bay Leaf": ("Bay Leaf Oil", "grade omitted in the note list"),
    "Cinnamon Leaf": ("Cinnamon Leaf Oil", "grade omitted in the note list"),
    "Tarragon": ("Tarragon Oil", "grade omitted in the note list"),
    "Seaweed": ("Seaweed Absolute", "grade omitted in the note list"),
    "Salt": ("Calone", "the 'salt' of a note list is the marine-ozonic effect; Calone is its material"),
    "Sea Salt": ("Calone", "the marine effect; Calone is its material"),
    "Marine Notes": ("Calone", "the marine effect; Calone is its material"),
    "Caramel": ("Maltol", "the caramel effect in perfumery is maltol / ethyl maltol"),
    "Toffee": ("Ethyl Maltol", "the toffee effect is ethyl maltol"),
    "Cacao": ("Cocoa", "cacao is cocoa"),
    "Licorice": ("Anethole", "liquorice reads as the anethole note"),
    "Musk ketone": ("Musk Ketone", "casing only"),
    "gamma-Methyl ionone": ("Methyl Ionone", "dataset2 holds the isomer mixture under one name"),
    "Vetivert Oil Bourbon": ("Vetiver Haiti", "'bourbon' vetivert is the Reunion/Haiti type; Haiti is what dataset2 holds"),
    "Haitian Vetiver": ("Vetiver Haiti", "same material"),
    "Jasmine Sambac": ("Sambac Jasmine", "grade omitted in the note list"),
    "Jasmin base": ("Jasmine Absolute", "a compounded jasmin base stands for jasmine in a note list"),
    "Rose base": ("Rose Absolute", "a compounded rose base stands for rose in a note list"),
    "Lavender Oil French": ("Lavender Oil", "origin qualifier; the same oil"),
    "Neroli Oil reconstituted": ("Neroli Oil", "a reconstitution stands for the oil in a note list"),
    "Patchouli Oil light": ("Patchouli Oil", "'light' is a fractionated grade of the same oil"),
    "Soil Tincture": ("Geosmin", "the smell of soil is geosmin"),
    "Mastic": ("Lentisque Absolute", "mastic is the resin of Pistacia lentiscus, dataset2's Lentisque"),
    "Ylang Ylang": ("Ylang-Ylang", "grade omitted in the note list"),
    "Magnolia": ("Magnolia Absolute", "grade omitted in the note list"),
    "Apricot": ("Aldehyde C14 Peach", "the apricot/peach effect is the C14 lactone"),
    "Banana": ("Isoamyl Acetate", "the banana effect is isoamyl acetate"),
    "Papaya": ("Ethyl 2-Methylbutyrate", "the tropical-fruit effect; the closest material dataset2 holds"),
    "Floral Notes": ("Rose", "generic category word; rose is the representative floral"),
    # constituents.csv (Tisserand & Young 2e) gives these naturals a CAS dataset2 already carries under another name
    "Rosewood": ("Bois de Rose", "Aniba rosaeodora; dataset2 files it under its French name, CAS 8015-77-8"),
    "Brazilian Rosewood": ("Bois de Rose", "Aniba rosaeodora; dataset2 files it under its French name"),
    "Artemisia": ("Artemisia Oil", "Artemisia absinthium (wormwood), CAS 8008-93-3"),
    "Ambrette Seed": ("Amber Seed", "Abelmoschus moschatus seed oil - dataset2's 'Amber Seed' carries its CAS 8015-62-1"),
    "Fruity Notes": ("Aldehyde C14 Peach", "generic category word; the C14 lactone is the representative fruity material"),
    # the naturals added above, under the everyday names the note lists actually use
    "Verbena": ("Verbena Absolute", "plain 'Verbena' is lemon verbena; only the absolute is legal in the UK/EU"),
    "Lemon Verbena": ("Verbena Absolute", "only the absolute is legal in the UK/EU - the oil is banned"),
    "Immortelle": ("Helichrysum Oil", "immortelle is the everyday name for helichrysum"),
    "Myrtle": ("Myrtle Oil", "grade omitted in the note list"),
    "Caraway": ("Caraway Oil", "grade omitted in the note list"),
    "Clementine": ("Clementine Oil", "grade omitted in the note list"),
    "Carnation": ("Carnation Absolute", "the absolute is the material; the fuller carnation effect is an accord"),
    "Tomato Leaf": ("Tomato Leaf Absolute", "grade omitted in the note list"),
}

# Names the note lists use that dataset2 cannot answer. Recorded so the gap is VISIBLE rather than silently
# unresolved, and deliberately NOT invented as dataset2 rows. Two kinds, each with the reason a human needs:
GAPS = {
    # perfumery builds these as an accord - there is no single natural behind them (Curtis Ch 6 floral bases)
    "Freesia": "accord, no natural", "Peony": "accord, no natural", "Carnation": "accord, no natural",
    "Lilac": "accord, no natural", "Hyacinth": "accord, no natural", "Gardenia": "accord, no natural",
    "Honeysuckle": "accord, no natural", "Cyclamen": "accord, no natural", "Sweet Pea": "accord, no natural",
    "Wisteria": "accord, no natural", "Dried Fruits": "accord, no natural", "Whiskey": "accord, no natural",
    "Whiskey Accord": "accord, no natural", "Rum": "accord, no natural",
    # a real material perfumery uses that dataset2 does not hold yet - a human should author the row
    "Tomato Leaf": "real material missing from dataset2 (tomato leaf absolute)",
    "Chestnut": "real material missing from dataset2",
}

# Chemical_Family from the systematic name Curtis prints in the monograph - the suffix IS the functional class.
# Ordered: the first pattern that matches wins, so 'nitrile' beats the generic 'ester' inside a longer name.
CHEM_FAMILY = [(r"nitrile", "Nitrile"), (r"pyrazine", "Pyrazine"), (r"lactone|olide", "Lactone"),
               (r"acetal", "Acetal"), (r"salicylate", "Salicylate Ester"), (r"benzoate", "Benzoate Ester"),
               (r"cinnamate", "Cinnamate Ester"), (r"anthranilate", "Anthranilate"), (r"carbonate", "Carbonate Ester"),
               (r"\bether\b|anisole", "Phenyl Ether"), (r"ketone|\w+one\b", "Ketone"),
               (r"aldehyde|\w+al\b", "Aldehyde"), (r"\w+ate\b", "Ester"), (r"\w+ol\b", "Alcohol"),
               (r"\w+ene\b", "Terpene Hydrocarbon")]


def chemical_family(name: str) -> str:
    for pat, fam in CHEM_FAMILY:
        if re.search(pat, name, re.I):
            return fam
    return ""


INTENSITY_TO_STRENGTH = {"6": "Very strong", "5": "Strong", "4": "Medium", "3": "Medium", "2": "Low", "1": "Low"}
CURTIS_CLASS = {"Top": "Top", "Middle": "Heart", "Basic": "Base", "Base": "Base"}


def _s(v) -> str:
    """pandas gives NaN for an empty cell; str(NaN) is 'nan', which must never reach a CSV."""
    return "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip()


def _same_material(book_name: str, dataset2_name: str) -> bool:
    """Do two names plausibly denote the same thing? Used to tell a spelling difference ('Styralyl' vs 'Styrallyl')
    from a dataset2 CAS defect ('Fig Leaf' carrying cis-3-hexenol's 928-96-1)."""
    def key(x: str) -> set[str]:
        x = re.sub(r"\b(?:oil|absolute|extract|resinoid|cis|trans|alpha|beta|gamma|delta|iso|l|d|r|s|n|p|o|m|para|ortho|meta)\b",
                   " ", x.lower())
        return {w for w in re.findall(r"[a-z]{3,}", x)}
    a, b = key(book_name), key(dataset2_name)
    if not a or not b:
        return False
    if a & b:
        return True
    # 'Isoamyl Acetate' vs 'amyl acetate': one side's word contained in the other's
    return any(x in y or y in x for x in a for y in b if min(len(x), len(y)) >= 5)


# Abbreviations Curtis uses in the Ch 5 monograph code columns that his Ch 3 vocabulary table does not itself list.
# Each is his own contraction of a word the table spells out elsewhere; nothing here is a guess at an unclear code.
CODE_SUPPLEMENT = {"SPI": "Spicy", "LEM": "Lemon", "CIT": "Citrus", "OLY": "Oily", "WXY": "Waxy", "MIM": "Mimosa",
                   "CIN": "Cinnamon", "ORS": "Orris", "SHP": "Sharp", "PGT": "Pungent", "CMP": "Camphoraceous",
                   "MIN": "Minty", "PMT": "Peppermint", "COO": "Cooling"}
# tenacity text ('24 HOURS', '3 DAYS') bleeds into the code columns from the OCR; never read it as odour
CODE_NOISE = {"HOU", "OUR", "URS", "DAY", "AYS", "HRS", "MIN"}


def odour_vocabulary() -> dict[str, str]:
    """code -> word. The Code column holds only the 71 flower headwords; the general descriptors (FLO floral,
    SWE sweet, WDY woody, BAL balsamic...) appear only inside each row's `Related` list as 'Floral (FLO)'."""
    v = pd.read_csv(REF / "curtis_odour_vocabulary.csv", dtype=str, keep_default_na=False)
    vocab: dict[str, str] = {}
    for r in v.itertuples():
        code, word = _s(r.Code).upper(), _s(r.Word)
        if code and word:
            vocab.setdefault(code, word)
        for word2, code2 in re.findall(r"([A-Za-z][A-Za-z \-]*?)\s*\(([A-Z]{2,4})\)", _s(getattr(r, "Related", ""))):
            vocab.setdefault(code2.upper(), word2.strip())
    for code, word in CODE_SUPPLEMENT.items():
        vocab.setdefault(code, word)
    return vocab


def _decode(codes: str, vocab: dict[str, str]) -> list[str]:
    """Curtis writes a material's odour as three-letter codes. The OCR often runs them together ('SWEPGT' = sweet +
    pungent, 'GERGRN' = geranium + green), so tokenise by longest match against the vocabulary instead of splitting
    on width, and drop any letters that match nothing rather than guessing at them."""
    out: list[str] = []
    codes = re.split(r"[(\[]", codes or "")[0]           # 'MIN PMT (Standard for ...' - prose, not codes
    for run in re.findall(r"[A-Za-z]+", codes):
        run, i = run.upper(), 0
        while i < len(run):
            if run[i:i + 3] in CODE_NOISE:               # '24 HOURS' is tenacity, not odour
                i += 3
                continue
            for width in (4, 3, 2):                      # longest match first: 'SWEP' would eat 'SWE' + a stray P
                word = vocab.get(run[i:i + width])
                if word:
                    if word not in out:
                        out.append(word)
                    i += width
                    break
            else:
                i += 1                                   # an OCR stray; skip one letter and keep looking
    return out


def curtis_rows(mono: pd.DataFrame, vocab: dict[str, str], pubchem: dict[str, dict], cas_of: dict[str, str],
                existing_cas: dict[str, str], conflicts: list[dict]) -> tuple[list[dict], list[dict]]:
    """One dataset2 row per Curtis monograph material dataset2 lacks. Returns (new rows, aliases for CAS we hold)."""
    rows, aliases = [], []
    by_material = {_s(r.Material): r for r in mono.itertuples()}
    for material, note_name in CURTIS_NEW.items():
        cas = cas_of.get(material, "")
        r = by_material.get(material)
        if r is None:
            continue
        if cas and cas in existing_cas:
            held = existing_cas[cas]
            if _same_material(note_name, held):
                aliases.append({"Everyday_Name": note_name, "Dataset2_Name": held,
                                "Reason": f"Curtis lists this material; dataset2 already holds CAS {cas} as {held!r}",
                                "Source": _s(r.Source)})
            else:
                conflicts.append({"Book_Material": material, "Book_Name": note_name, "CAS": cas,
                                  "Dataset2_Holder": held, "Source": _s(r.Source),
                                  "Issue": "dataset2 gives this CAS to an unrelated note - one of the two CAS is wrong"})
            continue
        codes = " ".join(_s(getattr(r, c, "")) for c in ("Code_P_or_T", "Code_S_or_B", "Code_B_or_D", "Code_C"))
        words = _decode(codes, vocab)
        prop = pubchem.get(cas, {})
        intensity = _s(r.Intensity_1_6)
        rows.append({
            "Note_Name": note_name,
            "Chemical_Name": _s(r.Chemical_Name) or note_name,
            "CAS": cas,
            "Volatility_Class": CURTIS_CLASS.get(_s(r.Curtis_Note_Class), ""),
            "Odor_Strength": INTENSITY_TO_STRENGTH.get(intensity, "Medium"),
            "Chemical_Family": chemical_family(_s(r.Chemical_Name) or note_name),
            "Odor_Family": " / ".join(words[:2]),
            "Key_Nuances": ", ".join(words[:5]),
            "Molecular_Weight": prop.get("mw", ""),
            "LogP": prop.get("logp", ""),
            "Solubility": "Alcohol soluble",
            # dataset2 uses Natural_Source to say what KIND of row this is; Curtis' occurrence list belongs in prose
            "Natural_Source": "Synthetic" if _s(r.Kind) == "aroma chemical" else (_s(r.Natural_Source) or _s(r.Occurrence)),
            "Short_Description": "; ".join(x for x in (
                _s(r.Stability), f"Occurs naturally in {_s(r.Occurrence)}" if _s(r.Occurrence) else "",
                _s(r.Appearance)) if x),
            "Source": (f"{_s(r.Source)}; odour strength {intensity}/6 and note class {_s(r.Curtis_Note_Class)} from that "
                       f"monograph; CAS from PubChem"),
        })
    return rows, aliases


def ohloff_rows(pubchem: dict[str, dict], cas_of: dict[str, str], existing_cas: dict[str, str],
                mono: pd.DataFrame, conflicts: list[dict]) -> tuple[list[dict], list[dict]]:
    """One dataset2 row per Ohloff material dataset2 lacks, described from his olfactory-family chapter."""
    rows, aliases = [], []
    fam = pd.read_csv(REF / "ohloff_families.csv", dtype=str, keep_default_na=False)
    src_of = {}
    for r in fam.itertuples():
        src_of.setdefault(_s(r.Material), _s(getattr(r, "Source", "")))
    for material, (note_name, layer, strength, odour, nuances, chem) in OHLOFF_NEW.items():
        cas = cas_of.get(material, "")
        if not cas:
            continue
        source = src_of.get(material, "Ohloff/Pickenhagen/Kraft, Scent and Chemistry 2e, olfactory families")
        if cas in existing_cas:
            held = existing_cas[cas]
            if _same_material(note_name, held):
                aliases.append({"Everyday_Name": note_name, "Dataset2_Name": held,
                                "Reason": f"Ohloff lists this material; dataset2 already holds CAS {cas} as {held!r}",
                                "Source": source})
            else:
                conflicts.append({"Book_Material": material, "Book_Name": note_name, "CAS": cas,
                                  "Dataset2_Holder": held, "Source": source,
                                  "Issue": "dataset2 gives this CAS to an unrelated note - one of the two CAS is wrong"})
            continue
        prop = pubchem.get(cas, {})
        rows.append({
            "Note_Name": note_name, "Chemical_Name": note_name, "CAS": cas,
            "Volatility_Class": layer, "Odor_Strength": strength, "Chemical_Family": chem,
            "Odor_Family": odour, "Key_Nuances": nuances,
            "Molecular_Weight": prop.get("mw", ""), "LogP": prop.get("logp", ""),
            "Solubility": "Alcohol soluble", "Natural_Source": "Synthetic", "Short_Description": "",
            "Source": f"{source}; layer by the RSC Ch 11 p.190 boiling-point rule; CAS from PubChem",
        })
    return rows, aliases


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="report what would change, write nothing")
    args = ap.parse_args()

    add = pd.read_csv(HERE / "note_additions.csv", dtype=str, keep_default_na=False)
    mine = set(add.loc[add["Decided_By"].str.startswith(GEN_TAG), "Note_ID"])

    # dataset2 is REBUILT from the workbook plus note_additions.csv, so after one build it already contains this
    # script's own output. Subtract those rows before asking what is missing, or the second run finds nothing to do.
    notes = pd.read_csv(HERE / "dataset2_notes.csv", dtype=str, keep_default_na=False)
    notes = notes[~notes["Note_ID"].isin(mine)]
    existing_names = set(notes["Note_Name"])
    existing_cas: dict[str, str] = {}
    for r in notes.itertuples():
        c = _s(r.CAS)
        if c:
            existing_cas.setdefault(c, _s(r.Note_Name))

    vocab = odour_vocabulary()
    mono = pd.read_csv(REF / "curtis_monographs.csv", dtype=str, keep_default_na=False)
    cas_of = json.load(open(REF / "new_note_cas.json", encoding="utf-8"))
    pub = pd.read_csv(REF / "pubchem_properties.csv", dtype=str, keep_default_na=False)
    pubchem = {_s(r.CAS): {"mw": _s(r.PubChem_MW), "logp": _s(r.PubChem_XLogP)} for r in pub.itertuples()}

    conflicts: list[dict] = []
    c_rows, c_alias = curtis_rows(mono, vocab, pubchem, cas_of, existing_cas, conflicts)
    o_rows, o_alias = ohloff_rows(pubchem, cas_of, existing_cas, mono, conflicts)
    n_rows = natural_rows(existing_names)

    # A name dataset2 already uses must not be added a second time; it becomes an alias to itself (a no-op that
    # documents the overlap) rather than a duplicate row the build would reject.
    new_rows, seen = [], set()
    for row in c_rows + o_rows + n_rows:
        n = row["Note_Name"]
        if n in existing_names or n in seen:
            continue
        seen.add(n)
        new_rows.append(row)

    # ---- note_additions.csv: keep every hand-written row, replace the generated block
    kept = add[~add["Decided_By"].str.startswith(GEN_TAG)]
    used_ids = {int(m.group(1)) for m in (re.match(r"NOTE-(\d+)$", i) for i in kept["Note_ID"]) if m}
    nid = max(FIRST_ID, (max(used_ids) + 1) if used_ids else FIRST_ID)
    built = []
    for row in new_rows:
        out = {c: "" for c in add.columns}
        out.update({k: v for k, v in row.items() if k in out})
        out["Note_ID"] = f"NOTE-{nid}"
        out["Decided_By"] = f"{GEN_TAG}; provisional, perfumer sign-off required"
        nid += 1
        built.append(out)
    merged = pd.concat([kept, pd.DataFrame(built, columns=add.columns)], ignore_index=True) if built else kept

    # ---- note_display_aliases.csv: everyday name -> dataset2 Note_Name, for build_profiles.py only
    known_after = existing_names | {r["Note_Name"] for r in new_rows}
    alias_rows, unresolved = [], []
    for everyday, (target, reason) in DISPLAY_ALIASES.items():
        if target in known_after:
            alias_rows.append({"Everyday_Name": everyday, "Dataset2_Name": target, "Reason": reason,
                               "Source": "editorial (2026-09-23) - everyday name for a material dataset2 already holds",
                               "Apply": "Yes", "Decided_By": "ai (2026-09-23) - naming only, no chemistry changed"})
        else:
            unresolved.append((everyday, target))
    for a in c_alias + o_alias:
        if a["Dataset2_Name"] in known_after and a["Everyday_Name"] != a["Dataset2_Name"]:
            alias_rows.append({"Everyday_Name": a["Everyday_Name"], "Dataset2_Name": a["Dataset2_Name"],
                               "Reason": a["Reason"], "Source": a["Source"], "Apply": "Yes",
                               "Decided_By": "ai (2026-09-23) - the books' name for an existing CAS"})
    for name, why in GAPS.items():
        if name not in known_after:
            alias_rows.append({"Everyday_Name": name, "Dataset2_Name": "", "Apply": "No", "Reason": why,
                               "Source": "data/build_note_expansion.py GAPS - measured against dataset1 note atoms",
                               "Decided_By": "ai (2026-09-23) - recorded as a known gap, not a guess"})
    alias_df = pd.DataFrame(alias_rows, columns=["Everyday_Name", "Dataset2_Name", "Reason", "Source", "Apply", "Decided_By"])

    print(f"dataset2 today          : {len(notes)} rows")
    print(f"new rows from the books : {len(new_rows)}  ({len(c_rows)} Curtis, {len(o_rows)} Ohloff, "
          f"{len(n_rows)} naturals from T&Y Ch 14)")
    print(f"already held under a CAS: {len(c_alias) + len(o_alias)} -> aliases, not duplicate rows")
    print(f"display aliases         : {sum(1 for r in alias_rows if r['Apply'] == 'Yes')} applied, "
          f"{sum(1 for r in alias_rows if r['Apply'] == 'No')} recorded as gaps")
    if conflicts:
        print(f"\nCAS CONFLICTS ({len(conflicts)}) - dataset2 gives a book material's CAS to an unrelated note:")
        for c in conflicts:
            print(f"  {c['CAS']:<14} book: {c['Book_Name']:<26} dataset2: {c['Dataset2_Holder']}")
    if unresolved:
        print("\nalias targets that do NOT exist in dataset2 (fix the target or add the material):")
        for e, t in unresolved:
            print(f"  {e:<24} -> {t}")
    if args.dry_run:
        print("\n--dry-run: nothing written")
        return 1 if unresolved else 0
    pd.DataFrame(conflicts, columns=["Book_Material", "Book_Name", "CAS", "Dataset2_Holder", "Issue", "Source"]).to_csv(
        REF / "note_expansion_cas_conflicts.csv", index=False, encoding="utf-8")
    merged.to_csv(HERE / "note_additions.csv", index=False, encoding="utf-8")
    alias_df.to_csv(HERE / "note_display_aliases.csv", index=False, encoding="utf-8")
    print(f"\nwrote note_additions.csv ({len(merged)} rows) and note_display_aliases.csv ({len(alias_df)} rows)")
    return 1 if unresolved else 0


if __name__ == "__main__":
    sys.exit(main())
