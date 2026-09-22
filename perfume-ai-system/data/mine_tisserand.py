"""Mine Tisserand & Young, *Essential Oil Safety* 2e (2014) into data/constituents.csv - safety step 0's table.

    python data/mine_tisserand.py              # PDF -> text (pypdf, cached) -> profiles -> constituents.csv
    python data/mine_tisserand.py --dry-run    # parse and report, write nothing

Every essential-oil / absolute profile in the book lists "Key constituents" with published ranges ("Eugenol 68.6-87.0 %").
This tool parses those lines, keeps the constituents the project's safety tables know (ifra_limits / regulatory_uk /
safety_caps / allergens_uk), sums the isomer lines of one CAS inside a block, takes the highest upper bound across the
profile's variants (origins, species, chemotypes) and writes one row per (natural CAS, grade word, constituent CAS) with
the PDF page(s) in Source. Fraction_Used stays Provisional=Yes: it is a literature upper bound until a supplier CoA
replaces it. The mapping from dataset2 CAS to profile title (M below) is hand-maintained; the numbers are not.

PDF: c:/Users/onedi/Downloads/_OceanofPDF.com_Essential_oil_safety_-_Robert_Tiserand_and_Rodney_Young.pdf
"""
from __future__ import annotations

import collections
import csv
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
PDF = Path(os.environ.get("TISSERAND_PDF", r"C:/Users/onedi/Downloads/_OceanofPDF.com_Essential_oil_safety_-_Robert_Tiserand_and_Rodney_Young.pdf"))
TEXT_CACHE = HERE / "reference" / "tisserand_young_2e_text.txt"          # gitignored (copyright) - regenerated from the PDF
PROFILES_JSON = HERE / "reference" / "tisserand_young_2e_profiles.json"  # gitignored - the parsed profiles, for inspection
OUT_CSV = HERE / "constituents.csv"
COLUMNS = ["Natural_Name", "Natural_CAS", "Grade_Word", "Constituent_Name", "Constituent_CAS", "Typical_Min_Pct", "Typical_Max_Pct",
           "Fraction_Used", "Basis", "Source", "Note", "Provisional"]
SRC = "Tisserand & Young, Essential Oil Safety 2e (2014), profile '{title}', PDF p.{pages}"


def extract_text() -> str:
    """PDF -> text with '===== PDF PAGE n =====' markers (pypdf), cached next to the reference tables."""
    if TEXT_CACHE.exists():
        return TEXT_CACHE.read_text(encoding="utf-8")
    from pypdf import PdfReader
    if not PDF.exists():
        raise SystemExit(f"{PDF} not found - set TISSERAND_PDF or drop the text cache at {TEXT_CACHE}")
    parts = []
    for n, page in enumerate(PdfReader(str(PDF)).pages, 1):
        parts.append(f"\n===== PDF PAGE {n} =====\n" + (page.extract_text() or ""))
    text = "".join(parts)
    TEXT_CACHE.parent.mkdir(exist_ok=True)
    TEXT_CACHE.write_text(text, encoding="utf-8")
    return text


# ----------------------------------------------------------------------------------------------------------------
# 1. profile parser
# ----------------------------------------------------------------------------------------------------------------

PAGE = re.compile(r"^===== PDF PAGE (\d+) =====")
SKIP_HDR = re.compile(r"^(Synonyms?:|Family:|Essential oil|Absolute|Resinoid|Oleoresin|Concrete|CO2 extract|Source:|Botanical|Part used|Note:|[A-Z][a-z]+ type$|\s*$)")
CON = re.compile(r"^(.+?)\s+(?:((?:tr|<?\s*[\d.]+))\s*[–\-]\s*)?(<?\s*[\d.]+|tr)\s*%(?:\s*\([^)]*%\))?\s*[a-z]?$")
FORM = re.compile(r"^(Essential oil|Absolute|Resinoid|Oleoresin|Concrete|CO2 extract)$")
STOP = re.compile(r"^(Quality|Safety summary|Non-volatile|Hazards|Adulteration|Notes|Source:|Regulatory|Organ-specific|Systemic|Comments|Our safety|Contraindications|Maximum)")
BACK_STOP = re.compile(r"^(Quality|Safety summary|Non-volatile|Hazards|Adulteration|Regulatory|Organ-specific|Systemic|Comments|Our safety|Contraindications|Maximum)")
SECTION_WORDS = {"Comments", "Safety summary", "Regulatory guidelines", "Organ-specific effects", "Systemic effects", "Notes", "Hazards", "Contraindications", "Quality", "Adulteration"}
TITLE_FIX = {"Taget": "Tagetes"}
def is_title(s):
    s = s.strip()
    return bool(s) and ":" not in s and len(s) < 48 and s[0].isupper() and not s.endswith(",") and not s.startswith(("•", "(")) and not PAGE.match(s) and not SKIP_HDR.match(s) and "%" not in s
def is_ref(s):
    s = s.strip()
    return s.startswith("(") and not s.endswith("%") and bool(re.search(r"\b(19|20)\d\d\b", s) or "et al" in s or re.search(r"\bp\.?\s*\d", s))
def page_at(lines, i):
    for j in range(i, -1, -1):
        m = PAGE.match(lines[j])
        if m: return int(m.group(1))
    return None
