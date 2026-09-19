"""Ohloff, Pickenhagen, Kraft, *Scent and Chemistry — The Molecular World of Odors*, 2nd edn (Wiley-VCH 2022) ->
cited reference tables for Zone B's creative side.

    python data/mine_ohloff.py            # PDF -> text (pypdf, cached, gitignored) -> reference/ohloff_*.csv

What is taken (numbers and lists only, every row with its PDF page):
  * reference/ohloff_families.csv      the nine olfactory families of Ch 9.3 and the materials the authors file under each
                                        (parsed from the text, PDF p.609-616)
  * reference/ohloff_accords.csv       the basic floral / fruity accords of Ch 9.4 (ingredients; the base ingredient first) p.619-620
  * reference/ohloff_formulas.csv      the quantified trials: rose theme trials 1-6 (Tables 9.2/9.3, p.621) and the
                                        'Eternity' scheme (Table 9.4, p.627) — parts per 1000
  * reference/ohloff_usage_levels.csv  dosages the authors quote for landmark perfumes (Ch 9.6 'Legendary Perfumes', p.626-628)
  * product_types.csv                  gets an Ohloff figure in Cross_Check (Ch 9.6 p.624-625: EdC 2-4 %, EdT 5-20 %, EdP 10-20 %, extrait 15-35 %)
What is NOT taken: odour thresholds — the book quotes them for numbered structures (e.g. '7.260, th 11 ng/l air') in mixed units
(ng/l air vs ng/l water); mapping structure numbers to names by regex is not reliable enough for a safety-adjacent table.

PDF: c:/Users/onedi/Downloads/_OceanofPDF.com_Scent_and_Chemistry_The_Molecular_World_of_Odors_-_Gunther_Ohloff.pdf
"""
from __future__ import annotations

import csv
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REF = HERE / "reference"
PDF = Path(os.environ.get("OHLOFF_PDF", r"C:/Users/onedi/Downloads/_OceanofPDF.com_Scent_and_Chemistry_The_Molecular_World_of_Odors_-_Gunther_Ohloff.pdf"))
TEXT_CACHE = REF / "ohloff_scent_and_chemistry_2e_text.txt"     # gitignored (copyright)
BOOK = "Ohloff, Pickenhagen & Kraft, Scent and Chemistry 2e (Wiley-VCH 2022)"


def extract_text() -> str:
    if TEXT_CACHE.exists():
        return TEXT_CACHE.read_text(encoding="utf-8")
    from pypdf import PdfReader
    if not PDF.exists():
        raise SystemExit(f"{PDF} not found - set OHLOFF_PDF or drop the text cache at {TEXT_CACHE}")
    parts = [f"\n===== PDF PAGE {n} =====\n" + (p.extract_text() or "") for n, p in enumerate(PdfReader(str(PDF)).pages, 1)]
    text = "".join(parts)
    REF.mkdir(exist_ok=True)
    TEXT_CACHE.write_text(text, encoding="utf-8")
    return text


def page_text(text: str, n: int) -> str:
    a = text.find(f"===== PDF PAGE {n} =====")
    b = text.find("===== PDF PAGE ", a + 10)
    return text[a:b]


# ---------------------------------------------------------------------------------------------------------------
# 1. the nine olfactory families (Ch 9.3) — parsed
# ---------------------------------------------------------------------------------------------------------------
FAMILY_PAGES = range(609, 617)
HEADER = re.compile(r"^The ([A-Z][A-Za-z ]+?) Family:")
REF_NUM = re.compile(r"\s*\((?:rac‐|cis‐)?[\d.]+(?:/[\d.]+)?\)\s*$")        # structure numbers like (7.211) or (3.360/3.361)


def parse_families(text: str) -> list[dict]:
    rows, family, desc, page, in_desc = [], "", "", 0, False
    for n in FAMILY_PAGES:
        for raw in page_text(text, n).split("\n"):
            s = raw.strip()
            if not s or s.startswith("====="):
                continue
            m = HEADER.match(s)
            if m:
                family, desc, page, in_desc = m.group(1), s[m.end():].strip(), n, not s.rstrip().endswith(":")
                continue
            if not family:
                continue
            if in_desc:                     # the family's one-sentence description runs until a line ending in ':'
                desc += " " + s
                if s.endswith(":"):
                    in_desc = False
                continue
            if s.startswith("Before evaluating"):   # end of the lists (p.616)
                family = ""
                continue
            name = REF_NUM.sub("", s).strip().replace("‐", "-").replace("‑", "-")
            if name and len(name) < 60 and (not name.endswith(".") or name.endswith((" abs.", " res.", " cryst."))):
                rows.append({"Family": family, "Material": name, "Family_Description": re.sub(r"\s+", " ", desc).rstrip(":"),
                             "Source": f"{BOOK} Ch 9.3, PDF p.{n}"})
    return rows


