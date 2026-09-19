"""Curtis & Williams, *An Introduction to Perfumery* (Ellis Horwood 1994; Micelle Press 2e 2001) -> cited reference tables.

    python data/mine_curtis.py             # writes reference/curtis_*.csv and the product-table cross-checks

The scan in Downloads has no text layer. The tables below were transcribed from the page images (PDF page numbers
given; book page = PDF page - 17) and the stability statements were harvested from the OCR text of the monographs
(Windows OCR via data/winocr.ps1 -> reference/curtis_intro_to_perfumery_text.txt, gitignored - copyright) and checked
against the page images where the attribution was in doubt.

What is taken (numbers and material lists, every row page-cited):
  * reference/curtis_floral_bases.csv   seven floral bases (Rose, Jasmin, Lily-of-the-Valley, Carnation, Orange Blossom, Violet,
                                         Tuberose): material, recommended upper limit of dosage, Curtis' T/M/B function, skeleton
                                         formulae 1-3 (parts), plus the 'enhancers of natural origin' (Ch 10, PDF p.461-473)
  * reference/curtis_formulas.csv       the type formulas: aldehydic (p.482), basic chypre (p.484), lavender water (p.485),
                                         basic fougere (p.487), traditional eau de cologne (p.488), eau-de-cologne compound of
                                         experiment 11.22 (p.548), the three oriental complexes (p.483)
  * reference/curtis_stability.csv      per-material storage / stability / discoloration statements from the monographs (Ch 5-6)
                                         and the applications chapters (Ch 11-12): light, air, iron, alkali, Schiff bases,
                                         ester hydrolysis, water / alcohol solubility - what zone_b_chemistry/stability.py reads
  * product_types.csv Cross_Check       Curtis' table of toilet-water strengths (p.560) and the extrait range (p.560)
  * product_bases.csv                   glycerin as the alternative toilet-water humectant (p.561); source notes on water,
                                         antioxidant and sunscreen (p.560-561)
What is NOT taken: the 1994 IFRA lines in the monographs (superseded by the 51st Amendment) and the odour-code letters.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REF = HERE / "reference"
BOOK = "Curtis & Williams, An Introduction to Perfumery (1994)"


def src(page: int, where: str = "") -> str:
    return f"{BOOK} {where + ', ' if where else ''}PDF p.{page}"


# ---------------------------------------------------------------------------------------------------------------
# 1. floral bases (Ch 10, 'Experiments to create examples of floral bases') — transcribed from the page images
#    (material, dilution %, recommended upper limit, function T/M/B, skeleton 1, 2, 3)
# ---------------------------------------------------------------------------------------------------------------
BASES = {
    ("Rose", 470): {
        "rows": [
            ("Geraniol", "", 37, "T", 37, 37, 37), ("Geranyl acetate", "", 10, "M", 0, 0, 1), ("Phenylethyl alcohol", "", 68, "T", 31, 19, 3),
            ("Citronellol", "", 64, "T", 31, 64, 27), ("Eugenol", "", 10, "M", 0, 1, 0), ("Phenylacetic acid", "10", 10, "B", 0, 7, 0),
            ("alpha-Ionone", "", 56, "M", 0, 13, 2), ("Phenylacetaldehyde", "10", 12, "B", 6, 6, 0), ("Aldehyde C11 (-enic)", "10", 5, "T", 0, 3, 0),
            ("Aldehyde C8", "10", 5, "T", 0, 0, 2), ("Citral", "10", 5, "M", 0, 0, 1), ("Aldehyde C12 lauric", "10", 5, "T", 0, 1, 0),
            ("Nerol", "", 50, "T", 3, 0, 0), ("Aldehyde C9", "10", 24, "T", 2, 0, 1), ("Linalool", "", 15, "T", 0, 0, 3),
        ],
        "extension": [
            ("iso-Butyl phenylacetate", "10", "T", 0, 0, 1), ("Phenylpropyl alcohol", "", "M", 15, 8, 0), ("Geranyl butyrate", "", "T", 2, 0, 0),
            ("Phenylethyl isobutyrate", "10", "M", 0, 0, 2), ("Trichloromethylphenylcarbinyl acetate", "20", "B", 0, 75, 0),
        ],
        "enhancers": {"Top": ["Bergamot Oil FCF", "Lemon Oil", "Palmarosa Oil"], "Middle": ["Geranium Oil", "Mimosa Absolute", "Rose Absolute", "Rose Otto", "Ylang-Ylang Oil Extra"],
                      "Base": ["Ambergris Tincture", "Benzoin Resinoid", "Labdanum Resinoid", "Vetivert Oil"]},
    },
    ("Jasmin", 465): {
        "rows": [
            ("Amylcinnamic aldehyde", "", 24, "B", 24, 24, 12), ("Lyral", "", 52, "B", 3, 0, 72), ("Phenylethyl alcohol", "", 35, "T", 6, 0, 46),
            ("Methyl anthranilate", "", 10, "M", 0, 1, 2), ("Benzyl salicylate", "", 14, "T", 7, 0, 0), ("Benzyl alcohol", "", 50, "T", 4, 11, 0),
            ("Benzyl butyrate", "", 10, "T", 2, 0, 0), ("Benzyl propionate", "", 16, "T", 0, 5, 0), ("Benzyl acetate", "", 92, "T", 19, 34, 46),
            ("Indole", "10", 10, "M", 2, 4, 0), ("Dihydrojasmone", "1", 17, "M", 0, 6, 0), ("Linalyl acetate", "", 10, "T", 0, 2, 0),
            ("Linalool", "", 30, "T", 0, 7, 24), ("alpha-Ionone", "", 8, "M", 2, 2, 12), ("Musk T (ethylene brassylate)", "", 8, "B", 3, 0, 0),
            ("Aldehyde C14 peach (gamma-undecalactone)", "10", 8, "T", 0, 0, 12), ("Dimethyl benzyl carbinyl acetate", "", 6, "T", 0, 2, 0),
        ],
        "extension": [
            ("Benzyl phenylacetate", "", "M", 10, 0, 0), ("para-Cresyl acetate", "10", "T", 5, 0, 0), ("para-Cresyl iso-butyrate", "10", "T", 0, 0, 3),
            ("para-Cresyl phenylacetate", "10", "T", 0, 0, 6), ("Geraniol", "", "T", 0, 2, 0), ("Geranyl acetate", "", "M", 0, 0, 7), ("gamma-Methyl ionone", "", "M", 4, 0, 5),
        ],
        "enhancers": {"Top": ["Petitgrain Oil Bigarade", "Sweet Orange Oil"], "Middle": ["Celery Seed Oil 10%", "Jasmin Absolute", "Neroli Oil", "Orange Flower Absolute", "Rose Otto 10%", "Ylang-Ylang Oil"],
                      "Base": ["Benzoin Resinoid", "Balsam of Tolu Resinoid", "Styrax Resinoid", "Sandalwood Oil East Indian"]},
    },
    ("Lily-of-the-Valley", 467): {
        "rows": [
            ("Lyral", "", 83, "B", 83, 83, 83), ("Cyclamen aldehyde", "", 8, "B", 0, 8, 0), ("Linalyl cinnamate", "", 28, "T", 0, 0, 17),
            ("Heliotropine", "20", 70, "B", 0, 25, 0), ("Hexylcinnamic aldehyde", "", 22, "B", 0, 9, 24), ("alpha-Ionone", "", 25, "M", 20, 12, 0),
            ("Indole", "10", 10, "M", 0, 0, 1), ("Phenylethyl alcohol", "", 28, "T", 0, 0, 24), ("Benzaldehyde", "1", 28, "T", 1, 1, 0),
            ("alpha-Terpineol", "", 41, "T", 0, 13, 0), ("Citronellol", "", 44, "T", 28, 28, 38), ("Linalool", "", 40, "T", 55, 12, 15),
            ("Benzyl acetate", "", 14, "T", 5, 15, 1), ("cis-3-Hexenyl acetate", "1", 15, "T", 20, 15, 15),
        ],
        "extension": [
            ("Amylcinnamic aldehyde", "", "B", 0, 0, 12), ("Benzyl propionate", "", "T", 8, 0, 0), ("Benzyl salicylate", "", "T", 10, 0, 0),
            ("Phenylpropyl alcohol", "", "M", 6, 0, 0), ("Dimethyl benzyl carbinol", "", "T", 0, 7, 0), ("Vanillin", "10", "B", 0, 4, 0),
        ],
        "enhancers": {"Top": ["Bergamot Oil FCF", "Rosewood Oil", "Sweet Orange Oil"], "Middle": ["Jasmin Absolute", "Rose Absolute", "Ylang-Ylang Oil Extra"],
                      "Base": ["Benzoin Resinoid", "Civet Tincture", "Styrax Resinoid"]},
    },
    ("Carnation", 461): {
        "rows": [
            ("Eugenol", "", 36, "M", 36, 36, 36), ("iso-Eugenyl acetate", "", 20, "M", 0, 10, 0), ("Methyl iso-eugenol", "", 40, "M", 36, 0, 5),
            ("Benzyl iso-eugenol", "", 24, "M", 0, 12, 0), ("Lyral", "", 8, "B", 0, 3, 3), ("alpha-Ionone", "", 16, "M", 0, 0, 3),
            ("Vanillin", "10", 40, "B", 40, 12, 14), ("Phenylacetaldehyde (in phenylethyl alcohol)", "10", 24, "B", 0, 12, 14), ("Heliotropine", "20", 60, "M", 0, 30, 0),
            ("iso-Amyl salicylate", "", 24, "T", 18, 4, 7), ("Benzyl salicylate", "", 32, "T", 0, 0, 7), ("Phenylethyl alcohol", "", 48, "T", 13, 0, 9),
            ("Geraniol", "", 24, "T", 18, 0, 5), ("Citronellol", "", 28, "T", 0, 0, 5), ("Benzyl acetate", "", 24, "T", 0, 1, 14),
        ],
        "extension": [
            ("Anisaldehyde", "10", "M", 0, 5, 0), ("Phenylpropyl alcohol", "10", "M", 0, 0, 5), ("Methyl eugenol", "", "T", 0, 5, 0),
            ("gamma-Methyl ionone", "", "M", 8, 8, 0), ("alpha-Terpineol", "", "T", 3, 0, 0),
        ],
        "enhancers": {"Top": ["Bergamot Oil FCF", "Carrot Seed Oil 10%"], "Middle": ["Clary Sage Oil 10%", "Clove Bud Oil", "Jasmin Absolute", "Orange Flower Absolute", "Rose Otto 10%", "Ylang-Ylang Oil Extra"],
                      "Base": ["Benzoin Resinoid", "Black Pepper Oil", "Pimento Berry Oil", "Balsam of Peru Oil"]},
    },
    ("Orange Blossom", 469): {
        "rows": [
            ("Aurantiol", "50", 75, "B", 75, 50, 75), ("Linalyl acetate", "", 50, "T", 9, 35, 0), ("Methyl anthranilate", "", 18, "M", 0, 0, 38),
            ("Indole", "10", 12, "M", 0, 4, 25), ("Geraniol", "", 15, "T", 20, 0, 25), ("Nerol", "", 30, "T", 0, 25, 50),
            ("Linalool", "", 53, "T", 9, 125, 30), ("alpha-Terpineol", "", 30, "T", 34, 40, 13), ("Phenylethyl alcohol", "", 60, "T", 56, 0, 60),
            ("Aldehyde C10", "10", 6, "B", 0, 1, 13), ("Methyl benzoate", "10", 30, "T", 0, 0, 6), ("iso-Butyl phenylacetate", "", 6, "T", 0, 0, 6),
        ],
        "extension": [
            ("Aldehyde C12 lauric", "10", "T", 15, 0, 0), ("Aldehyde C12 MNA", "10", "T", 0, 10, 0), ("Citral", "10", "T", 0, 10, 0),
            ("Geranyl acetate", "", "M", 0, 0, 5), ("Lyral", "", "B", 10, 0, 10), ("Linalyl cinnamate", "", "M", 0, 8, 0),
            ("Methyl benzoate", "10", "T", 3, 0, 0), ("Methyl iso-eugenol", "", "M", 2, 0, 0),
        ],
        "enhancers": {"Top": ["Bergamot Oil FCF", "Mandarin Oil", "Petitgrain Oil Bigarade", "Rosewood Oil", "Sweet Orange Oil"],
                      "Middle": ["Jasmin Absolute", "Orange Flower Absolute", "Ylang-Ylang Oil Extra"], "Base": ["Myrrh Resinoid"]},
    },
    ("Violet", 473): {
        "rows": [
            ("alpha-Ionone", "", 55, "M", 55, 55, 55), ("beta-Ionone", "", 85, "M", 53, 115, 0), ("gamma-Methyl ionone", "", 85, "M", 36, 36, 180),
            ("Aldehyde C12", "10", 9, "T", 0, 0, 4), ("Anisaldehyde", "", 17, "M", 15, 32, 0), ("Jasmin base", "", 20, "M", 0, 28, 7),
            ("Benzyl iso-eugenol", "10", 100, "M", 0, 0, 150), ("Heliotropine", "20", 100, "M", 0, 75, 0), ("Musk T (ethylene brassylate)", "", 9, "B", 0, 5, 0),
            ("Phenylethyl alcohol", "", 14, "T", 0, 23, 0), ("Linalool", "", 6, "T", 0, 0, 7), ("Linalyl acetate", "", 10, "T", 0, 0, 10),
            ("Methyl nonylenate", "10", 40, "T", 15, 20, 0), ("Benzyl acetate", "", 20, "T", 0, 0, 37),
        ],
        "extension": [
            ("Benzyl iso-eugenol", "10", "M", 30, 0, 0), ("Eugenol", "", "M", 3, 0, 0), ("Lyral", "", "B", 0, 15, 0),
            ("Phenylethyl acetate", "", "T", 4, 0, 5), ("Vanillin", "10", "B", 15, 0, 12),
        ],
        "enhancers": {"Top": ["Bergamot Oil", "Mimosa Absolute"], "Middle": ["Guaiacwood Oil", "Rose Absolute", "Rose Otto 10%", "Violet Leaf Absolute 10%", "Ylang-Ylang Oil Extra"],
                      "Base": ["Benzoin Resinoid", "Sandalwood Oil East Indian", "Vetivert Oil"]},
    },
    ("Tuberose", 472): {
        "rows": [
            ("Linalool", "", 62, "B", 31, 31, 31), ("Heliotropine", "20", 75, "M", 30, 0, 40), ("Amylcinnamic aldehyde", "", 15, "B", 2, 0, 3),
            ("Benzyl salicylate", "", 55, "T", 0, 44, 0), ("Geraniol", "", 62, "T", 0, 0, 11), ("Lyral", "", 34, "T", 0, 132, 0),
            ("Methyl anthranilate", "", 5, "B", 5, 20, 3), ("Methyl salicylate", "", 35, "T", 3, 18, 6), ("Methyl benzoate", "", 10, "T", 4, 18, 9),
            ("Aldehyde C14 peach (gamma-undecalactone)", "10", 30, "T", 2, 0, 0), ("Benzyl acetate", "", 20, "T", 8, 44, 11), ("Methyl nonylenate", "10", 20, "T", 0, 5, 0),
        ],
        "extension": [("Aldehyde C12 lauric", "10", "T", 0, 5, 8), ("Aurantiol", "", "B", 12, 0, 0), ("Vanillin", "10", "B", 0, 0, 5)],
        "enhancers": {"Top": ["Bergamot Oil FCF"], "Middle": ["Celery Seed Oil 10%", "Jasmin Absolute", "Ylang-Ylang Oil Extra"],
                      "Base": ["Benzoin Resinoid", "Labdanum Resinoid", "Balsam of Peru Resinoid", "Balsam of Tolu Resinoid"]},
    },
}
FUNCTION = {"T": "Top", "M": "Heart", "B": "Base"}

# ---------------------------------------------------------------------------------------------------------------
# 2. type formulas (Ch 10 'Perfume types', Ch 11 experiment 11.22) — parts as printed
# ---------------------------------------------------------------------------------------------------------------
FORMULAS = {
    ("Aldehydic type perfume (Experiment 10.3)", 482, "floral-aldehydic"): [
        ("Jasmin base", 150, ""), ("Rose base", 130, "+/-10"), ("Muguet (Lily-of-the-Valley) base", 200, "+/-15"), ("Linalool", 80, "+/-5"),
        ("gamma-Methyl ionone", 80, "+/-8"), ("Coumarin", 50, "+/-10"), ("Musk ketone", 50, "+/-5"), ("Sandalwood Oil", 32, "+/-5"),
        ("Vetivert Oil Reunion", 30, "+/-3"), ("Civet Tincture 3%", 15, "+/-5"), ("Aldehyde C12 lauric 10%", 20, ""), ("Aldehyde C11 (-enic) 10%", 15, ""),
        ("Aldehyde C10 10%", 15, ""), ("Patchouli Oil light", 10, ""), ("Vanillin", 8, ""), ("Ambroxan 1%", 7, ""), ("Clove Bud Oil", 3, ""),
        ("Ylang-Ylang Oil Extra", 50, ""), ("Bergamot Oil Italian", 55, ""),
    ],
    ("Basic Chypre-type perfume", 484, "chypre"): [
        ("Bergamot Oil FCF", 15, "starting quantity"), ("Sandalwood Oil E.I.", 8, ""), ("Vetivert Oil Bourbon", 6, ""), ("Oakmoss Absolute decolourised", 5, ""),
        ("Rose base", 6, ""), ("Jasmin base", 5, ""), ("gamma-Methyl ionone", 3, ""), ("Patchouli Oil light", 5, ""), ("Musk ketone", 3, ""),
        ("Clary Sage Oil", 2, ""), ("Neroli Oil reconstituted", 2, ""),
    ],
    ("Lavender Water compound", 485, "lavender water"): [
        ("Lavender Oil French", 45, ""), ("Bergamot Oil FCF", 25, ""), ("Lemon Oil Sicilian", 6, ""), ("Neroli Oil reconstituted", 4, ""),
        ("Musk ketone", 3, ""), ("Sweet Orange Oil", 3, ""), ("Geranium Oil Reunion", 4, ""), ("Benzoin Resinoid", 4, ""),
    ],
    ("Basic Fougere-type perfume", 487, "fougere"): [
        ("Lavender Oil French", 14, ""), ("Bergamot Oil FCF", 8, ""), ("Coumarin", 12, ""), ("Rose base", 5, ""), ("Jasmin base", 4, ""),
        ("Oakmoss Absolute", 6, ""), ("Patchouli Oil light", 2, ""), ("Vetivert Oil Bourbon", 10, ""), ("Geranium Oil Bourbon", 2, ""), ("iso-Amyl salicylate", 3, ""),
    ],
    ("Traditional Eau de Cologne", 488, "eau de cologne"): [
        ("Bergamot Oil FCF", 27, ""), ("Lemon Oil Sicilian", 20, ""), ("Sweet Orange Oil", 16, ""), ("Neroli Oil reconstituted", 12, ""),
        ("Lavender Oil French", 6, ""), ("Rosemary Oil Spanish", 4, ""), ("Thyme Oil White", 1, ""), ("Clove Bud Oil", 1, ""),
        ("Petitgrain Oil", 3, "optional"), ("Clary Sage Oil", 2, "optional"), ("Benzoin Resinoid Siam", 3, "optional; the fixative"),
    ],
    ("Eau de Cologne type compound (Experiment 11.22)", 548, "eau de cologne"): [
        ("Bergamot Oil furanocoumarin-free", 21, ""), ("Lemon Oil", 25, ""), ("Citral", 2, ""), ("Rosemary Oil", 4, ""), ("Linalyl acetate", 7, ""),
        ("Petitgrain Oil Bigarade", 5, ""), ("Lavender Oil French", 8, ""), ("Geraniol", 7, ""), ("Musk ketone", 5, ""), ("Heliotropine", 6, ""),
        ("Benzoin resinoid Siam", 10, ""),
    ],
    ("Oriental complex 1 (Experiment 10.4)", 483, "oriental"): [("Accord A (sandalwood / patchouli-vetivert / Musk T / Ambroxan 1%)", 10, ""), ("Accord B (two or three heavier floral bases)", 70, ""), ("Accord C (bergamot, lemon, lavender, geranium)", 30, "")],
    ("Oriental complex 2 (Experiment 10.4)", 483, "oriental"): [("Accord A (sandalwood / patchouli-vetivert / Musk T / Ambroxan 1%)", 30, ""), ("Accord B (two or three heavier floral bases)", 50, ""), ("Accord C (bergamot, lemon, lavender, geranium)", 30, "")],
    ("Oriental complex 3 (Experiment 10.4)", 483, "oriental"): [("Accord A (sandalwood / patchouli-vetivert / Musk T / Ambroxan 1%)", 50, ""), ("Accord B (two or three heavier floral bases)", 30, ""), ("Accord C (bergamot, lemon, lavender, geranium)", 30, "")],
}

# ---------------------------------------------------------------------------------------------------------------
# 3. stability / discoloration statements (monographs Ch 5-6; applications Ch 11-12)
#    Class: light | air | iron | alkali | acid | schiff_amine | schiff_carbonyl | ester_hydrolysable | solvent | process
# ---------------------------------------------------------------------------------------------------------------
STABILITY = [
    # material, CAS (blank for naturals / classes), classes, statement, page
    ("Aldehydes C8-C10 (octanal, nonanal, decanal)", "124-13-0|124-19-6|112-31-2", "air|schiff_carbonyl", "cool place and small headspace essential; easily oxidised, with production of sour / unpleasant notes", 166),
    ("Aldehyde C11 undecylenic", "112-45-8", "air|schiff_carbonyl", "cool place and small headspace essential; polymerises rather easily, with reduction of odour strength", 167),
    ("Aldehyde C12 MNA (methyl nonyl acetaldehyde)", "110-41-8", "air|schiff_carbonyl", "cool place and small headspace necessary; stable, but capable of oxidation with production of sour notes", 168),
    ("Amylcinnamic aldehyde", "122-40-7", "air|schiff_carbonyl", "stable, but can oxidise with production of coarse or almondy notes, in which condition it is not fit for use", 172),
    ("Anisaldehyde", "123-11-5", "air|schiff_carbonyl", "stable, but can oxidise to odourless anisic acid", 173),
    ("Benzaldehyde", "100-52-7", "air|schiff_carbonyl", "small headspace advisable; readily oxidised in air to colourless, almost odourless benzoic acid", 174),
    ("Benzyl alcohol", "100-51-6", "air", "can oxidise to benzaldehyde and dibenzyl ether, with the onset of almondy notes", 176),
    ("Cinnamic aldehyde", "104-55-2", "air|light|alkali|schiff_carbonyl", "readily oxidised by atmospheric oxygen to odourless crystals of cinnamic acid; must be fully protected from light; can discolour white soaps; unstable in media of high pH", 181),
    ("Citral", "5392-40-5", "air|light|alkali|schiff_carbonyl", "becomes pale yellow, darkening on exposure to air and sunlight; contact with alkaline media promotes deterioration; severe discoloration in the presence of anthranilates, indole and other amines, quinolines and other nitrogen compounds (Schiff bases)", 183),
    ("Citronellal", "106-23-0", "air|light|alkali|schiff_carbonyl", "rather poor in contact with air or alkali, and in sunlight", 184),
    ("Dihydrojasmone", "1128-08-1", "schiff_carbonyl", "stable, but may cause discoloration", 191),
    ("Eugenol", "97-53-0", "air|alkali|iron", "darkens on exposure to air, particularly under alkaline conditions; discolours in contact with ferrous metal", 195),
    ("Farnesol", "4602-84-0", "iron", "avoid contact with aluminium; stable if of high purity; may give rise to discoloration", 198),
    ("Hydroxycitronellal", "107-75-5", "alkali|schiff_carbonyl", "unstable in alkaline media, should not be heated", 205),
    ("Indole", "120-72-9", "light|schiff_amine", "must be protected from light and isolated from all other materials; severe discoloration, particularly with aldehydes and ketones, or on exposure to sunlight", 206),
    ("Lilial", "80-54-6", "air", "fairly rapidly oxidised in air (crust of colourless crystals at the closure)", 208),
    ("Methyl anthranilate", "134-20-3", "light|schiff_amine", "can give rise to discoloration, particularly with certain aldehydes or ketones, or with nitro-musks; anthranilates darken on exposure to light and air (p.146)", 213),
    ("Methyl salicylate", "119-36-8", "iron", "stable, but can give rise to discoloration in the presence of iron", 218),
    ("Musk ketone", "81-14-1", "light|schiff_carbonyl", "must be protected from light, darkens on exposure to daylight; discoloration with amines such as indole and anthranilates, and certain aldehydes", 219),
    ("Musk xylene", "81-15-2", "light", "must be protected from light; darkens on exposure to daylight; discoloration with amines (banned in the UK/EU anyway)", 220),
    ("Vanillin", "121-33-5", "light|iron|alkali|schiff_carbonyl", "must be protected from light and stored free from contact with ferrous metals; discoloration in alkaline media, with nitrogen-containing chemicals, and in the presence of traces of iron", 230),
    ("Birch Tar Oil rectified", "8001-88-5", "iron", "may give rise to discoloration in the presence of traces of iron", 261),
    ("Cassia Oil", "8007-80-5", "iron|air", "discoloration with traces of iron; its cinnamic aldehyde readily oxidises to almost odourless cinnamic acid", 263),
    ("Clove Bud Oil", "8000-34-8", "iron|alkali", "stable, but gives rise to discoloration in the presence of iron; darkening due to oxidation of eugenol in the presence of alkali", 270),
    ("Jasmin Absolute", "8022-96-6|84776-64-7|90045-94-6", "schiff_amine|light", "cool place essential; its indole content may give rise to discoloration", 276),
    ("Lemon Oil cold pressed", "8008-56-8", "air", "stable, but deteriorates rapidly on exposure to air", 280),
    ("Mandarin Oil", "8008-31-9", "air|schiff_amine", "stable, but deteriorates fairly rapidly on exposure to air (contains methyl N-methyl anthranilate)", 281),
    ("Orange Flower Absolute", "8030-28-2", "schiff_amine|light", "slowly darkens; its indole content can give rise to discoloration", 285),
    ("Vanilla Absolute", "8024-06-4", "alkali|schiff_carbonyl", "stable, but can cause discoloration in the presence of alkali or amines (anthranilates, indole etc.)", 298),
    # classes and solvent / process statements
    ("Esters: acetates, formates, propionates, butyrates, caproates", "", "ester_hydrolysable", "hydrolysis in an aqueous product (toilet water) returns the parent alcohol and an acid whose smell is almost always unpleasant — benzyl acetate -> acetic acid (vinegar), allyl caproate -> caproic acid (stale sweat), geranyl butyrate -> butyric acid (rancid butter), phenylethyl formate -> formic acid; the acid formed catalyses further hydrolysis (autocatalytic at neutral or low pH); citronellyl formate is easily hydrolysed, phenylethyl formate resists", 526),
    ("Ethanol (solvent)", "64-17-5", "solvent", "reacts with aldehydes (and materials containing them) and many esters, but the products have acceptable odour and do not normally cause problems", 560),
    ("Water (solvent)", "7732-18-5", "solvent", "purified by distillation or ion exchange (salts removed); more polar than ethanol, will not dissolve the weakly polar terpenes of essential oils — an aqueous alcohol of 75 % strength or weaker mixes with only very small proportions of terpene-rich oils, so toilet-water compounds use terpeneless oils in place of Lemon, Orange and Bergamot; phenylethyl alcohol is the exception, water-soluble to 9 % at 15 C", 561),
    ("Extrait (product)", "", "process", "15-30 % of perfume compound in perfumery-grade alcohol, the remainder water; very small but effective proportions of an anti-oxidant and a sunscreen are usually incorporated to retard deterioration; storage rules: sealed container, cool place, protect from light", 560),
    ("Maturation (process)", "", "process", "an experimental compound should stand in a cool place for at least one week before final evaluation, and is about fully aged after one month; once diluted with alcohol to an extrait or toilet water it needs a further, longer maturation to reach equilibrium", 458),
    ("Light exposure (experiment 11.21)", "", "light", "in colourless glass on a window-sill for a month: musk ketone darkens rapidly, indole less rapidly (brown or pink); methyl anthranilate, citral and eugenol darken slowly; the citral + methyl anthranilate mixture darkens by Schiff base formation", 554),
    ("Aged cologne in light (experiment 11.22)", "", "light", "the aged compound smells smoother than the fresh one; refrigerated it stays pale yellow with a fresh odour; in direct sunlight it becomes darker and its freshness diminishes; indirect sunlight changes it more slowly", 555),
]

# ---------------------------------------------------------------------------------------------------------------
# 4. product-level cross-checks (Ch 12 p.560-561)
# ---------------------------------------------------------------------------------------------------------------
PRODUCT_CROSS = {
    "Extrait / parfum": "Curtis 1994 p.560: 15-30 % perfume compound in perfumery-grade alcohol, remainder water",
    "Parfum de toilette / Eau de parfum / Esprit de parfum": "Curtis 1994 p.560: 8-15 % compound, 80-90 % alcohol by volume",
    "Eau de toilette": "Curtis 1994 p.560: 4-8 %, c. 80 % alcohol",
    "Eau de cologne": "Curtis 1994 p.560: 3-5 %, c. 70 % alcohol",
    "Splash cologne": "Curtis 1994 p.560: 1-3 %, c. 60 % alcohol; eau fraiche c. 3 %, c. 80 % alcohol",
}


def write(path: Path, rows: list[dict], cols: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows):4d} rows -> {path.relative_to(HERE.parent)}")


def main() -> int:
    REF.mkdir(exist_ok=True)
    rows = []
    for (base, page), spec in BASES.items():
        for m, dil, lim, fn, s1, s2, s3 in spec["rows"]:
            rows.append({"Base": base, "Material": m, "Dilution_Pct": dil, "Upper_Limit_Parts": lim, "Function": FUNCTION[fn], "Section": "skeleton",
                         "Skeleton_1": s1 or "", "Skeleton_2": s2 or "", "Skeleton_3": s3 or "", "Source": src(page, "Ch 10 floral bases")})
        for m, dil, fn, s1, s2, s3 in spec["extension"]:
            rows.append({"Base": base, "Material": m, "Dilution_Pct": dil, "Upper_Limit_Parts": "", "Function": FUNCTION[fn], "Section": "extension",
                         "Skeleton_1": s1 or "", "Skeleton_2": s2 or "", "Skeleton_3": s3 or "", "Source": src(page, "Ch 10 floral bases")})
        for layer, mats in spec["enhancers"].items():
            for m in mats:
                rows.append({"Base": base, "Material": m, "Dilution_Pct": "", "Upper_Limit_Parts": "", "Function": {"Top": "Top", "Middle": "Heart", "Base": "Base"}[layer],
                             "Section": "enhancer of natural origin", "Skeleton_1": "", "Skeleton_2": "", "Skeleton_3": "", "Source": src(page, "Ch 10 floral bases")})
    write(REF / "curtis_floral_bases.csv", rows, ["Base", "Material", "Dilution_Pct", "Upper_Limit_Parts", "Function", "Section", "Skeleton_1", "Skeleton_2", "Skeleton_3", "Source"])

    rows = [{"Formula": f, "Family": fam, "Material": m, "Parts": p, "Note": n, "Source": src(page, "Ch 10/11")}
            for (f, page, fam), mats in FORMULAS.items() for m, p, n in mats]
    write(REF / "curtis_formulas.csv", rows, ["Formula", "Family", "Material", "Parts", "Note", "Source"])

    rows = [{"Material": m, "CAS": cas, "Classes": cl, "Statement": st, "Source": src(page)} for m, cas, cl, st, page in STABILITY]
    write(REF / "curtis_stability.csv", rows, ["Material", "CAS", "Classes", "Statement", "Source"])

    pt = HERE / "product_types.csv"
    prows = list(csv.DictReader(open(pt, encoding="utf-8")))
    for r in prows:
        add = PRODUCT_CROSS.get(r["Product_Type"])
        if add and "Curtis" not in r.get("Cross_Check", ""):
            r["Cross_Check"] = (r["Cross_Check"] + "; " if r["Cross_Check"] else "") + add
    with open(pt, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(prows[0].keys()))
        w.writeheader()
        w.writerows(prows)
    pb = HERE / "product_bases.csv"
    brows = list(csv.DictReader(open(pb, encoding="utf-8")))
    have = {r["Component"] for r in brows}
    if "Glycerin" not in have:
        brows.append({"Component": "Glycerin", "INCI": "Glycerin", "CAS": "56-81-5", "Role": "humectant (toilet waters)", "Default_Pct": "0", "Min_Pct": "0", "Max_Pct": "3",
                      "Phase": "additives", "When_To_Use": "toilet waters intended for liberal use: glycerine or propylene glycol counter the drying effect of the alcohol; optional",
                      "Legal_Basis": "UK/EU: no restriction", "Source": src(561, "Ch 12 toilet waters"), "Note": "alternative to propylene glycol (Poucher Formula VI)"})
    for r in brows:
        if r["Component"] == "Purified water" and "Curtis" not in r["Source"]:
            r["Source"] += f"; {src(561)}: purified by distillation or ion exchange; >25 % water dissolves only traces of terpene-rich oils"
        if r["Component"] == "BHT" and "Curtis" not in r["Source"]:
            r["Source"] += f"; {src(560)}: extraits carry an anti-oxidant and a sunscreen"
        if r["Component"] == "Benzophenone-3" and "Curtis" not in r["Source"]:
            r["Source"] += f"; {src(560)}: 'sunscreen' in extraits; p.547: UV 285-380 nm promotes the reactions that spoil aromatic materials"
    with open(pb, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(brows[0].keys()))
        w.writeheader()
        w.writerows(brows)
    print("product_types.csv / product_bases.csv cross-checks updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