def parse_profiles(text: str) -> list[dict]:
    """Text extract (with '===== PDF PAGE n =====' markers) -> [{title, page, botanical, constituents: [{name, lo, hi, variant, form, page, raw}]}].
    A profile starts at a "Botanical name(s):" line; its title is the nearest heading above; an anchor with no heading
    of its own (a second botanical variety inside one profile) is merged into the previous profile as a variant."""
    lines = text.split("\n")
    profiles = []
    for i, ln in enumerate(lines):
        if not re.match(r"^Botanical names?:", ln): continue
        title, variant0 = "", ""
        for j in range(i - 1, max(i - 14, -1), -1):
            s = lines[j].strip()
            if PAGE.match(s) or not s: continue
            if re.match(r"^Botanical names?:", s) or BACK_STOP.match(s) or is_ref(s) or CON.match(s): break
            if re.match(r"^[A-Z][A-Za-z ]+ type$", s): variant0 = s
            if is_title(s) and s not in SECTION_WORDS and not s.endswith("."): title = s; break
        title = TITLE_FIX.get(title, title)
        cons, variant, blocks, form = [], "", 0, ""
        for j in range(i - 1, max(i - 14, -1), -1):
            if FORM.match(lines[j].strip()): form = lines[j].strip(); break
        k, seen_key = i + 1, False
        while k < len(lines) and k < i + 400:
            s = lines[k].strip(); k += 1
            if PAGE.match(s) or not s: continue
            if re.match(r"^Botanical names?:", s): break               # next profile
            if FORM.match(s): form = s
            if s.startswith("Key constituents"):
                seen_key = True; blocks += 1; variant = ""; continue
            if not seen_key: continue
            if STOP.match(s): seen_key = False; continue               # a later "Key constituents:" (other form) re-enables
            if is_ref(s): variant = ""; continue
            if (s.endswith(("–", "-")) and k < len(lines) and re.match(r"^\s*[\d.]+\s*%", lines[k])) or (s.endswith(("+", "&")) and k < len(lines) and CON.match(lines[k].strip())):
                s = s + lines[k].strip(); k += 1                        # wrapped "name 2.3–" / "6.0%"
            m = CON.match(s)
            if m:
                name = m.group(1).strip().rstrip("*").strip()
                lo, hi = m.group(2), m.group(3)
                def num(x):
                    if x is None: return None
                    x = x.replace("<", "").replace("tr", "0").strip()
                    try: return float(x)
                    except ValueError: return None
                cons.append({"name": name, "lo": num(lo) if lo else num(hi), "hi": num(hi), "variant": variant, "form": form, "page": page_at(lines, k - 1), "raw": s})
            elif seen_key and ":" not in s and len(s) < 80 and "%" not in s:
                variant = s                                             # sub-heading like "Bulgarian" / "Sumatra benzoin volatile compounds"
        bot = ln.split(":", 1)[1].strip()
        if not title and profiles and cons:
            lab = variant0 or bot.split(" L.")[0][:40]
            for c in cons: c["variant"] = (lab + (" / " + c["variant"] if c["variant"] else ""))
            profiles[-1]["constituents"].extend(cons); profiles[-1]["blocks"] += blocks; profiles[-1]["botanical"] += " | " + bot
            continue
        profiles.append({"title": title, "page": page_at(lines, i), "line": i, "botanical": bot, "constituents": cons, "blocks": blocks})
    return profiles


# ----------------------------------------------------------------------------------------------------------------
# 2. constituent names -> CAS (only CAS the safety tables know are written) and dataset2 CAS -> profile mapping
# ----------------------------------------------------------------------------------------------------------------
def regulated_cas() -> set[str]:
    """Every CAS the safety tables know: only these constituents are worth rolling up."""
    def rd(n): return pd.read_csv(HERE / n, dtype=str, keep_default_na=False)
    out: set[str] = set()
    for df, col in ((rd("ifra_limits.csv"), "All_CAS"), (rd("regulatory_uk.csv"), "CAS"), (rd("safety_caps.csv"), "CAS"), (rd("allergens_uk.csv"), "All_CAS")):
        for v in df[col]:
            out.update(c.strip() for c in v.split("|") if c.strip())
    return out