# ---------------------------------------------------------------------------------------------------------------
# 2. transcribed tables (Ch 9.4 / 9.6) — page-cited
# ---------------------------------------------------------------------------------------------------------------
ACCORDS = [  # (accord, ingredient, position: 1 = the base ingredient the study starts from)
    ("Rose", ["2-Phenylethanol", "Citronellol", "beta-Damascenone"], 619),
    ("Lily of the valley", ["Hedione", "Citronellol", "Cyclamen aldehyde", "Indole"], 619),
    ("Jasmine", ["Hedione", "Benzyl acetate", "Indole"], 619),
    ("Tuberose", ["Benzyl salicylate", "delta-Decalactone", "Methyl anthranilate", "Eugenol", "Indole"], 619),
    ("Violet", ["Isoraldeine (gamma-methyl ionone)", "Undecavertol", "alpha-Ionone"], 619),
    ("Orange flower", ["Linalool", "Methyl anthranilate", "2-Phenylethanol", "Indole"], 619),
    ("Strawberry", ["Maltol", "cis-3-Hexenol", "Aldehyde C-16"], 619),
    ("Peach", ["gamma-Undecalactone", "cis-3-Hexenyl acetate"], 619),
    ("Apple", ["Agrumex", "cis-3-Hexenyl acetate", "Ethyl methyl butyrate"], 619),
    ("Raspberry", ["alpha-Ionone", "Raspberry ketone", "cis-3-Hexenol"], 620),
    ("Pear", ["Hexyl acetate", "Geranyl acetate"], 620),
    ("Cherry", ["Ethyl maltol", "Benzaldehyde"], 620),
]
FORMULAS = [  # (formula, material, parts per 1000, dilution note, page)
    *[("Rose trial 1 (Table 9.2)", m, p, "", 621) for m, p in (("2-Phenylethanol", 500), ("Citronellol", 500), ("Dipropylene glycol", 0))],
    *[("Rose trial 2 (Table 9.2)", m, p, "", 621) for m, p in (("2-Phenylethanol", 500), ("Citronellol", 250), ("Dipropylene glycol", 250))],
    *[("Rose trial 3 (Table 9.2)", m, p, "", 621) for m, p in (("2-Phenylethanol", 500), ("Citronellol", 100), ("Dipropylene glycol", 400))],
    *[("Rose trial 4 (Table 9.3)", m, p, d, 621) for m, p, d in (("2-Phenylethanol", 500, ""), ("Citronellol", 100, ""), ("beta-Damascenone", 40, "dilution not stated in the table; p.619 convention: un-weighable materials go in as 1 % in DPG"), ("Dipropylene glycol", 360, ""))],
    *[("Rose trial 5 (Table 9.3)", m, p, d, 621) for m, p, d in (("2-Phenylethanol", 500, ""), ("Citronellol", 100, ""), ("beta-Damascenone", 20, "see trial 4"), ("Dipropylene glycol", 380, ""))],
    *[("Rose trial 6 (Table 9.3)", m, p, d, 621) for m, p, d in (("2-Phenylethanol", 500, ""), ("Citronellol", 100, ""), ("beta-Damascenone", 10, "see trial 4; the authors' preferred petaly-fruity rose"), ("Dipropylene glycol", 390, ""))],
    *[("Eternity scheme (Table 9.4, Calvin Klein 1988)", m, p, d, 627) for m, p, d in (
        ("Lyral", 300, "HICC — BANNED in the UK/EU since 2021: the scheme is historical, not a formula to run"), ("Citronellol", 60, ""), ("alpha-Ionone", 60, ""),
        ("beta-Ionone", 280, ""), ("Eugenol", 80, ""), ("Heliotropin", 200, ""), ("Indole", 20, "as a 1 % solution in DPG (table states it)"))],
]
USAGE = [  # (material, approx % of the concentrate, perfume, year, note, page)
    ("Hydroxycitronellal", "15", "Diorissimo (Dior)", 1956, "with ca. 8 % Lyral; the transparent muguet heart", 626),
    ("Lyral (HICC)", "8", "Diorissimo (Dior)", 1956, "banned today (UK/EU Annex II)", 626),
    ("Rose oxide", "0.3", "Chloé Eau de Parfum", 2008, "'metallic rose'", 626),
    ("Cedrene", "5", "Chloé Eau de Parfum", 2008, "cedarwood accord", 626),
    ("Florol / Florosa", "10", "Chloé Eau de Parfum", 2008, "petaly aspect", 626),
    ("Sandalwood oil", "25", "Samsara (Guerlain)", 1989, "natural East Indian sandalwood", 626),
    ("Isoraldeine (gamma-methyl ionone)", "13", "Samsara (Guerlain)", 1989, "powdery violet heart", 626),
    ("Galbanum oil", "0.7", "Vent Vert (Balmain)", 1945, "'outrageous amount' — the prototype green", 627),
    ("Patchouli oil", "20", "Angel (Mugler)", 1992, "dark chocolate accord with vanillin and coumarin", 627),
    ("Vanillin", "4", "Angel (Mugler)", 1992, "", 627),
    ("Coumarin", "4", "Angel (Mugler)", 1992, "", 627),
    ("Ambroxan", "15", "Baccarat Rouge 540 (MFK)", 2014, "", 627),
    ("Evernyl", "12", "Baccarat Rouge 540 (MFK)", 2014, "levels previously seen only in fougeres", 627),
    ("Ethyl maltol", "3", "Baccarat Rouge 540 (MFK)", 2014, "'outrageous amount'", 627),
    ("Vanillin", "15", "Musc Ravageur (F. Malle)", 2000, "deliberate overdose", 628),
    ("Musks (total)", "20", "Musc Ravageur (F. Malle)", 2000, "'only' ca. 20 % of musks", 628),
    ("Calone 1951", "0.2", "Kenzo pour Homme", 1991, "first marine note", 628),
    ("Benzyl salicylate", "30", "Kenzo pour Homme", 1991, "salicylate heart, 'quite remarkable for a masculine'", 628),
    ("Iso E Super", "35", "Declaration (Cartier)", 1998, "", 628),
    ("Iso E Super", "50", "Terre d'Hermes", 2006, "the upper end of what a concentrate carries", 628),
]
PRODUCT_CONC = {  # product_types.csv Product_Type -> Ohloff figure (Ch 9.6 p.624-625)
    "Eau de cologne": "Ohloff 2e p.624: 2-4 % (eau de cologne and splash colognes)",
    "Splash cologne": "Ohloff 2e p.624: 2-4 % (eau de cologne and splash colognes)",
    "Eau de toilette": "Ohloff 2e p.624: 5-20 %",
    "Parfum de toilette / Eau de parfum / Esprit de parfum": "Ohloff 2e p.625: 10-20 %",
    "Extrait / parfum": "Ohloff 2e p.625: 15-35 %",
}
PRACTICE = [  # numeric working practice worth keeping next to the tables (used by product_formulation / accord_study docs)
    ("evaluation dilution", "10 % of the material or trial in 85° ethanol; high-impact materials (indole) at 1 %", 616),
    ("standard alcohol", "85 % EtOH as the general fine-fragrance formulation alcohol; demineralised water", 607),
    ("trial arithmetic", "formulate to 1000 parts, weigh 10 g; halve or double a material between trials; un-weighable amounts as 1 % in DPG", 619),
    ("layer timing", "top notes = first 5-10 min; heart up to ~5 h; fond days to weeks on fabric/blotter", 608),
    ("sketch size", "the architecture of a fragrance is 5-10 ingredients; add the rest one at a time in separate trials", 624),
]


