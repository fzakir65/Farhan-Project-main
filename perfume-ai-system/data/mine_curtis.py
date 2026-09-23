"""Curtis & Williams, *An Introduction to Perfumery* (Ellis Horwood 1994; Micelle Press 2e 2001) -> cited reference tables.

    python data/mine_curtis.py             # writes reference/curtis_*.csv and the product-table cross-checks

The scan in Downloads has no text layer. The tables below were transcribed from the page images (PDF page numbers
given; book page = PDF page - 17) and the stability statements were harvested from the OCR text of the monographs
(Windows OCR via data/winocr.ps1 -> reference/curtis_intro_to_perfumery_text.txt, gitignored - copyright) and checked
against the page images where the attribution was in doubt.

What is taken (numbers and material lists, every row page-cited):
  * reference/curtis_floral_bases.csv   all fourteen floral bases (Rose, Jasmin, Lily-of-the-Valley, Carnation, Orange Blossom, Violet,
                                         Tuberose, Acacia, Gardenia, Honeysuckle, Hyacinth, Lilac, Narcissus, Sweet Pea): material, recommended upper limit of dosage, Curtis' T/M/B function, skeleton
                                         formulae 1-3 (parts), plus the 'enhancers of natural origin' (Ch 10, PDF p.461-473)
  * reference/curtis_formulas.csv       the type formulas: aldehydic (p.482), basic chypre (p.484), lavender water (p.485),
                                         basic fougere (p.487), traditional eau de cologne (p.488), eau-de-cologne compound of
                                         experiment 11.22 (p.548), the three oriental complexes (p.483)
  * reference/curtis_stability.csv      per-material storage / stability / discoloration statements from the monographs (Ch 5-6)
                                         and the applications chapters (Ch 11-12): light, air, iron, alkali, Schiff bases,
                                         ester hydrolysis, water / alcohol solubility - what zone_b_chemistry/stability.py reads
  * reference/curtis_monographs.csv     the Ch 5 aroma-chemical (PDF p.165-231) and Ch 6 natural-material (p.258-309) monographs
                                         parsed from word-boxed OCR (data/winocr_boxes.ps1 -> reference/curtis_boxes/pNNN.json, gitignored):
                                         Curtis' Top / Middle / Basic note class, the bold intensity digit on the 1-6 scale (found by the
                                         digit's box height in the page image), odour codes, and every text field (appearance, storage,
                                         stability, applications, occurrence, natural source, production, chief constituents)
  * reference/curtis_odour_vocabulary.csv  Ch 3 'Tables of odour descriptive words' (PDF p.66-91): code, word, origin and the
                                         related descriptors — the seed of data/user_lexicon.csv
  * product_types.csv Cross_Check       Curtis' table of toilet-water strengths (p.560) and the extrait range (p.560)
  * product_bases.csv                   glycerin as the alternative toilet-water humectant (p.561); source notes on water,
                                         antioxidant and sunscreen (p.560-561)
What is NOT taken: the 1994 IFRA lines in the monographs (superseded by the 51st Amendment) and the odour-code letters.
"""
from __future__ import annotations