CANON = {  # normalised T&Y name -> (Constituent_Name, CAS)
    "eugenol": ("Eugenol", "97-53-0"),
    "isoeugenol": ("Isoeugenol", "97-54-1"), "(e)-isoeugenol": ("Isoeugenol", "97-54-1"), "(z)-isoeugenol": ("Isoeugenol", "97-54-1"),
    "methyleugenol": ("Methyl eugenol", "93-15-2"), "methyl eugenol": ("Methyl eugenol", "93-15-2"),
    "estragole": ("Estragole", "140-67-0"), "methyl chavicol": ("Estragole", "140-67-0"),
    "safrole": ("Safrole", "94-59-7"),
    "(e)-cinnamaldehyde": ("Cinnamic aldehyde", "104-55-2"), "(z)-cinnamaldehyde": ("Cinnamic aldehyde", "104-55-2"), "cinnamaldehyde": ("Cinnamic aldehyde", "104-55-2"),
    "cinnamyl alcohol": ("Cinnamic alcohol", "104-54-1"), "(e)-cinnamyl alcohol": ("Cinnamic alcohol", "104-54-1"),
    "coumarin": ("Coumarin", "91-64-5"),
    "herniarin (7-methoxycoumarin)": ("7-Methoxycoumarin", "531-59-9"), "7-methoxycoumarin": ("7-Methoxycoumarin", "531-59-9"), "herniarin": ("7-Methoxycoumarin", "531-59-9"),
    "dihydrocoumarin": ("Dihydrocoumarin", "119-84-6"), "6-methylcoumarin": ("6-Methylcoumarin", "92-48-8"), "7-methylcoumarin": ("7-Methylcoumarin", "2445-83-2"),
    "benzyl benzoate": ("Benzyl Benzoate", "120-51-4"), "benzyl alcohol": ("Benzyl Alcohol", "100-51-6"),
    "benzyl cinnamate": ("Benzyl Cinnamate", "103-41-3"), "(e)-benzyl cinnamate": ("Benzyl Cinnamate", "103-41-3"), "benzyl (e)-cinnamate": ("Benzyl Cinnamate", "103-41-3"),
    "benzyl salicylate": ("Benzyl Salicylate", "118-58-1"),
    "citronellol": ("Citronellol", "106-22-9"), "(-)-citronellol": ("Citronellol", "106-22-9"), "(+)-citronellol": ("Citronellol", "106-22-9"),
    "geraniol": ("Geraniol", "106-24-1"),
    "linalool": ("Linalool", "78-70-6"), "(-)-linalool": ("Linalool", "78-70-6"), "(+)-linalool": ("Linalool", "78-70-6"),
    "limonene": ("Limonene", "5989-27-5"), "(+)-limonene": ("Limonene", "5989-27-5"), "(-)-limonene": ("Limonene", "5989-27-5"),
    "(+)-limonene + 1,8-cineole": ("Limonene", "5989-27-5"), "(+)-limonene & 1,8-cineole": ("Limonene", "5989-27-5"), "limonene + 1,8-cineole": ("Limonene", "5989-27-5"),
    "geranial": ("Citral", "5392-40-5"), "neral": ("Citral", "5392-40-5"), "citral": ("Citral", "5392-40-5"),
    "citronellal": ("Citronellal", "106-23-0"), "(+)-citronellal": ("Citronellal", "106-23-0"), "(-)-citronellal": ("Citronellal", "106-23-0"),
    "farnesol": ("Farnesol", "4602-84-0"), "(e,e)-farnesol": ("Farnesol", "4602-84-0"), "(z,e)-farnesol": ("Farnesol", "4602-84-0"), "(e,z)-farnesol": ("Farnesol", "4602-84-0"), "(z,z)-farnesol": ("Farnesol", "4602-84-0"),
    "farnesal": ("Farnesal", "19317-11-4"), "(e,e)-farnesal": ("Farnesal", "19317-11-4"),
    "methyl n-methylanthranilate": ("Methyl N-methylanthranilate", "85-91-6"), "methyl n-methyl anthranilate": ("Methyl N-methylanthranilate", "85-91-6"),
    "methyl salicylate": ("Methyl salicylate", "119-36-8"),
    "safranal": ("Safranal", "116-26-7"),
    "benzaldehyde": ("Benzaldehyde", "100-52-7"),
    "carvone": ("Carvone", "99-49-0"), "(+)-carvone": ("Carvone", "99-49-0"), "(-)-carvone": ("Carvone", "99-49-0"),
    "anisyl alcohol": ("Anisyl alcohol", "105-13-5"), "anise alcohol": ("Anisyl alcohol", "105-13-5"), "4-methoxybenzyl alcohol": ("Anisyl alcohol", "105-13-5"),
    "cedrene": ("Cedrene", "11028-42-5"), "a-cedrene": ("Cedrene", "11028-42-5"), "b-cedrene": ("Cedrene", "11028-42-5"),
    "longifolene": ("Longifolene", "475-20-7"),
    "hydroxycitronellal": ("Hydroxycitronellal", "107-75-5"),
    "vanillin": ("Vanillin", "121-33-5"), "guaiacol": ("Guaiacol", "90-05-1"),
    "indole": ("Indole", "120-72-9"), "skatole": ("Skatole", "83-34-1"), "3-methylindole": ("Skatole", "83-34-1"),
    "decanal": ("Aldehyde C-10", "112-31-2"), "undecanal": ("Aldehyde C-11", "112-45-8"), "2-methylundecanal": ("Aldehyde C-12 MNA", "110-41-8"),
    "(e)-2-hexenal": ("2-Hexenal", "6728-26-3"), "2-hexenal": ("2-Hexenal", "6728-26-3"),
    "raspberry ketone": ("Raspberry ketone", "5471-51-2"),
    "methyl 2-octynoate": ("Methyl heptine carbonate", "111-12-6"), "methyl heptine carbonate": ("Methyl heptine carbonate", "111-12-6"),
    "a-amylcinnamaldehyde": ("Alpha-Amyl cinnamic aldehyde", "122-40-7"), "a-hexylcinnamaldehyde": ("Alpha-Hexyl cinnamic aldehyde", "101-86-0"),
    "cyclamen aldehyde": ("Cyclamen aldehyde", "103-95-7"),
    "a-isomethyl ionone": ("Alpha-isomethyl ionone", "127-51-5"),
    "benzyl cyanide": ("Benzyl cyanide", "140-29-4"),
    # combined GC peaks: the whole peak is booked to the regulated member (upper bound)
    "safrole + p -cymen-8-ol": ("Safrole", "94-59-7"), "citronellol + d-cadinene": ("Citronellol", "106-22-9"),
    "1,8-cineole + (+)-limonene": ("Limonene", "5989-27-5"), "(+)-limonene + (z)-b-ocimene": ("Limonene", "5989-27-5"),
    "a-caryophyllene + citronellyl acetate": None,
}
CANON = {k: v for k, v in CANON.items() if v}
SKIP = {"atranol", "chloroatranol"}   # treemoss raw figures; the legal control is the IFRA CoA spec (group_rules ifra_spec_coa), not a roll-up
STEMS = ("eugenol", "estragole", "safrole", "cinnam", "coumarin", "benzyl", "citronell", "geraniol", "linalool", "limonene", "geranial", "neral",
         "farnes", "anthranil", "salicyl", "safranal", "carvone", "cedrene", "vanillin", "indole", "decanal", "hexenal", "anis")
