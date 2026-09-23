"""Build data/user_lexicon.csv — everyday words and phrases -> the catalogue's own accord terms (Zone A's datasheet).

    python data/build_user_lexicon.py        # rewrites user_lexicon.csv; every row keeps its Source and Decided_By

Three layers, in order of authority:
  1. Curtis & Williams 1994, Ch 3 'Tables of odour descriptive words' (reference/curtis_odour_vocabulary.csv): a perfumery
     word and the descriptors the authors relate it to ('Honeysuckle: sweet, floral, heavy, orange flower, tuberose, honey,
     rose') — mapped to catalogue terms through CODE_TERM. Cited to the page.
  2. Ohloff, Pickenhagen & Kraft 2e, Ch 9.3 (reference/ohloff_families.csv): every material the authors file under one of the
     nine olfactory families -> that family's terms, plus the specific term the material name carries (rose oil -> rose).
  3. Everyday language (ocean, cookies, clean laundry, 'not too strong' …) — AI-authored, marked Decided_By=ai, reviewable.
Rows the user promotes from the input log (data/review_input_log.py) are appended by that script with Source='input log'.

Accord_Terms is 'term:weight;term:weight' — the weights only order the terms; the matcher and the inventor read the order.
Every term is checked against the catalogue vocabulary at build time; an unknown term fails the build.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
OUT = HERE / "user_lexicon.csv"
COLS = ["Phrase", "Accord_Terms", "Family", "Gender", "Season", "Strength", "Kind", "Source", "Decided_By", "Apply"]

# Curtis three-letter descriptor codes -> catalogue accord term ('' = a quality word, not an accord)
CODE_TERM = {
    "FLO": "floral", "SWE": "sweet", "HNY": "honey", "ROS": "rose", "TBR": "tuberose", "JAS": "jasmine", "GRN": "green", "GRE": "green",
    "FRU": "fruity", "WDY": "woody", "BAL": "balsamic", "AMB": "amber", "MUS": "musky", "PDR": "powdery", "VAN": "vanilla", "HER": "herbal",
    "FRE": "fresh", "ERT": "earthy", "RES": "resinous", "VIO": "violet", "OFL": "white floral", "CON": "coniferous", "FOR": "coniferous",
    "ALM": "almond", "CLV": "warm spicy", "WRM": "warm", "MAR": "marine", "MEN": "minty", "MN": "minty", "AGR": "aromatic", "VEG": "green",
    "CML": "caramel", "ANM": "animalic", "ANI": "anis", "CMT": "balsamic", "BEN": "balsamic", "LLY": "floral", "LLC": "floral", "LLW": "floral",
    "HAW": "floral", "HLT": "powdery", "CIT": "citrus", "LEM": "citrus", "SPI": "spicy", "MOS": "mossy", "LEA": "leather", "SMK": "smoky",
    "TOB": "tobacco", "CED": "woody", "SAN": "sandalwood", "PAT": "patchouli", "VET": "vetiver", "LAV": "lavender", "INC": "incense", "COC": "coconut",
    "CHO": "chocolate", "COF": "coffee", "TEA": "tea", "MET": "metallic", "MLK": "milky", "OZO": "ozonic", "GRS": "grassy", "PIN": "coniferous",
    "CAM": "camphor", "TER": "", "RIC": "", "HVY": "", "WY": "", "HW": "", "SOF": "", "DEL": "", "DIF": "", "DRY": "", "SHP": "", "PGT": "", "BIT": "", "LHT": "", "PHE": "",
    "WTG": "minty", "GER": "rose", "CIN": "cinnamon", "CLO": "warm spicy", "NMG": "warm spicy", "GGR": "warm spicy", "CMN": "spicy", "PCH": "fruity",
    "SBY": "fruity", "RBY": "fruity", "PNA": "tropical", "WMN": "fruity", "PRN": "fruity", "JPR": "pear", "VIN": "boozy", "TRP": "tropical", "HAY": "herbal",
    "UMB": "herbal", "CNL": "camphor", "ETH": "fresh", "IND": "animalic", "CIV": "animalic", "EQI": "animalic", "FCL": "animalic", "CRE": "animalic",
    "CIS": "amber", "LAB": "amber", "MYR": "resinous", "OPO": "resinous", "PER": "balsamic", "STY": "balsamic", "TOL": "balsamic", "GLB": "green",
    "HIB": "woody", "RWD": "woody", "YLA": "white floral", "CNA": "warm spicy", "CAS": "floral", "CYC": "floral", "GDN": "white floral", "HON": "floral",
    "HCT": "green", "JON": "floral", "WAL": "floral", "SUL": "", "FNG": "warm spicy", "STL": "",
}
# what a Curtis entry word itself means when it has no related descriptors (from the entry's own definition text)
WORD_SELF = {"peach": "fruity", "pineapple": "tropical", "raspberry": "fruity", "strawberry": "fruity", "watermelon": "fruity", "prune": "fruity",
             "jargonelle pear": "pear", "cumin": "spicy", "ginger": "warm spicy", "nutmeg": "warm spicy", "fenugreek": "warm spicy", "geranium": "rose",
             "honey": "honey", "metallic": "metallic", "camphorous or camphoraceous": "camphor", "mentholic": "minty", "cineolic": "camphor",
             "tropical": "tropical", "vinous": "boozy", "equine": "animalic", "faecal": "animalic", "indolic": "animalic", "ethereal": "fresh",
             "powdery": "powdery", "resinous": "resinous", "sweet": "sweet", "warm": "warm", "fresh": "fresh", "hay": "herbal", "vegetable": "green",
             "umbelliferous": "herbal", "cedarwood": "woody", "hibawood": "woody", "rosewood": "woody", "civet": "animalic", "cistus": "amber",
             "labdanum": "amber", "myrrh": "resinous", "opopanax": "resinous", "peru balsam": "balsamic", "styrax": "balsamic", "tolu balsam": "balsamic",
             "vanilla": "vanilla", "galbanum": "green", "pine": "coniferous", "violet": "violet", "jasmin": "jasmine", "carnation": "warm spicy",
             "heliotrope": "powdery", "lily": "floral", "lilac": "floral", "lilac (coloured)": "floral", "lilac (white)": "floral", "hyacinth": "green",
             "jonquil": "floral", "wallflower": "floral", "cassie": "floral", "clover": "honey", "cyclamen": "floral", "gardenia": "white floral",
             "hawthorn": "almond", "honeysuckle": "floral", "ylang-ylang": "white floral", "light": "", "heavy": "", "diffusive": "", "dry": "",
             "sharp": "", "pungent": "", "stale": "", "sulphurous": "", "cresylic": ""}
# Ohloff family -> terms; material-name fragments -> the specific catalogue term
FAMILY_TERMS = {"Fruity": ["fruity"], "Aldehydic": ["aldehydic"], "Herbal": ["herbal", "aromatic"], "Marine or Ozony": ["marine", "aquatic", "ozonic"],
                "Floral": ["floral"], "Spicy": ["spicy"], "Woody": ["woody"], "Animalic": ["animalic"], "Balsamic": ["balsamic"]}
FRAGMENT_TERM = [  # (regex on the material name, term) — first match wins per pattern, several may apply
    (r"rose", "rose"), (r"damascen", "rose"), (r"citronellol|geraniol|phenylethanol|phenyl ethyl|palmarosa|geranium", "rose"),
    (r"jasmin", "jasmine"), (r"benzyl acetate|hedione|jasmone", "jasmine"), (r"tuberose", "tuberose"), (r"violet|ionone|undecavertol", "violet"),
    (r"orris|irone", "iris"), (r"neroli|orange flower|orange blossom|ylang|methyl anthranilate|narcisse|osmanthus", "white floral"),
    (r"sandal|santal|javanol|polysantol|sandranol", "sandalwood"), (r"vetiver", "vetiver"), (r"patchouli", "patchouli"), (r"oak ?moss|evernyl|moss", "mossy"),
    (r"cedar|cedr", "woody"), (r"musk|ambrette|brassylate|galaxolide|tonalide|fixolide|habanolide|globalide|helvetolide|muscenone|exaltolide", "musky"),
    (r"ambro|amber|ambrox|cistus|labdanum|ambergris", "amber"), (r"\boud\b|agarwood", "oud"), (r"leather|quinol|castoreum|suederal", "leather"),
    (r"civet|indole|skatole", "animalic"), (r"vanill", "vanilla"), (r"cinnam", "cinnamon"), (r"cardamom", "cardamom"), (r"clove|eugenol|carnation", "warm spicy"),
    (r"pepper|ginger|nutmeg|saffron|cumin|pimento|allspice", "spicy"), (r"lemon|orange oil|bergamot|lime|mandarin|grapefruit|citr|yuzu", "citrus"),
    (r"mint|menthol|carvone", "minty"), (r"anis|anethol|estragol|tarragon|basil", "anis"), (r"lavender|lavandin", "lavender"), (r"coffee", "coffee"),
    (r"cocoa|chocolate", "chocolate"), (r"coconut", "coconut"), (r"honey", "honey"), (r"\btea\b", "tea"), (r"tobacco", "tobacco"),
    (r"hexen|galbanum|green", "green"), (r"calone|seaweed|helional", "marine"), (r"coumarin|tonka", "sweet"), (r"heliotrop", "powdery"),
    (r"benzoin", "resinous"), (r"incense|olibanum|frankincense", "incense"), (r"myrrh|elemi|opoponax|opopanax", "resinous"), (r"maltol", "caramel"),
    (r"lactone", "lactonic"), (r"aldehyde", "aldehydic"), (r"\bfig\b", "fig"), (r"pear", "pear"), (r"apple|peach|raspberry|cassis|blackcurrant|davana|agrumex|octalactone|undecalactone", "fruity"),
    (r"juniper|pine|fir|cypress", "coniferous"), (r"eucalyptus|camphor|cineole", "camphor"), (r"rosemary|thyme|sage|artemisia|cedar leaf|laurel|clary", "herbal"),
    (r"iso e super|cashmeran|guaiac|cypriol|timber|vertofix", "woody"), (r"cade|birch|styrax", "smoky"), (r"beeswax", "beeswax"), (r"hay", "herbal"),
    (r"ethyl maltol", "caramel"), (r"cyclamen|florol|florosa|florhydral|linalool|lilial|lyral", "floral"), (r"anisaldehyde", "anis"),
    (r"styralyl|styrallyl", "green"), (r"caryophyllene", "spicy"), (r"phenylacetaldehyde", "green"), (r"benzyl salicylate|hexyl salicylate", "floral"),
    (r"nonadienal", "green"), (r"octenol", "earthy"), (r"geosmin", "earthy"),
]
# everyday language (AI-authored; every row is a decision a human can veto). weights order the terms.
EVERYDAY = [
    # scenes
    ("ocean", "aquatic:1;marine:0.9;salty:0.7"), ("sea", "aquatic:1;marine:0.9;salty:0.7"), ("sea breeze", "marine:1;aquatic:0.9;fresh:0.6"), ("beach", "aquatic:1;salty:0.8;coconut:0.5;tropical:0.5"),
    ("beachy", "aquatic:1;salty:0.8;coconut:0.5;tropical:0.5"), ("seaside", "marine:1;salty:0.8"), ("seawater", "marine:1;salty:0.9"), ("surf", "aquatic:1;ozonic:0.6"), ("waves", "aquatic:1;ozonic:0.6"),
    ("rain", "ozonic:1;green:0.6;damp:0.6"), ("after the rain", "earthy:1;damp:0.8;green:0.7;ozonic:0.6"), ("petrichor", "earthy:1;damp:0.9;mineral:0.5"), ("wet earth", "earthy:1;damp:0.9"),
    ("wet soil", "earthy:1;damp:0.9"), ("soil", "earthy:1"), ("dirt", "earthy:1"), ("mud", "earthy:1;damp:0.7"), ("forest", "coniferous:1;green:0.8;woody:0.7;mossy:0.5"), ("woods", "woody:1;coniferous:0.6"),
    ("pine forest", "coniferous:1;green:0.6"), ("pine", "coniferous:1"), ("christmas tree", "coniferous:1;resinous:0.6"), ("fir", "coniferous:1"), ("cedar", "woody:1"),
    ("pencil shavings", "woody:1"), ("sawdust", "woody:1"), ("campfire", "smoky:1;woody:0.7"), ("bonfire", "smoky:1;woody:0.7"), ("smoke", "smoky:1"), ("fireplace", "smoky:1;woody:0.8;warm:0.5"),
    ("grass", "grassy:1;green:0.9"), ("cut grass", "grassy:1;green:0.9"), ("freshly cut grass", "grassy:1;green:0.9"), ("lawn", "grassy:1;green:0.8"), ("meadow", "green:1;grassy:0.8;floral:0.5"), ("hay", "herbal:1;sweet:0.4"),
    ("garden", "floral:1;green:0.8"), ("flowers", "floral:1"), ("flowery", "floral:1"), ("bouquet", "floral:1"), ("blossom", "floral:1;white floral:0.6"), ("petals", "floral:1;rose:0.5"),
    ("church", "incense:1;resinous:0.7"), ("temple", "incense:1;resinous:0.7;sandalwood:0.5"), ("incense", "incense:1"), ("smoky incense", "incense:1;smoky:0.8"),
    ("library", "woody:0.9;powdery:0.6;inky:0.6;leather:0.5"), ("old books", "powdery:0.8;woody:0.7;inky:0.6"), ("paper", "inky:1;powdery:0.5"), ("ink", "inky:1"),
    ("leather jacket", "leather:1"), ("saddle", "leather:1;animalic:0.5"), ("new car", "leather:1;metallic:0.4"), ("cigar", "tobacco:1;woody:0.5"), ("cigarettes", "tobacco:1;smoky:0.6"), ("pipe tobacco", "tobacco:1;sweet:0.5"),
    ("whisky", "boozy:1;whisky:1"), ("whiskey", "boozy:1;whisky:1"), ("rum", "boozy:1;rum:1"), ("wine", "boozy:1;fruity:0.5"), ("cognac", "boozy:1"), ("liquor", "boozy:1"), ("booze", "boozy:1"), ("bourbon", "boozy:1;bourbon:1"), ("gin", "boozy:0.9;coniferous:0.7;citrus:0.5"),
    ("bakery", "gourmand:1;sweet:0.9;vanilla:0.7"), ("cookies", "gourmand:1;sweet:0.9;vanilla:0.7"), ("cookie", "gourmand:1;sweet:0.9;vanilla:0.7"), ("cake", "gourmand:1;sweet:0.9;vanilla:0.7"), ("baked", "gourmand:1;sweet:0.8"),
    ("pastry", "gourmand:1;sweet:0.8"), ("dessert", "gourmand:1;sweet:0.9"), ("pudding", "gourmand:1;sweet:0.8;milky:0.5"), ("candy", "sweet:1;fruity:0.6"), ("candyfloss", "sweet:1;caramel:0.6"), ("cotton candy", "sweet:1;caramel:0.6"),
    ("toffee", "caramel:1;sweet:0.8"), ("butterscotch", "caramel:1;sweet:0.8"), ("praline", "nutty:1;caramel:0.8;sweet:0.6"), ("marzipan", "almond:1;sweet:0.7"), ("cherry", "almond:0.8;fruity:0.8"),
    ("ice cream", "milky:1;sweet:0.8;vanilla:0.7"), ("cream", "milky:1;lactonic:0.7"), ("creamy", "milky:1;lactonic:0.7"), ("milk", "milky:1;lactonic:0.7"), ("custard", "vanilla:1;milky:0.8;sweet:0.6"),
    ("hot chocolate", "chocolate:1;milky:0.6;sweet:0.6"), ("cocoa", "chocolate:1;cacao:1"), ("espresso", "coffee:1"), ("latte", "coffee:1;milky:0.7"), ("mocha", "coffee:1;chocolate:0.8"),
    ("spice market", "warm spicy:1;spicy:0.9"), ("spice rack", "warm spicy:1;spicy:0.9"), ("spiced", "spicy:1;warm spicy:0.8"), ("spices", "spicy:1;warm spicy:0.8"), ("chai", "warm spicy:1;tea:0.8;cardamom:0.6"),
    ("gingerbread", "warm spicy:1;cinnamon:0.8;sweet:0.7"), ("pepper", "spicy:1;fresh spicy:0.7"), ("peppery", "spicy:1;fresh spicy:0.7"), ("clove", "warm spicy:1"), ("ginger", "spicy:1;fresh spicy:0.7"), ("nutmeg", "warm spicy:1"),
    ("curry", "warm spicy:1;spicy:0.8"), ("cinnamon roll", "cinnamon:1;sweet:0.8;gourmand:0.7"),
    ("lemon", "citrus:1"), ("lemony", "citrus:1"), ("lime", "citrus:1"), ("orange", "citrus:1"), ("grapefruit", "citrus:1"), ("zesty", "citrus:1;fresh:0.6"), ("citrusy", "citrus:1"), ("tangy", "citrus:0.9;fruity:0.6"), ("lemonade", "citrus:1;sweet:0.5"),
    ("mint", "minty:1"), ("menthol", "minty:1;camphor:0.6"), ("toothpaste", "minty:1"), ("eucalyptus", "camphor:1;herbal:0.6;fresh:0.5"), ("medicinal", "camphor:1;herbal:0.6"), ("vicks", "camphor:1;minty:0.8"),
    ("herbs", "herbal:1;aromatic:0.8"), ("herby", "herbal:1;aromatic:0.8"), ("rosemary", "herbal:1;aromatic:0.9"), ("thyme", "herbal:1;aromatic:0.8"), ("sage", "herbal:1;aromatic:0.8"), ("basil", "herbal:1;green:0.7;anis:0.4"),
    ("liquorice", "anis:1"), ("licorice", "anis:1"), ("aniseed", "anis:1"), ("fennel", "anis:1;herbal:0.6"),
    ("apple", "fruity:1"), ("green apple", "fruity:1;green:0.8"), ("berries", "fruity:1"), ("berry", "fruity:1"), ("peach", "fruity:1;lactonic:0.5"), ("mango", "tropical:1;fruity:0.9"), ("pineapple", "tropical:1;fruity:0.9"),
    ("passion fruit", "tropical:1;fruity:0.9"), ("banana", "tropical:1;fruity:0.8"), ("melon", "fruity:1;aquatic:0.6"), ("plum", "fruity:1;sweet:0.6"), ("juicy", "fruity:1"), ("jam", "fruity:1;sweet:0.8"),
    ("coconut", "coconut:1;tropical:0.7"), ("suntan lotion", "coconut:1;tropical:0.8;solar:0"), ("sunscreen", "coconut:0.9;tropical:0.7;powdery:0.4"), ("pina colada", "coconut:1;tropical:0.9;rum:0.6"), ("holiday", "tropical:0.8;coconut:0.6;citrus:0.5"),
    ("honeyed", "honey:1;honeyed:1"), ("beeswax", "beeswax:1;honey:0.8"), ("nuts", "nutty:1"), ("hazelnut", "nutty:1;gourmand:0.6"), ("almonds", "almond:1;nutty:0.6"),
    ("laundry", "clean:1;soapy:0.8;musky:0.6"), ("clean laundry", "clean:1;soapy:0.8;musky:0.6"), ("fresh sheets", "clean:1;soapy:0.7;musky:0.6"), ("fresh linen", "clean:1;soapy:0.7;musky:0.6"), ("linen", "clean:1;soapy:0.6"),
    ("soap", "soapy:1;clean:0.9"), ("shower", "clean:1;soapy:0.8;fresh:0.7"), ("just showered", "clean:1;soapy:0.8;fresh:0.7"), ("shampoo", "soapy:1;clean:0.8;fruity:0.4"), ("cotton", "clean:1;soapy:0.6;powdery:0.5"),
    ("baby powder", "powdery:1;musky:0.5"), ("talc", "powdery:1"), ("talcum", "powdery:1"), ("makeup", "powdery:1;iris:0.6;violet:0.5"), ("lipstick", "powdery:1;iris:0.7;violet:0.6;rose:0.5"), ("cosmetic", "powdery:1;iris:0.5"),
    ("skin", "musky:1"), ("skin scent", "musky:1;clean:0.6"), ("second skin", "musky:1;clean:0.6"), ("skin-like", "musky:1"), ("cashmere", "musky:1;powdery:0.6;warm:0.5"), ("cosy", "warm:1;amber:0.8;vanilla:0.6"), ("cozy", "warm:1;amber:0.8;vanilla:0.6"),
    ("warm and cozy", "warm:1;amber:0.8;vanilla:0.6"), ("comforting", "warm:1;vanilla:0.7;musky:0.6"), ("sexy", "sensual:1;musky:0.8;amber:0.7"), ("seductive", "sensual:1;musky:0.8;amber:0.7"), ("sensual", "sensual:1;musky:0.8"), ("romantic", "rose:1;floral:0.8;sweet:0.5"),
    ("dark", "smoky:0.8;oud:0.7;leather:0.7;incense:0.6"), ("mysterious", "incense:0.9;oud:0.7;smoky:0.6;amber:0.5"), ("gothic", "incense:1;smoky:0.8;leather:0.6"), ("night", "amber:0.8;oud:0.7;sweet:0.6"), ("evening", "amber:0.8;warm spicy:0.6;sweet:0.5"),
    ("elegant", "iris:0.8;aldehydic:0.7;floral:0.7"), ("classic", "chypre:0.8;aldehydic:0.7;floral:0.6"), ("old-fashioned", "aldehydic:0.9;powdery:0.8;floral:0.6"), ("vintage", "chypre:0.9;aldehydic:0.8;mossy:0.6"),
    ("expensive", "oud:0.8;amber:0.7;iris:0.6"), ("luxurious", "oud:0.8;amber:0.7;iris:0.6"), ("rich", "amber:0.9;warm spicy:0.6;resinous:0.5"), ("opulent", "amber:0.9;oud:0.7;white floral:0.6"),
    ("sporty", "fresh:1;aquatic:0.8;citrus:0.8"), ("gym", "fresh:1;aquatic:0.8;citrus:0.7;clean:0.7"), ("energetic", "citrus:1;fresh:0.9"), ("uplifting", "citrus:1;fresh:0.8"), ("crisp", "fresh:1;green:0.6;citrus:0.6"),
    ("airy", "ozonic:1;fresh:0.8;clean:0.6"), ("breezy", "ozonic:1;fresh:0.8;aquatic:0.6"), ("watery", "aquatic:1"), ("cool", "fresh:1;minty:0.5;aquatic:0.5"), ("icy", "minty:1;fresh:0.8;aquatic:0.5"),
    ("office", "clean:1;fresh:0.7;soft spicy:0.4"), ("work", "clean:1;fresh:0.7"), ("professional", "clean:1;woody:0.6;fresh:0.6"), ("date night", "sensual:1;amber:0.8;sweet:0.6"), ("club", "sweet:1;amber:0.8;oud:0.6"), ("party", "sweet:1;fruity:0.7;amber:0.6"),
    ("wedding", "white floral:1;floral:0.9;musky:0.5"), ("bride", "white floral:1;floral:0.9"), ("summer", "citrus:0.9;aquatic:0.8;fresh:0.8"), ("winter", "amber:0.9;warm spicy:0.8;vanilla:0.6"), ("autumn", "woody:0.9;warm spicy:0.7;earthy:0.5"), ("fall", "woody:0.9;warm spicy:0.7;earthy:0.5"), ("spring", "green:0.9;floral:0.9;fresh:0.7"),
    ("manly", "woody:1;aromatic:0.8;fresh spicy:0.6"), ("masculine", "woody:1;aromatic:0.8;fresh spicy:0.6"), ("feminine", "floral:1;sweet:0.6;powdery:0.5"), ("girly", "sweet:1;fruity:0.8;floral:0.7"), ("unisex", "woody:0.7;citrus:0.6;musky:0.6"),
    ("hippie", "patchouli:1;earthy:0.7;incense:0.6"), ("earthy", "earthy:1"), ("mossy", "mossy:1"), ("green", "green:1"), ("woody", "woody:1"), ("wood", "woody:1"), ("oud", "oud:1"), ("agarwood", "oud:1"), ("musk", "musky:1;musk:1"),
    ("amber", "amber:1"), ("ambery", "amber:1"), ("resin", "resinous:1"), ("balsam", "balsamic:1"), ("vanilla", "vanilla:1"), ("caramel", "caramel:1"), ("chocolate", "chocolate:1"), ("coffee", "coffee:1"), ("tea", "tea:1"), ("green tea", "tea:1;green:0.7;fresh:0.5"),
    ("rose", "rose:1"), ("roses", "rose:1"), ("jasmine", "jasmine:1;white floral:0.8"), ("gardenia", "white floral:1;tuberose:0.6"), ("lily", "white floral:1;floral:0.8"), ("lily of the valley", "floral:1;green:0.6;fresh:0.5"), ("muguet", "floral:1;green:0.6"),
    ("orange blossom", "white floral:1;citrus:0.4"), ("neroli", "white floral:1;citrus:0.6"), ("violet", "violet:1;powdery:0.6"), ("iris", "iris:1;powdery:0.8"), ("orris", "iris:1;powdery:0.8"), ("lavender", "lavender:1;aromatic:0.6"), ("peony", "rose:0.9;floral:0.9;fresh:0.5"),
    ("lilac", "floral:1;powdery:0.4"), ("honeysuckle", "floral:1;honey:0.7;sweet:0.6"), ("magnolia", "white floral:1;citrus:0.4"), ("cherry blossom", "floral:1;powdery:0.5;almond:0.4"), ("freesia", "floral:1;fresh:0.6"), ("ylang", "white floral:1"),
    ("sandalwood", "sandalwood:1;woody:0.7"), ("vetiver", "vetiver:1;earthy:0.5"), ("patchouli", "patchouli:1;earthy:0.6"), ("leather", "leather:1"), ("suede", "suede:1;leather:0.8"), ("tobacco", "tobacco:1"), ("smoky", "smoky:1"), ("smokey", "smoky:1"),
    ("aldehydes", "aldehydic:1"), ("soapy", "soapy:1;clean:0.8"), ("powdery", "powdery:1"), ("musky", "musky:1"), ("animalic", "animalic:1"), ("salty", "salty:1;marine:0.6"), ("mineral", "mineral:1"), ("metallic", "metallic:1"), ("nutty", "nutty:1"),
    ("sweet", "sweet:1"), ("sugary", "sweet:1;caramel:0.5"), ("fresh", "fresh:1"), ("clean", "clean:1"), ("warm", "warm:1;amber:0.6"), ("spicy", "spicy:1"), ("fruity", "fruity:1"), ("floral", "floral:1"), ("citrus", "citrus:1"), ("aquatic", "aquatic:1"), ("marine", "marine:1"),
    ("gourmand", "gourmand:1"), ("edible", "gourmand:1;sweet:0.7"), ("foodie", "gourmand:1;sweet:0.7"), ("boozy", "boozy:1"), ("oriental", "oriental:1;amber:0.8;warm spicy:0.6"), ("chypre", "chypre:1;mossy:0.7"), ("fougere", "aromatic:1;lavender:0.8;mossy:0.6"), ("fougère", "aromatic:1;lavender:0.8;mossy:0.6"),
    ("aromatic", "aromatic:1"), ("herbal", "herbal:1"), ("balsamic", "balsamic:1"), ("resinous", "resinous:1"), ("coniferous", "coniferous:1"), ("camphor", "camphor:1"), ("tropical", "tropical:1"), ("milky", "milky:1"), ("lactonic", "lactonic:1"), ("honey", "honey:1"), ("almond", "almond:1"),
]
STRENGTH_PHRASES = [  # phrase -> strength 1..5 (also read by the input handler's qualifier logic)
    ("beast mode", 5), ("fills the room", 5), ("fill the room", 5), ("projects", 5), ("projection", 5), ("long lasting", 5), ("long-lasting", 5), ("lasts all day", 5), ("all day", 5), ("powerful", 5), ("very strong", 5),
    ("strong", 4), ("noticeable", 3), ("moderate", 3), ("medium", 3), ("not too strong", 2), ("not overpowering", 2), ("not too heavy", 2), ("not too loud", 2), ("subtle", 2), ("soft", 2), ("light", 2), ("gentle", 2), ("delicate", 2),
    ("barely there", 1), ("skin scent", 1), ("close to the skin", 1), ("close to skin", 1), ("intimate", 1), ("whisper", 1),
]


def main() -> int:
    from load_data import load_all
    from zone_a_llm.input_handler import vocabulary
    data = load_all()
    vocab = vocabulary(data)
    terms = set(vocab["accords"])
    rows: list[dict] = []
    seen: set[str] = set()

    def add(phrase, pairs, kind, source, decided, family="", gender="", season="", strength=""):
        phrase = phrase.strip().casefold()
        if not phrase or phrase in seen:
            return
        clean = []
        for t, w in pairs:
            if t not in terms:
                raise SystemExit(f"user_lexicon: {phrase!r} -> unknown catalogue term {t!r}")
            if t not in [c for c, _ in clean]:
                clean.append((t, float(w)))
        if not clean and not (family or gender or season or strength):
            return
        seen.add(phrase)
        rows.append({"Phrase": phrase, "Accord_Terms": ";".join(f"{t}:{w:g}" for t, w in clean), "Family": family, "Gender": gender, "Season": season,
                     "Strength": strength, "Kind": kind, "Source": source, "Decided_By": decided, "Apply": "Yes"})

    # 1. Curtis Ch 3 vocabulary
    cv = pd.read_csv(HERE / "reference" / "curtis_odour_vocabulary.csv", dtype=str, keep_default_na=False)
    for r in cv.itertuples():
        word = re.sub(r"\s*\(.*?\)", "", r.Word).casefold()
        pairs = []
        self_term = WORD_SELF.get(r.Word.casefold(), "")
        if r.Word.casefold() in terms:
            pairs.append((r.Word.casefold(), 1.0))
        elif self_term:
            pairs.append((self_term, 1.0))
        w = 0.85
        for code in [c for c in r.Related_Codes.split("|") if c]:
            t = CODE_TERM.get(code, "")
            if t and t not in [p for p, _ in pairs]:
                pairs.append((t, round(w, 2)))
                w *= 0.85
        add(word, pairs, "perfumery descriptor", r.Source, "book (Curtis 1994 odour vocabulary)")
        if word.startswith("lilac"):
            add("lilac", pairs, "perfumery descriptor", r.Source, "book (Curtis 1994 odour vocabulary)")

    # 2. Ohloff families
    of = pd.read_csv(HERE / "reference" / "ohloff_families.csv", dtype=str, keep_default_na=False)
    for r in of.itertuples():
        name = re.sub(r"\s*\(.*?\)", "", r.Material).casefold().replace(" abs.", " absolute").replace(" res.", " resinoid")
        pairs = []
        for pat, t in FRAGMENT_TERM:
            if re.search(pat, name) and t not in [p for p, _ in pairs]:
                pairs.append((t, 1.0))
        for t in FAMILY_TERMS.get(r.Family, []):
            if t not in [p for p, _ in pairs]:
                pairs.append((t, 0.7))
        add(name, pairs, "material (Ohloff family)", r.Source, "book (Ohloff 2e family lists)")
        base = re.sub(r"\s+(oil|absolute|resinoid|abs\.|res\.|cryst\.)$", "", name)
        if base != name:
            add(base, pairs, "material (Ohloff family)", r.Source, "book (Ohloff 2e family lists)")

    # 3. everyday language
    for phrase, spec in EVERYDAY:
        pairs = [(p.split(":")[0], float(p.split(":")[1])) for p in spec.split(";") if p and float(p.split(":")[1]) > 0]
        season = {"summer": "Summer", "winter": "Winter", "autumn": "Fall", "fall": "Fall", "spring": "Spring"}.get(phrase, "")
        gender = {"manly": "Men", "masculine": "Men", "feminine": "Women", "girly": "Women", "unisex": "Unisex"}.get(phrase, "")
        add(phrase, pairs, "everyday language", "everyday usage — AI-authored 2026-09-22 (veto by editing this file)", "ai", season=season, gender=gender)
    for phrase, strength in STRENGTH_PHRASES:
        add(phrase, [], "strength", "everyday usage — AI-authored 2026-09-22", "ai", strength=str(strength))

    # keep rows promoted from the input log
    if OUT.exists():
        old = pd.read_csv(OUT, dtype=str, keep_default_na=False)
        for r in old[old["Source"].str.startswith("input log")].itertuples():
            if r.Phrase not in seen:
                rows.append({c: getattr(r, c) for c in COLS}); seen.add(r.Phrase)
    rows.sort(key=lambda r: (r["Kind"], r["Phrase"]))
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS); w.writeheader(); w.writerows(rows)
    kinds = pd.Series([r["Kind"] for r in rows]).value_counts().to_dict()
    print(f"{len(rows)} lexicon rows -> {OUT.name}: {kinds}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