def write(path: Path, rows: list[dict], cols: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows):4d} rows -> {path.relative_to(HERE.parent)}")


def main() -> int:
    text = extract_text()
    fam = parse_families(text)
    write(REF / "ohloff_families.csv", fam, ["Family", "Material", "Family_Description", "Source"])
    write(REF / "ohloff_accords.csv",
          [{"Accord": a, "Ingredient": ing, "Position": i + 1, "Role": "base ingredient (study starts here)" if i == 0 else "added, halved / doubled between trials",
            "Source": f"{BOOK} Ch 9.4, PDF p.{pg}"} for a, ings, pg in ACCORDS for i, ing in enumerate(ings)],
          ["Accord", "Ingredient", "Position", "Role", "Source"])
    write(REF / "ohloff_formulas.csv",
          [{"Formula": f, "Material": m, "Parts_per_1000": p, "Note": d, "Source": f"{BOOK} Ch 9.4/9.6, PDF p.{pg}"} for f, m, p, d, pg in FORMULAS],
          ["Formula", "Material", "Parts_per_1000", "Note", "Source"])
    write(REF / "ohloff_usage_levels.csv",
          [{"Material": m, "Approx_Pct_Of_Concentrate": pct, "Perfume": perf, "Year": y, "Note": n, "Source": f"{BOOK} Ch 9.6 'Legendary Perfumes', PDF p.{pg}"}
           for m, pct, perf, y, n, pg in USAGE],
          ["Material", "Approx_Pct_Of_Concentrate", "Perfume", "Year", "Note", "Source"])
    write(REF / "ohloff_practice.csv", [{"Topic": a, "Statement": b, "Source": f"{BOOK} Ch 9, PDF p.{pg}"} for a, b, pg in PRACTICE], ["Topic", "Statement", "Source"])
    # product_types.csv Cross_Check: append the Ohloff figure once
    pt = HERE / "product_types.csv"
    rows = list(csv.DictReader(open(pt, encoding="utf-8")))
    for r in rows:
        add = PRODUCT_CONC.get(r["Product_Type"])
        if add and "Ohloff" not in r.get("Cross_Check", ""):
            r["Cross_Check"] = (r["Cross_Check"] + "; " if r["Cross_Check"] else "") + add
    with open(pt, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("product_types.csv Cross_Check updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