def norm(s):
    s = s.lower().replace("\u2212", "-").replace("\u2013", "-").replace("\u03b1", "a").replace("\u03b2", "b").replace("\u03b3", "g").replace("\u03b4", "d")
    s = re.sub(r"\(([ezrs+\-,\s\d]+)\)", lambda m: "(" + re.sub(r"[\s\d]", "", m.group(1)) + ")", s)
    s = re.sub(r"\s*\*\s*$", "", s); s = re.sub(r"\s+", " ", s).strip()
    return s

# --- dataset2 natural CAS -> T&Y profile(s). grade: Grade_Word (distinct and non-blank when a CAS has >1 profile).
# form / variant: optional substrings that select constituent blocks inside the profile.
M = []
def add(cas, name, title, grade="", form=None, variant=None, note=""):
    M.append(dict(cas=cas, name=name, title=title, grade=grade, form=form, variant=variant, note=note))
add("8006-77-7", "Allspice (pimento berry) oil", "Pimento berry")
add("8015-65-4", "Amyris oil", "Amyris")
add("8015-64-3", "Angelica root oil", "Angelica root")
add("8015-62-1", "Ambrette seed oil", "Ambrette")
add("8022-34-2", "Agarwood (oud) oil", "Agarwood")
add("8008-93-3", "Artemisia (wormwood) oil", "Wormwood")
add("8015-73-4", "Basil oil (linalool CT)", "Basil (linalool CT)", grade="linalool", form="Essential oil", note="European sweet basil; a note name without 'linalool' / 'estragole' -> worst case of both chemotypes")
add("8015-73-4", "Basil oil (estragole CT)", "Basil (estragole CT)", grade="estragole", note="exotic / Comoros type")
add("8006-78-8", "Bay (West Indian) leaf oil", "Bay (West Indian)")
add("9000-05-9", "Benzoin Siam resinoid", "Benzoin", variant="Siam", note="volatile-compound composition of the resinoid")
add("9000-72-0", "Benzoin Sumatra resinoid", "Benzoin", variant="Sumatra", note="volatile-compound composition of the resinoid")
add("8007-75-8", "Bergamot oil expressed", "Bergamot (expressed)", grade="expressed", note="a note name without 'expressed' / 'FCF' -> worst case of both")
add("8007-75-8", "Bergamot oil FCF", "Bergamot (FCF)", grade="FCF")
add("68916-04-1", "Bitter orange peel oil", "Orange (bitter)")
add("8006-82-4", "Black pepper oil", "Pepper (black)")
add("68648-86-2", "Blackcurrant bud absolute", "Blackcurrant bud", form="Absolute")
add("91722-40-6", "Cassis (blackcurrant bud) absolute", "Blackcurrant bud", form="Absolute")
add("8015-77-8", "Rosewood (bois de rose) oil", "Rosewood")
add("8007-01-0", "Rose otto (R. damascena oil)", "Rose (Damask)", grade="otto", note="Bulgarian and Turkish oils, highest bound taken; 'Rose' / 'Rose Oil' without a grade word -> worst case of otto and absolute")
add("8007-01-0", "Rose absolute (closest published profile: R. centifolia)", "Rose (Provence)", grade="absolute", note="T&Y publish no R. damascena absolute; the Provence absolute is the closest profile - replace with the supplier CoA")
add("90106-38-0", "Turkish rose absolute (closest published profile: R. centifolia)", "Rose (Provence)", note="species differ (R. damascena vs R. centifolia); replace with the supplier CoA")
add("8013-10-3", "Cade oil rectified", "Cade (rectified)", grade="rectified")
add("8013-10-3", "Cade oil unrectified (juniper tar)", "Cade (unrectified)", grade="unrectified")
add("8000-66-6", "Cardamom oil", "Cardamon")
add("8015-88-1", "Carrot seed oil", "Carrot seed")
add("8000-27-9", "Cedarwood oil Virginian", "Cedarwood (Virginian)", grade="virginia", note="plain 'Cedarwood' -> worst case of Virginian and Texan")
add("8000-27-9", "Cedarwood oil Texan", "Cedarwood (Texan)", grade="texas")
add("68990-83-0", "Cedarwood oil Texas", "Cedarwood (Texan)")
add("92201-55-3", "Cedarwood oil Atlas", "Cedarwood (Atlas)")
add("8015-91-6", "Cinnamon bark oil", "Cinnamon bark", grade="bark", note="same CAS as the leaf oil - the grade word decides; none -> worst case")
add("8015-91-6", "Cinnamon leaf oil", "Cinnamon leaf", grade="leaf")
add("8007-80-5", "Cassia oil", "Cassia", note="bark and leaf oils, highest bound taken")
add("89997-74-0", "Cistus oil", "Cistus")
add("8016-26-0", "Labdanum", "Labdanum")
add("8000-29-1", "Citronella oil", "Citronella", note="Ceylon (C. nardus) and Java (C. winterianus) types, highest bound taken")
add("8016-63-5", "Clary sage oil", "Clary sage", form="Essential oil")
add("8000-34-8", "Clove bud oil", "Clove bud")
add("8008-52-4", "Coriander seed oil", "Coriander seed")
add("8023-88-9", "Costus root oil", "Costus")
add("8014-13-9", "Cumin seed oil", "Cumin")
add("8013-86-3", "Cypress oil", "Cypress")
add("91771-62-9", "Cypriol (nagarmotha) oil", "Nagarmotha")
add("91745-46-9", "Cypriol (nagarmotha) oil", "Nagarmotha")
add("8016-03-3", "Davana oil", "Davana")
add("8023-89-0", "Elemi oil", "Elemi")
add("8000-48-4", "Eucalyptus oil (cineole-rich)", "Eucalyptus (cineole-rich)", grade="globulus", note="species blocks, highest bound taken; 'citriodora' in the note name selects lemon-scented gum")
add("8000-48-4", "Eucalyptus citriodora oil", "Lemon-scented gum", grade="citriodora")
add("8006-84-6", "Fennel oil sweet", "Fennel (sweet)")
add("90028-76-5", "Fir balsam (Abies balsamea)", "Fir needle (Canadian)")
add("8016-36-2", "Frankincense (olibanum) oil", "Frankincense", note="six Boswellia species, highest bound taken")
add("89957-98-2", "Olibanum resinoid", "Frankincense", note="essential-oil profile used for the resinoid volatiles")
add("8023-91-4", "Galbanum oil", "Galbanum")
add("8000-46-2", "Geranium oil", "Geranium", note="Chinese, Egyptian, Moroccan, Reunion, highest bound taken")
add("8007-08-7", "Ginger oil", "Ginger")
add("8016-20-4", "Grapefruit oil", "Grapefruit")
add("84650-60-2", "Tea leaf absolute", "Tea leaf")
add("8016-23-7", "Guaiacwood oil", "Guaiacwood")
add("8042-47-5", "Hay absolute", "Hay", note="dataset2 carries 8042-47-5 for Hay Absolute (verify - this CAS is also used for mineral oil)")
add("91771-45-8", "Hinoki wood oil", "Hinoki wood")
add("8006-83-5", "Hyssop oil", "Hyssop (pinocamphone CT)")
add("90045-89-9", "Orris (iris) absolute", "Orris", form="Absolute")
add("8002-73-1", "Orris butter (orris oil / concrete)", "Orris", form="Essential oil")
add("84776-64-7", "Jasmine absolute (grandiflorum)", "Jasmine")
add("90045-94-6", "Jasmine absolute (grandiflorum)", "Jasmine")
add("8022-96-6", "Jasmine absolute (grandiflorum)", "Jasmine")
add("91770-14-8", "Jasmine sambac absolute", "Jasmine sambac")
add("8012-91-7", "Juniper berry oil", "Juniperberry")
add("91722-69-9", "Lavandin oil", "Lavandin", form="Essential oil")
add("8000-28-0", "Lavender absolute", "Lavender", grade="absolute", form="Absolute", note="plain 'Lavender' -> worst case of oil and absolute (coumarin / herniarin only in the absolute)")
add("8000-28-0", "Lavender oil", "Lavender", grade="oil", form="Essential oil")
add("8008-56-8", "Lemon oil expressed", "Lemon (expressed)", grade="expressed", note="plain 'Lemon Oil' -> worst case")
add("8008-56-8", "Lemon oil distilled", "Lemon (distilled)", grade="distilled")
add("8007-02-1", "Lemongrass oil", "Lemongrass", note="East and West Indian types, highest bound taken")
add("61789-92-2", "Lentisque (mastic) absolute", "Mastic")
add("8008-26-2", "Lime oil expressed", "Lime (expressed)", grade="expressed", note="Mexican and Persian types; plain 'Lime' -> worst case")
add("8008-26-2", "Lime oil distilled", "Lime (distilled)", grade="distilled")
add("68855-99-2", "Litsea cubeba (may chang) oil", "May chang")
add("8007-12-3", "Mace oil", "Mace")
add("8008-31-9", "Mandarin oil", "Mandarin")
add("8016-87-3", "Mimosa absolute", "Mimosa")
add("8006-67-5", "Mimosa absolute", "Mimosa")
add("8006-90-4", "Peppermint oil", "Peppermint")
add("8014-71-9", "Melissa oil", "Melissa")
add("9000-45-7", "Myrrh", "Myrrh")
add("8016-37-3", "Myrrh oil", "Myrrh")
add("8016-38-4", "Neroli (orange flower) oil", "Neroli", note="Egyptian and Spanish, highest bound taken")
add("8030-28-2", "Orange flower absolute", "Orange flower")
add("8008-45-5", "Nutmeg oil", "Nutmeg", note="East and West Indian types, highest bound taken (safrole / methyl eugenol are East Indian)")
add("90028-68-5", "Oakmoss absolute", "Oakmoss")
add("90028-67-4", "Treemoss absolute", "Treemoss", note="atranol / chloroatranol figures deliberately NOT rolled up: the legal control is the IFRA CoA specification (group_rules)")
add("8021-36-1", "Opoponax", "Opopanax")
add("8008-57-9", "Sweet orange oil", "Orange (sweet)")
add("92347-21-2", "Osmanthus absolute", "Osmanthus")
add("959130-05-3", "Palo santo oil", "Palo santo")
add("8014-09-3", "Patchouli oil", "Patchouli")
add("8007-00-9", "Peru balsam", "Peru balsam")
add("8014-17-3", "Petitgrain (orange leaf) oil", "Orange leaf", form="Essential oil", note="Bigarade and Paraguayan oils, highest bound taken")
add("8002-09-3", "Pine needle oil (Scots)", "Pine (Scots)")
add("68917-52-2", "Pink pepper oil", "Pepper (pink)")
add("8000-25-7", "Rosemary oil", "Rosemary", note="seven chemotypes, highest bound taken")
add("8014-29-7", "Rue oil", "Rue")
add("84604-17-1", "Saffron", "Saffron", note="volatile fraction; T&Y p.1553 say the figures are for the volatiles, so this is an upper bound for an extract")
add("8022-56-8", "Sage oil (Dalmatian)", "Sage (Dalmatian)")
add("8016-65-7", "Sage oil (Spanish)", "Sage (Spanish)")
add("8006-87-9", "Sandalwood oil (East Indian)", "Sandalwood (East Indian)")
add("8008-79-5", "Spearmint oil", "Spearmint")
add("8007-70-3", "Star anise oil", "Anise (star)")
add("8046-19-3", "Styrax", "Styrax", note="L. orientalis and L. styraciflua, highest bound taken")
add("8016-88-4", "Tarragon oil", "Tarragon")
add("8007-46-3", "Thyme oil", "Thyme (thymol CT, carvacrol CT and")
add("9000-64-0", "Tolu balsam", "Tolu balsam", note="volatile-compound composition")
add("8024-04-2", "Tonka bean absolute", "Tonka")
add("8024-05-3", "Tuberose absolute", "Tuberose")
add("8024-06-4", "Vanilla absolute", "Vanilla", note="volatiles / extract / CO2 blocks, highest bound taken")
add("85116-63-8", "Verbena absolute (lemon verbena)", "Verbena (lemon)", form="Essential oil", note="T&Y give no absolute data; the essential-oil profile stands in as an upper bound")
add("8024-12-2", "Verbena oil (lemon verbena)", "Verbena (lemon)", form="Essential oil")
add("8016-96-4", "Vetiver oil", "Vetiver")
add("8024-08-6", "Violet leaf absolute", "Violet leaf")
add("68917-75-9", "Wintergreen oil", "Wintergreen")
add("8006-81-3", "Ylang ylang oil", "Ylang-ylang", form="Essential oil", note="extra / I / II / III / complete grades, highest bound taken")
add("233683-84-6", "Yuzu oil", "Yuzu")
add("8001-88-5", "Birch tar oil", "Birch tar")