import csv
import json
import re
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
    ("Acacia", 460): {
        "rows": [
            ("Anisaldehyde", "", 80, "M", 80, 80, 80), ("Lyral", "", 17, "B", 5, 48, 6), ("Amylcinnamic aldehyde", "", 36, "B", 0, 3, 0),
            ("Musk T (ethylene brassylate)", "", 10, "B", 0, 0, 4), ("Methyl naphthyl ketone", "", 74, "B", 0, 16, 10), ("Heliotropine", "20", 105, "M", 90, 30, 70),
            ("Phenylpropyl alcohol", "", 20, "T", 11, 16, 0), ("alpha-Terpineol", "", 20, "T", 0, 10, 0), ("Phenylethyl alcohol", "", 35, "T", 11, 19, 8),
            ("Linalool", "", 35, "T", 10, 30, 12), ("Linalyl acetate", "", 4, "T", 7, 6, 5), ("Citronellol", "", 12, "T", 5, 16, 13),
            ("para-Methyl acetophenone", "", 8, "T", 7, 0, 10), ("Benzyl acetate", "", 28, "T", 7, 6, 25),
        ],
        "extension": [
            ("Aldehyde C16 strawberry", "10", "B", 2, 0, 0), ("Phenylacetaldehyde (in phenylethyl alcohol)", "50", "B", 6, 8, 9),
            ("Phenylacetic acid", "10", "B", 40, 30, 0), ("Vanillin", "10", "B", 60, 0, 0),
        ],
        "enhancers": {"Top": ["Bergamot Oil FCF", "Petitgrain Oil Bigarade"], "Middle": ["Jasmin Absolute", "Orange Flower Absolute", "Ylang-Ylang Oil Extra"],
                      "Base": ["Benzoin Resinoid", "Balsam of Peru Resinoid", "Sandalwood Oil East Indian", "Balsam of Tolu Resinoid"]},
    },
    ("Gardenia", 462): {
        "rows": [
            ("Lyral", "", 42, "B", 42, 42, 21), ("Jasmin base", "", 36, "B", 6, 2, 9), ("Orange Blossom base", "", 36, "B", 0, 4, 3), ("Tuberose base", "", 35, "B", 2, 3, 3),
            ("Methyl anthranilate", "", 4, "M", 0, 0, 15), ("Amylcinnamic aldehyde", "", 8, "B", 6, 0, 2), ("Coumarin", "10", 40, "B", 0, 40, 30),
            ("Phenylacetaldehyde dimethylacetal", "", 15, "B", 1, 7, 0), ("Musk T (ethylene brassylate)", "", 30, "B", 0, 0, 2), ("alpha-Ionone", "", 20, "M", 0, 21, 0),
            ("Heliotropine", "20", 100, "M", 0, 85, 0), ("Phenylethyl alcohol", "", 20, "T", 20, 20, 24), ("Linalool", "", 13, "T", 2, 0, 6),
            ("Linalyl acetate", "", 15, "T", 4, 0, 12), ("Dimethyl benzyl carbinol", "", 8, "T", 0, 8, 0), ("Citronellol", "", 15, "T", 0, 9, 24),
            ("alpha-Terpineol", "", 28, "T", 13, 13, 30), ("Methyl phenyl carbinyl acetate", "", 23, "T", 6, 19, 27), ("Benzyl acetate", "", 28, "T", 32, 10, 15),
        ],
        "extension": [
            ("Acetyl iso-eugenol", "", "M", 16, 0, 0), ("Aldehyde C10", "10", "T", 0, 2, 0), ("Aldehyde C16 strawberry", "10", "B", 6, 5, 0),
            ("Aldehyde C18 coconut", "10", "B", 0, 30, 0), ("Phenylpropyl alcohol", "", "M", 0, 10, 0), ("Methyl salicylate", "10", "T", 0, 10, 5),
        ],
        "enhancers": {"Top": ["Bergamot Oil FCF", "Coriander Oil", "Petitgrain Oil Bigarade", "Mimosa Absolute"],
                      "Middle": ["Clary Sage Oil 10%", "Clove Bud Oil", "Jasmin Absolute", "Rose Absolute", "Myrrh Resinoid", "Ylang-Ylang Oil"],
                      "Base": ["Benzoin Resinoid", "Balsam of Peru Resinoid", "Sandalwood Oil East Indian", "Vetivert Oil"]},
    },
    ("Honeysuckle", 463): {
        "rows": [
            ("Linalool", "", 45, "T", 45, 45, 20), ("Lyral", "", 48, "B", 0, 6, 60), ("alpha-Ionone", "", 27, "M", 20, 8, 10), ("Jasmin base", "", 8, "B", 0, 0, 2),
            ("Orange Blossom base", "", 10, "B", 0, 2, 2), ("Heliotropine", "20", 150, "M", 0, 80, 120), ("Vanillin", "10", 56, "B", 15, 18, 28),
            ("Methyl anthranilate", "", 10, "M", 6, 0, 0), ("Phenylethyl phenylacetate", "", 10, "B", 0, 0, 20), ("Methyl naphthyl ketone", "", 10, "B", 0, 0, 20),
            ("Musk ketone", "10", 80, "B", 0, 20, 0), ("Geraniol", "", 45, "T", 0, 0, 16), ("Citronellol", "", 16, "T", 12, 0, 0),
            ("Phenylethyl alcohol", "", 30, "T", 36, 11, 56), ("alpha-Terpineol", "", 34, "T", 45, 14, 24), ("Benzyl acetate", "", 13, "T", 3, 0, 8),
        ],
        "extension": [
            ("Aldehyde C11 (-enic)", "10", "T", 0, 20, 0), ("Amylcinnamic aldehyde", "", "B", 60, 0, 0), ("Aurantiol", "", "B", 0, 0, 35),
            ("Cyclamen aldehyde", "", "B", 3, 0, 0), ("iso-Eugenyl acetate", "", "M", 3, 0, 0), ("Indole", "10", "M", 2, 0, 0),
            ("Lilial", "", "M", 5, 0, 0), ("Phenylacetaldehyde", "10", "B", 12, 0, 0), ("Phenylacetic acid", "10", "B", 0, 0, 9),
        ],
        "enhancers": {"Top": ["Bergamot Oil FCF"], "Middle": ["Jasmin Absolute", "Rose Absolute", "Ylang-Ylang Oil"],
                      "Base": ["Olibanum Resinoid", "Styrax Resinoid", "Balsam of Tolu Resinoid"]},
    },
    ("Hyacinth", 464): {
        "rows": [
            ("Phenylpropyl alcohol", "", 28, "M", 28, 28, 28), ("Phenylacetaldehyde", "50", 80, "B", 3, 18, 22), ("Heliotropine", "20", 100, "M", 0, 0, 25),
            ("alpha-Ionone", "", 6, "M", 0, 6, 0), ("Amylcinnamic aldehyde", "", 10, "B", 0, 9, 2), ("Lyral", "", 40, "B", 5, 0, 0),
            ("Nonane-1,3-diol diacetate", "", 20, "M", 0, 10, 0), ("Coumarin", "", 4, "B", 0, 0, 1), ("Indole", "10", 10, "M", 9, 0, 0),
            ("Benzyl alcohol", "", 20, "M", 0, 18, 7), ("Linalool", "", 24, "T", 0, 0, 9), ("Linalyl acetate", "", 10, "T", 0, 0, 2),
            ("Methyl eugenol", "", 12, "T", 0, 8, 0), ("Phenylethyl alcohol", "", 76, "T", 74, 18, 4), ("iso-Amyl salicylate", "", 20, "T", 20, 0, 0),
            ("Benzyl acetate", "", 20, "T", 22, 0, 7),
        ],
        "extension": [
            ("Benzyl propionate", "", "T", 0, 14, 5), ("Cyclamen aldehyde", "", "B", 2, 0, 0), ("Eugenol", "", "M", 2, 0, 0), ("Methyl eugenol", "", "T", 0, 0, 12),
            ("Methyl iso-eugenol", "", "M", 0, 8, 0), ("alpha-Terpineol", "", "T", 0, 0, 10), ("Trichloromethylphenylcarbinyl acetate", "10", "B", 20, 0, 0),
        ],
        "enhancers": {"Top": ["Bergamot Oil FCF", "Carrot Seed Oil 10%"], "Middle": ["Clary Sage Oil 10%", "Clove Bud Oil", "Jasmin Absolute", "Orange Flower Absolute", "Rose Otto 10%", "Ylang-Ylang Oil Extra"],
                      "Base": ["Benzoin Resinoid", "Styrax Resinoid", "Black Pepper Oil"]},
    },
    ("Lilac", 466): {
        "rows": [
            ("Lyral", "", 23, "B", 23, 23, 23), ("Lilial", "", 10, "B", 0, 1, 0), ("Anisyl alcohol", "", 15, "M", 0, 0, 9), ("Anisaldehyde", "", 12, "M", 0, 1, 0),
            ("Heliotropine", "20", 150, "T", 50, 35, 60), ("Benzyl alcohol", "", 30, "T", 5, 0, 10), ("Phenylethyl alcohol", "", 55, "T", 20, 21, 10),
            ("Amylcinnamic aldehyde", "", 5, "B", 0, 0, 4), ("Phenylpropyl alcohol", "", 72, "M", 0, 0, 32), ("alpha-Ionone", "", 4, "M", 0, 0, 2),
            ("Jasmin base", "", 17, "B", 0, 3, 4), ("Indole", "10", 9, "B", 10, 0, 6), ("Linalool", "", 15, "T", 14, 3, 9),
            ("Phenylacetaldehyde dimethylacetal", "", 13, "B", 0, 2, 2), ("Benzyl acetate", "", 14, "T", 11, 2, 8), ("alpha-Terpineol", "", 76, "T", 10, 4, 25),
        ],
        "extension": [
            ("Cinnamyl acetate", "", "M", 0, 3, 0), ("Coumarin", "10", "B", 0, 0, 15), ("Musk ketone", "10", "B", 0, 6, 0),
            ("Hydrocinnamic aldehyde", "10", "M", 15, 0, 10), ("Vanillin", "10", "B", 8, 0, 0),
        ],
        "enhancers": {"Top": ["Basil Oil", "Bergamot Oil FCF", "Coriander Oil 10%", "Petitgrain Oil Bigarade"], "Middle": ["Rose Absolute 10%", "Rose Otto 10%", "Styrax Oil"],
                      "Base": ["Benzoin Resinoid", "Balsam of Peru Resinoid", "Balsam of Tolu Resinoid"]},
    },
    ("Narcissus", 468): {
        "rows": [
            ("Lyral", "", 20, "B", 20, 20, 20), ("Phenylacetaldehyde (in phenylethyl alcohol)", "50", 18, "B", 4, 2, 0), ("Amylcinnamic aldehyde", "", 10, "B", 0, 2, 0),
            ("Benzyl alcohol", "", 18, "M", 0, 0, 2), ("Heliotropine", "", 25, "M", 10, 0, 0), ("Indole", "10", 7, "M", 1, 2, 0),
            ("Methyl naphthyl ketone", "", 18, "B", 0, 0, 13), ("alpha-Terpineol", "", 70, "T", 20, 0, 0), ("Geraniol", "", 28, "T", 10, 0, 0),
            ("Phenylethyl alcohol", "", 23, "T", 0, 10, 0), ("Nerol", "", 36, "T", 0, 30, 0), ("Linalool", "", 35, "T", 10, 40, 5),
            ("Linalyl acetate", "", 14, "T", 0, 0, 3), ("Benzyl acetate", "", 46, "T", 0, 40, 7), ("para-Cresyl acetate", "", 7, "T", 2, 0, 3),
            ("para-Cresyl isobutyrate", "", 5, "T", 1, 0, 1), ("para-Cresyl phenylacetate", "", 20, "T", 7, 14, 3),
        ],
        "extension": [("iso-Butyl phenylacetate", "", "T", 12, 0, 0), ("Phenylpropyl alcohol", "", "M", 0, 0, 20), ("Eugenyl acetate", "", "M", 5, 4, 0), ("Linalyl cinnamate", "", "M", 0, 0, 4)],
        "enhancers": {"Top": ["Bergamot Oil FCF", "Petitgrain Oil Bigarade"], "Middle": ["Jasmin Absolute", "Orange Flower Absolute", "Rose Otto 10%", "Styrax Oil"],
                      "Base": ["Benzoin Resinoid", "Styrax Resinoid"]},
    },
    ("Sweet Pea", 471): {
        "rows": [
            ("Methyl naphthyl ketone", "10", 140, "B", 140, 140, 140), ("Methyl anthranilate", "", 12, "M", 0, 8, 10), ("Lyral", "", 40, "B", 0, 0, 8),
            ("Phenylacetaldehyde dimethyl acetal", "", 18, "M", 4, 12, 16), ("Heliotropine", "20", 190, "M", 0, 45, 70), ("Rose base", "", 14, "B", 7, 1, 6),
            ("Orange Blossom base", "", 9, "B", 0, 40, 30), ("Amylcinnamic aldehyde", "", 17, "B", 14, 0, 0), ("alpha-Ionone", "", 20, "M", 21, 12, 8),
            ("iso-Amyl salicylate", "", 28, "T", 28, 0, 0), ("Musk T (ethylene brassylate)", "", 7, "B", 0, 0, 6), ("Vanillin", "10", 40, "B", 0, 0, 50),
            ("Phenylethyl acetate", "", 4, "T", 0, 0, 6), ("alpha-Terpineol", "", 55, "T", 0, 23, 28), ("Linalool", "", 50, "T", 32, 47, 56),
            ("Linalyl acetate", "", 18, "T", 0, 7, 8), ("Methyl nonylenate", "10", 35, "T", 0, 0, 14), ("para-Methyl acetophenone", "", 17, "T", 14, 0, 0),
        ],
        "extension": [
            ("Aldehyde C10", "1", "T", 0, 4, 0), ("Aldehyde C12 MNA", "10", "T", 0, 0, 6), ("Benzophenone", "", "B", 12, 0, 0),
            ("iso-Butyl phenylacetate", "", "T", 0, 3, 0), ("Coumarin", "10", "B", 40, 0, 0), ("Indole", "1", "M", 6, 0, 0),
        ],
        "enhancers": {"Top": ["Bergamot Oil FCF", "Petitgrain Oil Bigarade", "Sweet Orange Oil"], "Middle": ["Orange Flower Absolute", "Rose Otto 10%", "Styrax Oil", "Ylang-Ylang Oil Extra"],
                      "Base": ["Benzoin Resinoid", "Styrax Resinoid"]},
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


# ---------------------------------------------------------------------------------------------------------------
# 5. monographs (Ch 5 aroma chemicals, Ch 6 naturals) from the word-boxed OCR
# ---------------------------------------------------------------------------------------------------------------
BOXES = REF / "curtis_boxes"
CHEM_PAGES, NAT_PAGES = range(165, 232), range(258, 310)
LABELS = ["Appearance", "Storage", "Stability", "IFRA", "Applications", "Occurrence", "Experiment",
          "Natural source", "Geographical source", "Production technique", "Chief constituents"]
LABEL_KEY = {l.casefold(): l for l in LABELS}
HEADER_WORDS = re.compile(r"^(Ch\.|\[Ch\.|Aromatic materials|\d{3}$)")
NOTE_CLASS = {"top": "Top", "middle": "Middle", "basic": "Basic"}
VALUE_X = 700                 # values start right of the label column


def _lines(page: int) -> list[dict]:
    f = BOXES / f"p{page:03d}.json"
    if not f.exists():
        return []
    d = json.loads(f.read_text(encoding="utf-8"))
    out = []
    for ln in d.get("lines", []):
        ws = ln["words"]
        out.append({"text": ln["text"].strip(), "x": ws[0]["x"], "x1": ws[-1]["x"] + ws[-1]["w"], "y": ws[0]["y"],
                    "h": max(w["h"] for w in ws), "words": ws})
    return sorted(out, key=lambda l: (l["y"], l["x"]))


def _anchors(lines: list[dict]) -> list[dict]:
    """The 'Top/Middle/Basic note' marker of every monograph on the page (one line for naturals, two for aroma chemicals)."""
    out = []
    for i, ln in enumerate(lines):
        t = ln["text"].casefold()
        m = re.match(r"^(top|middle|basic)\s+note$", t)
        if m:
            out.append({"cls": NOTE_CLASS[m.group(1)], "y": ln["y"], "x": ln["x"]})
            continue
        if t in NOTE_CLASS:
            nxt = [l for l in lines if l["text"].casefold() == "note" and 0 < l["y"] - ln["y"] < 80 and abs(l["x"] - ln["x"]) < 80]
            if nxt:
                out.append({"cls": NOTE_CLASS[t], "y": ln["y"], "x": ln["x"]})
    return sorted(out, key=lambda a: a["y"])


def _intensity(lines: list[dict], anchor: dict, y_end: int) -> str:
    digits = [w for ln in lines for w in ln["words"] if w["t"] in list("0123456") and abs(w["x"] - anchor["x"] - 35) < 90
              and anchor["y"] < w["y"] < min(y_end, anchor["y"] + 460)]
    if not digits:
        return ""
    tall = [w for w in digits if w["h"] >= 34]
    if len(tall) == 1:
        return tall[0]["t"]
    return ""                                                  # ambiguous: leave blank rather than guess


def parse_monographs() -> list[dict]:
    rows = []
    for kind, pages in (("aroma chemical", CHEM_PAGES), ("natural", NAT_PAGES)):
        for page in pages:
            lines = _lines(page)
            if not lines:
                continue
            anchors = _anchors(lines)
            for k, a in enumerate(anchors):
                y_end = anchors[k + 1]["y"] - 40 if k + 1 < len(anchors) else 10 ** 6
                # the previous monograph owns everything down to 70 px below its last field label (a wrapped value line)
                prev_labels = [l["y"] for l in lines if l["y"] < a["y"] and l["x"] < VALUE_X and l["text"].casefold() in LABEL_KEY]
                y_start = max([230] + [y + 70 for y in prev_labels])
                # title: the centred bold line just above / beside the anchor
                cands = [l for l in lines if max(y_start, a["y"] - 170) <= l["y"] <= a["y"] + 45 and l["x"] > 450 and l["x1"] < 1700 and len(l["text"]) < 60
                         and not HEADER_WORDS.match(l["text"]) and l["text"].casefold() not in LABEL_KEY and not re.match(r"^[PSBCTD]\s", l["text"])
                         and l["text"].casefold() not in ("note",) and not re.match(r"^(top|middle|basic)", l["text"].casefold())
                         and abs((l["x"] + l["x1"]) / 2 - 990) < 300]
                title = ""
                if cands:
                    best = min(cands, key=lambda l: (abs((l["x"] + l["x1"]) / 2 - 990), -l["h"]))
                    title = best["text"]
                # odour codes: a single letter P/S/B/C (aroma chemicals) or T/B/D (naturals) in the right column, its text on the same line
                # or as a separate OCR line at the same y further right
                codes = {}
                letters = [l for l in lines if a["y"] - 60 <= l["y"] <= y_end and l["x"] > 1150 and (l["text"] in list("PSBCTD") or re.match(r"^[PSBCTD]\s+\S", l["text"]))]
                for l in letters:
                    m = re.match(r"^([PSBCTD])\s+(.+)$", l["text"])
                    if m:
                        codes[m.group(1)] = m.group(2).strip()
                    else:
                        same = [t for t in lines if abs(t["y"] - l["y"]) < 25 and t["x"] > l["x1"] and t["x"] < l["x1"] + 200]
                        codes[l["text"]] = " ".join(t["text"] for t in same).strip()
                labels = [l for l in lines if a["y"] < l["y"] < y_end and l["x"] < VALUE_X and l["text"].casefold() in LABEL_KEY]
                labels.sort(key=lambda l: l["y"])
                first_label_y = labels[0]["y"] if labels else y_end
                chem_name = ""
                if kind == "aroma chemical":
                    mids = [l for l in lines if a["y"] + 380 < l["y"] < first_label_y - 10 and l["x"] > 300 and len(l["text"]) > 3
                            and not re.match(r"^[PSBC]\s", l["text"]) and l["text"].casefold() not in LABEL_KEY]
                    if mids:
                        chem_name = max(mids, key=lambda l: len(l["text"]))["text"]
                fields = {}
                for i, lab in enumerate(labels):
                    y0 = lab["y"] - 15
                    y1 = (labels[i + 1]["y"] - 15) if i + 1 < len(labels) else y_end
                    vals = [l["text"] for l in lines if y0 <= l["y"] < y1 and l["x"] >= VALUE_X - 160 and l["x"] > lab["x1"] - 40]
                    fields[LABEL_KEY[lab["text"].casefold()]] = " ".join(vals).strip()
                title = TITLE_FIX.get(title, title)
                if not title or len(title) < 3:
                    continue
                rows.append({"Material": title, "Kind": kind, "Chemical_Name": chem_name, "Curtis_Note_Class": a["cls"],
                             "Intensity_1_6": _intensity(lines, a, first_label_y), "Code_P_or_T": codes.get("P", codes.get("T", "")),
                             "Code_S_or_B": codes.get("S", codes.get("B", "")), "Code_B_or_D": codes.get("B", codes.get("D", "")) if kind == "aroma chemical" else codes.get("D", ""),
                             "Code_C": codes.get("C", ""), "Appearance": fields.get("Appearance", ""), "Storage": fields.get("Storage", ""),
                             "Stability": fields.get("Stability", ""), "IFRA_1994_superseded": fields.get("IFRA", ""), "Applications": fields.get("Applications", ""),
                             "Occurrence": fields.get("Occurrence", ""), "Natural_Source": fields.get("Natural source", ""),
                             "Geographical_Source": fields.get("Geographical source", ""), "Production": fields.get("Production technique", ""),
                             "Chief_Constituents": fields.get("Chief constituents", ""), "Experiment": fields.get("Experiment", ""),
                             "Source": src(page, "Ch 5 monograph" if kind == "aroma chemical" else "Ch 6 monograph")})
    return rows


TITLE_FIX = {"Aldehyde cg": "Aldehyde C8", "Aldehyde CIO": "Aldehyde C10", "Aldehyde Cll (-enic)": "Aldehyde C11 (-enic)", "Aldehyde Cll (-ylic)": "Aldehyde C11 (-ylic)",
             "Aldehyde (MNA)": "Aldehyde C12 (MNA)", "I-Citronellol": "l-Citronellol", "I-Menthol": "l-Menthol", "Nonane-I,3-diol diacetate": "Nonane-1,3-diol diacetate",
             "Vertenex (IFE)": "Vertenex (IFF)", "Trichloromethylphenylcarbinyl": "Trichloromethylphenylcarbinyl acetate"}


# ---------------------------------------------------------------------------------------------------------------
# 6. Chapter 3 odour vocabulary (PDF p.66-91): three-letter code | descriptor word | origin | related descriptors
# ---------------------------------------------------------------------------------------------------------------
VOCAB_PAGES = range(66, 92)
CODE_ITEM = re.compile(r"([A-Z][A-Za-z\-' ]+?)(?:-re1?lated|, coloured,|, white,)?\s*\(([A-Z]{2,3})\)")


def parse_vocabulary() -> list[dict]:
    rows = []
    for page in VOCAB_PAGES:
        lines = _lines(page)
        codes = [l for l in lines if l["x"] < 440 and re.fullmatch(r"[A-Z]{2,3}", l["text"]) and l["y"] > 240]
        codes.sort(key=lambda l: l["y"])
        for k, c in enumerate(codes):
            y_end = codes[k + 1]["y"] - 20 if k + 1 < len(codes) else 10 ** 6
            word = [l for l in lines if abs(l["y"] - c["y"]) < 25 and 440 <= l["x"] < 560]
            origin = [l for l in lines if abs(l["y"] - c["y"]) < 25 and l["x"] > 1300]
            body = [l for l in lines if c["y"] + 25 < l["y"] < y_end and 440 <= l["x"] < 560]
            text = " ".join(l["text"] for l in body)
            descs = [(m.group(1).strip(), m.group(2)) for m in CODE_ITEM.finditer(text)]
            if not word:
                continue
            rows.append({"Code": c["text"], "Word": word[0]["text"], "Origin": origin[0]["text"] if origin else "",
                         "Related": "|".join(f"{n} ({cd})" for n, cd in descs), "Related_Codes": "|".join(cd for _, cd in descs),
                         "Text": text if not descs else "", "Source": src(page, "Ch 3 odour vocabulary")})
    return rows


VOCAB_COLS = ["Code", "Word", "Origin", "Related", "Related_Codes", "Text", "Source"]


MONO_COLS = ["Material", "Kind", "Chemical_Name", "Curtis_Note_Class", "Intensity_1_6", "Code_P_or_T", "Code_S_or_B", "Code_B_or_D", "Code_C", "Appearance", "Storage",
             "Stability", "IFRA_1994_superseded", "Applications", "Occurrence", "Natural_Source", "Geographical_Source", "Production", "Chief_Constituents", "Experiment", "Source"]


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

    if BOXES.exists():
        vocab = parse_vocabulary()
        write(REF / "curtis_odour_vocabulary.csv", vocab, VOCAB_COLS)
        mono = parse_monographs()
        write(REF / "curtis_monographs.csv", mono, MONO_COLS)
        n_int = sum(1 for r in mono if r["Intensity_1_6"])
        print(f"   monographs: {sum(1 for r in mono if r['Kind'] == 'aroma chemical')} aroma chemicals, {sum(1 for r in mono if r['Kind'] == 'natural')} naturals; "
              f"intensity read for {n_int}")
    else:
        print("   (no reference/curtis_boxes — run data/winocr_boxes.ps1 on the page images to regenerate curtis_monographs.csv)")

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