def build_rows(profiles: list[dict]) -> tuple[list[dict], dict, list]:
    """Profiles -> constituents.csv rows (one per natural CAS / grade word / constituent CAS), plus review lists."""
    BY = {x["title"]: x for x in profiles}
    regulated = regulated_cas()
    rows, unmapped, no_profile = [], defaultdict(int), []
    for m in M:
        prof = BY.get(m["title"])
        if not prof: no_profile.append(m["title"]); continue
        cons = prof["constituents"]
        if m["form"]: cons = [c for c in cons if c["form"] == m["form"]]
        if m["variant"]: cons = [c for c in cons if m["variant"].lower() in c["variant"].lower()]
        # per variant: sum the isomer lines of one constituent CAS; then the highest bound across variants
        per_var = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0, set()]))
        for c in cons:
            key = norm(c["name"])
            if key in SKIP: continue
            hit = CANON.get(key)
            if not hit:
                if any(w in key for w in STEMS): unmapped[key] += 1
                continue
            if hit[1] not in regulated: continue
            v = per_var[(c["form"], c["variant"])][hit]
            v[0] += c["lo"] or 0.0; v[1] += c["hi"] or 0.0; v[2].add(c["page"])
        best = {}
        for var, d in per_var.items():
            for hit, (lo, hi, pages) in d.items():
                b = best.get(hit)
                if b is None or hi > b[1]: best[hit] = [lo, hi, set(pages), var]
                elif hi == b[1]: b[2] |= pages
        for (cname, ccas), (lo, hi, pages, var) in sorted(best.items(), key=lambda kv: -kv[1][1]):
            if hi <= 0: continue
            frac = min(1.0, round(hi / 100.0, 4))          # (E)+(Z) upper bounds can sum past 100
            rows.append({"Natural_Name": m["name"], "Natural_CAS": m["cas"], "Grade_Word": m["grade"], "Constituent_Name": cname, "Constituent_CAS": ccas,
                         "Typical_Min_Pct": f"{lo:g}", "Typical_Max_Pct": f"{hi:g}", "Fraction_Used": f"{frac:g}",
                         "Basis": "upper bound of the published range (isomers of one CAS summed)" if lo != hi else "single published value (isomers of one CAS summed)",
                         "Source": SRC.format(title=m["title"], pages="/".join(str(p) for p in sorted(pages))),
                         "Note": "; ".join(x for x in ((f"variant: {var[1]}" if var[1] else ""), (f"form: {var[0]}" if var[0] else ""), ("upper bounds of the isomers sum past 100 %, capped at 1.0" if hi > 100 else ""), m["note"]) if x), "Provisional": "Yes"})
    seen = set(); out = []
    for r in rows:                                    # the engine's key
        k = (r["Natural_CAS"], r["Grade_Word"], r["Constituent_CAS"])
        if k in seen: continue
        seen.add(k); out.append(r)
    return out, unmapped, no_profile


# ---------------------------------------------------------------------------------------------------------------
# 3. the book's own dermal maxima (Ch 13 profiles) and Chapter 14 'Sources' lists — second-source cross-checks
# ---------------------------------------------------------------------------------------------------------------
MAXIMA_CSV = HERE / "reference" / "tisserand_dermal_maxima.csv"
CH14_CSV = HERE / "reference" / "tisserand_ch14_sources.csv"
PCT = re.compile(r"(\d+(?:\.\d+)?)\s*%")


def _pct_or_text(s: str) -> str:
    m = PCT.search(s)
    return m.group(1) if m else ("no limit" if re.search(r"no (legal )?limit", s, re.I) else s.strip())


def parse_dermal_maxima(text: str, profiles: list[dict]) -> list[dict]:
    """Every 'Maximum dermal use level' statement of the oil profiles: the single T&Y figure, or the EU / IFRA / T&Y triplet,
    with the constituent the limit is based on ('based on eugenol content') and the owning profile."""
    lines = text.split("\n")
    starts = sorted(pr["line"] for pr in profiles)
    by_line = {pr["line"]: pr for pr in profiles}
    rows = []
    for i, ln in enumerate(lines):
        if not ln.startswith("Maximum dermal use level"):
            continue
        owner = None
        for st in reversed(starts):
            if st < i:
                owner = by_line[st]
                break
        if owner is None or not owner["title"]:
            continue
        basis = ""
        m = re.search(r"\(based on (.+?) content\)", ln)
        if m:
            basis = m.group(1)
        head = ln.split(":", 1)[1] if ":" in ln else ""
        form = ""
        for j in range(owner["line"] - 14, i):                    # the form (Essential oil / Absolute ...) the statement belongs to
            if j >= 0 and FORM.match(lines[j].strip()):
                form = lines[j].strip()
        row = {"Profile": owner["title"], "Form": form, "Basis_Constituent": basis, "EU_Pct": "", "IFRA_Pct": "", "TY_Pct": "", "Single_Pct": "", "Qualifier": "",
               "Source": SRC.format(title=owner["title"], pages=page_at(lines, i))}
        if PCT.search(head):
            row["Single_Pct"] = PCT.search(head).group(1)
            row["Qualifier"] = re.sub(r"^[^%]*%\s*", "", head).strip(" .()")
        else:
            k, seen = i + 1, 0
            while k < len(lines) and k < i + 8 and seen < 3:
                s = lines[k].strip(); k += 1
                if not s or PAGE.match(s):
                    continue
                if s.startswith("EU"):
                    row["EU_Pct"] = _pct_or_text(s[2:]); seen += 1
                elif s.startswith("IFRA"):
                    row["IFRA_Pct"] = _pct_or_text(s[4:]); seen += 1
                elif s.startswith("Tisserand & Young"):
                    row["TY_Pct"] = _pct_or_text(s[len("Tisserand & Young"):]); seen += 1
                else:
                    break
            if not seen:
                continue
        rows.append(row)
    return rows


CH14_HEAD = re.compile(r"^(Synonyms?|Systematic name|Chemical class):")
CH14_SRC = re.compile(r"^(.+?)\s+(?:(?:~|<)\s*)?((?:tr|[\d.]+))(?:\s*[–\-]\s*(<?\s*[\d.]+))?\s*%(?:\s*\(.*\))?\*?\s*$")


def parse_ch14_sources(text: str) -> list[dict]:
    """Chapter 14 constituent profiles: 'CAS number' + the 'Sources > x %' list (natural -> range) — the inverse index of the
    oil profiles, used to cross-check constituents.csv against the same book."""
    k = text.find("\nConstituent profiles\nCHAPTER CONTENTS")
    lines = text[k:].split("\n") if k > 0 else []
    rows, name, cas, in_src = [], "", "", False
    for i, ln in enumerate(lines):
        s = ln.strip()
        if CH14_HEAD.match(s):
            for j in range(i - 1, max(i - 4, -1), -1):
                h = lines[j].strip()
                if h and not PAGE.match(h) and not CH14_HEAD.match(h) and not h.startswith("Notes"):
                    if h != name:
                        name, cas, in_src = h, "", False
                    break
            continue
        m = re.match(r"^CAS number:\s*([\d\-]+)", s)
        if m:
            cas = m.group(1); continue
        if re.match(r"^Sources\s*>", s):
            in_src = True; continue
        if in_src:
            if not s or PAGE.match(s):
                continue
            m = CH14_SRC.match(s)
            if m and name:
                lo, hi = m.group(2), m.group(3)
                hi = hi if hi else lo
                try:
                    lo_f = 0.0 if lo == "tr" else float(lo.replace("<", "").strip()); hi_f = float(hi.replace("<", "").strip())
                except ValueError:
                    continue
                rows.append({"Constituent": name, "Constituent_CAS": cas, "Natural": m.group(1).strip(), "Min_Pct": lo_f, "Max_Pct": hi_f,
                             "Source": f"Tisserand & Young, Essential Oil Safety 2e (2014), Ch 14 profile '{name}', PDF p.{page_at(lines, i)}"})
            else:
                in_src = False
    return rows


def cross_check_ch14(rows: list[dict], ch14: list[dict]) -> list[dict]:
    """constituents.csv rows vs the Chapter 14 'Sources' lists: same book, two places — a disagreement is a parse error to look at."""
    idx: dict[tuple[str, str], float] = {}
    for r in ch14:
        key = (r["Constituent_CAS"], re.sub(r"[^a-z]", "", r["Natural"].casefold()))
        idx[key] = max(idx.get(key, 0.0), float(r["Max_Pct"]))
    out = []
    for r in rows:
        title = re.search(r"profile '(.+?)'", r["Source"])
        if not title:
            continue
        key = (r["Constituent_CAS"], re.sub(r"[^a-z]", "", title.group(1).casefold()))
        if key in idx:
            ours, theirs = float(r["Fraction_Used"]) * 100, idx[key]
            out.append({"Natural": r["Natural_Name"], "Constituent": r["Constituent_Name"], "Profile_Max_Pct": ours, "Ch14_Max_Pct": theirs,
                        "Agrees": abs(ours - theirs) <= max(0.5, 0.05 * theirs) or ours >= theirs})
    return out


def main(argv: list[str]) -> int:
    text = extract_text()
    profiles = parse_profiles(text)
    n_con = sum(len(p["constituents"]) for p in profiles)
    print(f"{len(profiles)} profiles parsed, {sum(1 for p in profiles if p['constituents'])} with constituents, {n_con} constituent lines")
    PROFILES_JSON.parent.mkdir(exist_ok=True)
    json.dump(profiles, open(PROFILES_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    out, unmapped, no_profile = build_rows(profiles)
    if no_profile:
        print("mapping names a profile the parser did not find:", no_profile)
    if unmapped:
        print("regulated-looking constituent names with no CAS mapping (review CANON):", dict(sorted(unmapped.items(), key=lambda kv: -kv[1])))
    if "--dry-run" in argv:
        print(len(out), "rows would be written")
        return 0
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(out)
    print(f"{len(out)} rows for {len({r['Natural_CAS'] for r in out})} natural CAS -> {OUT_CSV.name}")
    print(collections.Counter(r["Constituent_Name"] for r in out).most_common(12))
    # second-source tables from the same book
    maxima = parse_dermal_maxima(text, profiles)
    title_cas: dict[str, list[str]] = {}
    title_entries: dict[str, list[dict]] = {}
    for m in M:                                                   # the same profile -> dataset2 CAS map (and grade word) the constituents use
        title_cas.setdefault(m["title"], [])
        if m["cas"] not in title_cas[m["title"]]:
            title_cas[m["title"]].append(m["cas"])
        title_entries.setdefault(m["title"], []).append(m)
    for r in maxima:
        r["Dataset2_CAS"] = "|".join(title_cas.get(r["Profile"], []))
        ents = title_entries.get(r["Profile"], [])
        by_form = [e for e in ents if e.get("form") and e["form"] == r["Form"]]     # lavender: 'absolute' rows vs 'oil' rows
        grades = sorted({e["grade"] for e in (by_form or ents) if e["grade"]})
        r["Grade_Word"] = grades[0] if len(grades) == 1 else ""
    with open(MAXIMA_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["Profile", "Dataset2_CAS", "Grade_Word", "Form", "Basis_Constituent", "EU_Pct", "IFRA_Pct", "TY_Pct", "Single_Pct", "Qualifier", "Source"])
        w.writeheader(); w.writerows(maxima)
    print(f"{len(maxima)} dermal-maximum statements -> {MAXIMA_CSV.name}")
    ch14 = parse_ch14_sources(text)
    with open(CH14_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["Constituent", "Constituent_CAS", "Natural", "Min_Pct", "Max_Pct", "Source"])
        w.writeheader(); w.writerows(ch14)
    print(f"{len(ch14)} Chapter-14 source lines -> {CH14_CSV.name}")
    chk = cross_check_ch14(out, ch14)
    bad = [c for c in chk if not c["Agrees"]]
    print(f"Ch 13 vs Ch 14 cross-check: {len(chk)} comparable rows, {len(bad)} where the profile upper bound is BELOW the Ch 14 figure:")
    for c in bad[:40]:
        print(f"   {c['Natural'][:34]:34s} {c['Constituent']:22s} profile {c['Profile_Max_Pct']:6.2f}  ch14 {c['Ch14_Max_Pct']:6.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
