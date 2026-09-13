"""Regenerate the catalogue + IFRA data files in this folder from their sources.

Run from anywhere:  python data/build_datasets.py

Sources (all local, see DATA_PROVENANCE.md):
  dataset1_perfumes.csv  <- ../Farhan-Project-main/perfume_system_master_with_recipes.xlsx :: perfumes
  dataset2_notes.csv     <- ../Farhan-Project-main/notes_dataset_normalized.xlsx           :: notes_raw
  dataset3_accords.csv   <- ../Farhan-Project-main/accord_dataset_normalized_v2.xlsx       :: accord_raw
  ifra_limits.csv        <- reference/ifra_51st_standards_overview.csv (official IFRA table)
                            + the material selection in IFRA_MATERIALS below

Everything numeric in ifra_limits.csv is looked up from the official table by
Standard key; nothing is typed by hand. Deterministic: same inputs -> same files.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ML_PROJECT = HERE.parents[1] / "Farhan-Project-main"
OFFICIAL = HERE / "reference" / "ifra_51st_standards_overview.csv"

# ----------------------------------------------------------------------------
# dataset1 — perfumes (CLAUDE.md schema; Mood_Vibe / Occasion have no source yet)
# ----------------------------------------------------------------------------

def _lines(cell) -> str:
    """Fragrantica-style multi-line cells -> '; '-joined list."""
    if pd.isna(cell):
        return ""
    parts = [p.strip() for p in str(cell).replace("\r", "\n").split("\n")]
    return "; ".join(p for p in parts if p)


def build_perfumes() -> pd.DataFrame:
    src = pd.read_excel(ML_PROJECT / "perfume_system_master_with_recipes.xlsx", sheet_name="perfumes")
    out = pd.DataFrame({
        "Perfume_ID": src["perfume_id"],
        "Perfume_Name": src["perfume_name"].astype(str).str.strip(),
        "Brand": src["brand"].astype(str).str.strip(),
        "Fragrance_Family": src["fragrance_family"].astype(str).str.strip(),
        "Main_Accords": src["main_accords_raw"].map(_lines),
        "Top_Notes": src["top_notes_raw"].map(_lines),
        "Middle_Notes": src["middle_notes_raw"].map(_lines),
        "Base_Notes": src["base_notes_raw"].map(_lines),
        "Gender": src["gender"].astype(str).str.strip(),
        "Season": src["season_raw"].map(_lines),
        "Longevity": src["longevity"].astype(str).str.strip(),   # text in source; loader maps to 1-5
        "Sillage": src["sillage"].astype(str).str.strip(),       # text in source; loader maps to 1-5
        "Description": src["description"].fillna("").astype(str).str.strip(),
        "Mood_Vibe": "",                                          # no source column yet
        "Occasion": "",                                           # no source column yet
    })
    return out


# ----------------------------------------------------------------------------
# dataset2 — notes (CLAUDE.md practical fields + chemistry fields; CAS is the join key)
# ----------------------------------------------------------------------------

def build_notes() -> pd.DataFrame:
    src = pd.read_excel(ML_PROJECT / "notes_dataset_normalized.xlsx", sheet_name="notes_raw")
    out = pd.DataFrame({
        "Note_ID": src["note_id"],
        "Note_Name": src["Note Name"].astype(str).str.strip(),
        "Chemical_Name": src["Chemical Name"],
        "CAS": src["cas_number_clean"].fillna(src["CAS Number"]),
        "Volatility_Class": src["Volatility Class"],
        "Odor_Strength": src["Odor Strength"],
        "Accords_Used_In": src["Accords Used In"],
        "Chemical_Family": src["Chemical Family"],
        "Odor_Family": src["Odor Family"],
        "Key_Nuances": src["Key Nuances"],
        "Molecular_Weight": src["Molecular Weight"],
        "Boiling_Point_C": src["Boiling Point (°C)"],
        "Vapor_Pressure": src["Vapor Pressure"],
        "LogP": src["LogP"],
        "Odor_Threshold_mg_L": src["Odor Threshold (mg/L)"],
        "Tenacity_hrs": src["Tenacity (hrs)"],
        "Substantivity_Index": src["Substantivity Index"],
        "Flash_Point_C": src["Flash Point (°C)"],
        "Solubility": src["Solubility"],
        "Natural_Source": src["Natural Source"],
        "Short_Description": src["Short Description"],
    })
    return out


# ----------------------------------------------------------------------------
# dataset3 — accords (exact CLAUDE.md columns)
# ----------------------------------------------------------------------------

def build_accords() -> pd.DataFrame:
    src = pd.read_excel(ML_PROJECT / "accord_dataset_normalized_v2.xlsx", sheet_name="accord_raw")
    out = pd.DataFrame({
        "Accord_ID": src["accord_id"],
        "Accord_Name": src["Accord Name"].astype(str).str.strip(),
        "Accord_Category": src["Accord Category"].astype(str).str.strip(),
        "Note_ID": src["note_id"],
        "Note_Name": src["Note Name"].astype(str).str.strip(),
        "Note_Role": src["Note Role"].astype(str).str.strip(),
        "Layer": src["Layer"].astype(str).str.strip(),
        "Importance_Weight": src["Importance Weight"],
        "Typical_Presence": src["Typical Presence"],
        "Blend_Compatibility": src["Blend Compatibility"],
        "Stability_Class": src["Stability Class"].astype(str).str.strip(),
    })
    return out


# ----------------------------------------------------------------------------
# ifra_limits — from the official 51st Amendment overview, by Standard key
# ----------------------------------------------------------------------------

# (Material_Name as used in this project, primary CAS, IFRA_STD key, Phototoxic, Notes)
IFRA_MATERIALS = [
    ("Coumarin", "91-64-5", "IFRA_STD_023", "No", ""),
    ("Citronellol", "106-22-9", "IFRA_STD_022", "No", ""),
    ("Geraniol", "106-24-1", "IFRA_STD_037", "No", ""),
    ("Eugenol", "97-53-0", "IFRA_STD_035", "No", "Sum contributions from clove, cinnamon leaf, bay, pimento oils"),
    ("Citral", "5392-40-5", "IFRA_STD_021", "No", "Geranial + neral summed; sum contributions from lemongrass, litsea, lemon oils"),
    ("Isoeugenol", "97-54-1", "IFRA_STD_048", "No", "UK/EU Annex III cap 0.02 is stricter - see regulatory_uk.csv"),
    ("Benzyl Salicylate", "118-58-1", "IFRA_STD_011", "No", ""),
    ("Benzyl Benzoate", "120-51-4", "IFRA_STD_009", "No", ""),
    ("Benzyl Alcohol", "100-51-6", "IFRA_STD_008", "No", ""),
    ("Benzyl Cinnamate", "103-41-3", "IFRA_STD_010", "No", ""),
    ("Cinnamic aldehyde", "104-55-2", "IFRA_STD_018", "No", "Powerful - small dose; sum contributions from cinnamon bark/cassia oils"),
    ("Cinnamic alcohol", "104-54-1", "IFRA_STD_017", "No", ""),
    ("Hydroxycitronellal", "107-75-5", "IFRA_STD_043", "No", "UK/EU Annex III cap 1.0 is stricter - see regulatory_uk.csv"),
    ("Cashmeran", "33704-61-9", "IFRA_STD_028", "No", "DPMI"),
    ("Iso E Super", "54464-57-2", "IFRA_STD_068", "No", "OTNE"),
    ("Exaltolide", "106-02-5", "IFRA_STD_026", "No", "Cyclopentadecanolide"),
    ("Norlimbanol", "70788-30-6", "IFRA_STD_221", "No", "Timberol"),
    ("Farnesol", "4602-84-0", "IFRA_STD_036", "No", "Spec: >=96% farnesol isomers by GLC"),
    ("Oakmoss Absolute", "90028-68-5", "IFRA_STD_067", "No",
     "Spec: atranol & chloroatranol each <100 ppm; DHA <=0.1%; no added treemoss. Oakmoss+treemoss combined <= limit. UK/EU: atranol/chloroatranol banned as substances"),
    ("Treemoss", "90028-67-4", "IFRA_STD_080", "No",
     "Spec: DHA <=0.8%; atranol & chloroatranol each <100 ppm. Oakmoss+treemoss combined <= limit"),
    ("Rose ketones", "23696-85-7", "IFRA_STD_077", "No", "All 16 rose-ketone isomers (damascones/damascenones) summed; very powerful"),
    ("Methyl ionone", "1335-46-2", "IFRA_STD_063", "No", "Isomers summed; spec: pseudo-methyl-ionones <=2% impurity"),
    ("Alpha-Hexyl cinnamic aldehyde", "101-86-0", "IFRA_STD_040", "No", ""),
    ("Alpha-Amyl cinnamic aldehyde", "122-40-7", "IFRA_STD_005", "No", ""),
    ("Alpha-Amyl cinnamic alcohol", "101-85-9", "IFRA_STD_004", "No", ""),
    ("Anisyl alcohol", "105-13-5", "IFRA_STD_006", "No", ""),
    ("Benzaldehyde", "100-52-7", "IFRA_STD_007", "No", ""),
    ("Carvone", "99-49-0", "IFRA_STD_016", "No", ""),
    ("Cyclamen aldehyde", "103-95-7", "IFRA_STD_025", "No", "Spec: <=1.5% cyclamen alcohol"),
    ("Lilial", "80-54-6", "IFRA_STD_015", "No",
     "IFRA: prohibited in Cat 1 & 6 only. BANNED outright in UK/EU cosmetics -> regulatory_uk.csv REJECTS it"),
    ("Peru balsam", "8007-00-9", "IFRA_STD_071", "No", "Crude PROHIBITED (also UK/EU Annex II); extracts/distillates only"),
    ("Linalool", "78-70-6", "IFRA_STD_187", "No", "Spec: peroxide value <20 mmol/L (antioxidant e.g. 0.1% BHT)"),
    ("Limonene", "138-86-3", "IFRA_STD_186", "No", "Spec: peroxide value <20 mmol/L (antioxidant e.g. 0.1% BHT)"),
    ("Farnesal", "19317-11-4", "IFRA_STD_202", "No", ""),
    ("Citronellal", "106-23-0", "IFRA_STD_206", "No", ""),
    ("Cedrene", "11028-42-5", "IFRA_STD_197", "No", "Isomers summed"),
    ("Longifolene", "475-20-7", "IFRA_STD_199", "No", ""),
    ("Sandalore", "65113-99-7", "IFRA_STD_212", "No", ""),
    ("Polysantol", "107898-54-4", "IFRA_STD_211", "No", ""),
    ("Raspberry ketone", "5471-51-2", "IFRA_STD_217", "No", "Depigmentation"),
    ("Bergamot oil expressed", "8007-75-8", "IFRA_STD_087", "Yes", "Furocoumarin"),
    ("Lemon oil cold pressed", "8008-56-8", "IFRA_STD_092", "Yes", "Furocoumarin"),
    ("Lime oil expressed", "8008-26-2", "IFRA_STD_093", "Yes", "Furocoumarin"),
    ("Grapefruit oil expressed", "8016-20-4", "IFRA_STD_091", "Yes", "Furocoumarin"),
    ("Bitter orange peel oil", "68916-04-1", "IFRA_STD_088", "Yes", "Furocoumarin"),
    ("Angelica root oil", "8015-64-3", "IFRA_STD_086", "Yes", "Furocoumarin"),
    ("Cumin oil", "8014-13-9", "IFRA_STD_090", "Yes", "Furocoumarin"),
    ("Rue oil", "8014-29-7", "IFRA_STD_096", "Yes", "Furocoumarin"),
    ("Methyl N-methylanthranilate", "85-91-6", "IFRA_STD_094", "Yes",
     "Phototoxic (own) - NOT part of furocoumarin sum; nitrosamine potential -> notify downstream"),
    ("Acetyl hexamethyl indan", "15323-35-0", "IFRA_STD_085", "Yes", "AHMI; phototoxic (own) - NOT part of furocoumarin sum"),
    ("Methyl beta-naphthyl ketone", "93-08-3", "IFRA_STD_095", "Yes", "Phototoxic (own) - NOT part of furocoumarin sum"),
    ("Tagetes oil", "91722-29-1", "IFRA_STD_097", "Yes",
     "T. erecta PROHIBITED (also UK/EU Annex II); T. patula/minuta only, alpha-terthienyl <=0.35%; phototoxic (own) - NOT part of furocoumarin sum"),
    # --- added after the 2026-09-11 audit: referenced by other tables / Carles ---
    ("Methyl heptine carbonate", "111-12-6", "IFRA_STD_062", "No", "MHC+MOC combined <= MHC limit (reaction_rules.csv)"),
    ("Methyl octine carbonate", "111-80-8", "IFRA_STD_064", "No", "Also MHC+MOC combined <= MHC limit"),
    ("Costus root oil", "8023-88-9", "IFRA_STD_124", "No", "PROHIBITED (also UK/EU Annex II)"),
    ("Cade oil", "8013-10-3", "IFRA_STD_119", "No",
     "Crude PROHIBITED; rectified only, PAH markers (benzopyrene + 1,2-benzanthracene) <=1 ppb in final product, summed with rectified birch tar/styrax/opoponax"),
    ("Birch tar", "8001-88-5", "IFRA_STD_114", "No", "Crude PROHIBITED; rectified only, same PAH <=1 ppb rule as cade oil"),
    ("Styrax", "8046-19-3", "IFRA_STD_078", "No",
     "Crude gum PROHIBITED; resinoid/absolute/oil restricted; pyrolysis oil must be rectified, PAH <=1 ppb"),
    ("Musk ambrette", "83-66-9", "IFRA_STD_168", "No", "PROHIBITED (also UK/EU Annex II); appears throughout Carles' accords"),
    ("Musk ketone", "81-14-1", "IFRA_STD_189", "No", "Spec: musk xylene impurity <0.1%. UK/EU Annex III cap 1.4 in fine fragrance"),
    ("Jasmine absolute (grandiflorum)", "8022-96-6", "IFRA_STD_049", "No", ""),
    ("Jasmine absolute (sambac)", "91770-14-8", "IFRA_STD_050", "No", ""),
    ("Ylang ylang extracts", "8006-81-3", "IFRA_STD_084", "No", ""),
    ("Opoponax", "8021-36-1", "IFRA_STD_070", "No", "Rectified oil: PAH <=1 ppb rule"),
    ("Verbena absolute", "85116-63-8", "IFRA_STD_083", "Yes",
     "Verbena OIL prohibited for sensitization + phototoxicity (also UK/EU Annex II); only the absolute is allowed. "
     "Phototoxicity handled by the oil prohibition - NOT part of furocoumarin sum (not in Guidance Table 2 or 3)"),
    ("Melissa oil", "8014-71-9", "IFRA_STD_051", "No", ""),
    ("Tea leaf absolute", "84650-60-2", "IFRA_STD_079", "No", ""),
    ("Hexyl salicylate", "6259-76-3", "IFRA_STD_042", "No", ""),
    ("Acetylated vetiver oil", "84082-84-8", "IFRA_STD_002", "No", ""),
    ("Methyl eugenol", "93-15-2", "IFRA_STD_100", "No",
     "Natural constituent of rose, basil, bay, pimento, nutmeg oils -> sum contributions. UK/EU Annex III cap 0.01"),
    ("Estragole", "140-67-0", "IFRA_STD_099", "No", "Natural constituent of basil, tarragon, fennel, anise oils -> sum contributions"),
    ("Safranal", "116-26-7", "IFRA_STD_082", "No", "Major volatile of saffron extracts"),
    ("Safrole", "94-59-7", "IFRA_STD_179", "No",
     "As such PROHIBITED; natural contribution (nutmeg, sassafras, camphor oils) <=0.01% total in finished product (also UK/EU Annex II: <=100 ppm)"),
    ("HICC (Lyral)", "31906-04-4", "IFRA_STD_044", "No",
     "IFRA restricts (HMPCC) but BANNED in UK/EU since 2021 -> regulatory_uk.csv REJECTS it"),
    ("Dihydrocoumarin", "119-84-6", "IFRA_STD_029", "No", "IFRA restricts but BANNED in UK/EU Annex II -> regulatory_uk.csv REJECTS it"),
    ("Methyl 2-(formylamino)benzoate", "41270-80-8", "IFRA_STD_101", "Yes",
     "Phototoxic (own, Guidance Table 2) - NOT part of furocoumarin sum"),
]

# 'See Notebox' Standards whose numeric limit lives in the notes text
NOTEBOX_LIMITS = {"IFRA_STD_179": "0.01"}   # safrole natural contribution, % in finished product

# What the 'Prohibition' part of a combined IFRA type applies to (CLAUDE.md step 2):
#   grade    - one grade/species banned, another restricted (unknown grade -> REJECT)
#   category - banned only in other IFRA categories (Cat 4 cap applies)
#   as_such  - banned as an added ingredient; natural-contribution ceiling applies
#   all      - pure prohibition
PROHIBITION_SCOPE = {
    "IFRA_STD_015": "category",   # p-BMHCA (Lilial): prohibited in Cat 1 & 6
    "IFRA_STD_071": "grade",      # Peru balsam: crude banned, extracts restricted
    "IFRA_STD_097": "grade",      # Tagetes: T. erecta banned, T. patula/minuta restricted
    "IFRA_STD_119": "grade",      # Cade oil: crude banned, rectified with spec
    "IFRA_STD_114": "grade",      # Birch tar: crude banned, rectified with spec
    "IFRA_STD_078": "grade",      # Styrax: crude gum banned, extracts restricted
    "IFRA_STD_083": "grade",      # Verbena: oil banned, absolute restricted
    "IFRA_STD_179": "as_such",    # Safrole: banned as such, natural contribution <= 0.01%
}


def build_ifra_limits() -> pd.DataFrame:
    off = pd.read_csv(OFFICIAL, skiprows=2).set_index("Key")
    cas2key: dict[str, str] = {}
    for key, r in off.iterrows():
        for cas in re.findall(r"\d{2,7}-\d{2}-\d", str(r["CAS numbers"])):
            cas2key.setdefault(cas, key)

    rows = []
    for name, cas, key, photo, note in IFRA_MATERIALS:
        assert key in off.index, f"{name}: {key} not in official table"
        assert cas2key.get(cas) == key, f"{name}: CAS {cas} maps to {cas2key.get(cas)}, not {key}"
        raw = str(off.loc[key, "Category 4 (%)"]).strip().replace(",", ".")
        if key in NOTEBOX_LIMITS:
            limit = NOTEBOX_LIMITS[key]
        elif raw in ("nan", "") or not re.fullmatch(r"[0-9.]+", raw):
            limit = ""
        else:
            limit = raw
        std_type = "_".join(p.capitalize() for p in off.loc[key, "IFRA Standard type"].split("_"))
        all_cas = "|".join(re.findall(r"\d{2,7}-\d{2}-\d", str(off.loc[key, "CAS numbers"])))
        parts = std_type.split("_")
        if "Prohibition" not in parts:
            scope = ""
        elif parts == ["Prohibition"]:
            scope = "all"
        else:
            scope = PROHIBITION_SCOPE[key]        # KeyError = a new combined type needs a decision
        # Phototoxic flag must agree with the official 'Intrinsic property' column
        intrinsic = str(off.loc[key, "Intrinsic property driving the risk management measure"]).upper()
        assert (photo == "Yes") == ("PHOTOTOXICITY" in intrinsic), f"{name}: Phototoxic flag vs {intrinsic!r}"
        rows.append({
            "Material_Name": name, "CAS": cas, "IFRA_Type": std_type, "Category_4_Limit": limit,
            "Phototoxic": photo, "Notes": note, "IFRA_Key": key,
            "IFRA_Standard_Name": off.loc[key, "Name of the IFRA Standard"],
            "All_CAS": all_cas, "Amendment": int(off.loc[key, "Amendment number"]),
            "Prohibition_Scope": scope,
        })
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------
# group_rules — combination rules whose member lists come from the official table
# ----------------------------------------------------------------------------

# Guidance §1.6.1.2 / IFRA_STD_089: the sum-of-fractions rule applies ONLY to
# the furocoumarin-containing NCS below — not to AHMI, Methyl N-methylanthranilate,
# Methyl beta-naphthyl ketone or Tagetes, which are phototoxic in their own right.
FUROCOUMARIN_KEYS = ["IFRA_STD_086", "IFRA_STD_087", "IFRA_STD_088", "IFRA_STD_090",
                     "IFRA_STD_091", "IFRA_STD_092", "IFRA_STD_093", "IFRA_STD_096"]


def build_group_rules() -> pd.DataFrame:
    off = pd.read_csv(OFFICIAL, skiprows=2).set_index("Key")

    def cas_of(*keys):
        return "|".join(c for k in keys for c in re.findall(r"\d{2,7}-\d{2}-\d", str(off.loc[k, "CAS numbers"])))

    def names_of(*keys):
        return "|".join(off.loc[k, "Name of the IFRA Standard"] for k in keys)

    def cat4(key):
        return str(off.loc[key, "Category 4 (%)"]).strip().replace(",", ".")

    rows = [
        {"Group_Name": "furocoumarin_ncs", "Rule_Type": "ifra_sum_of_fractions",
         "Members_CAS": cas_of(*FUROCOUMARIN_KEYS), "Members_Names": names_of(*FUROCOUMARIN_KEYS),
         "Rule": "sum(used_pct_i / cat4_limit_i) over members must be <= Limit. "
                 "Alternative if 5-MOP (bergapten) is analytically known (Guidance s7.13, IFRA_STD_089): total 5-MOP "
                 "<= 0.0015% (15 ppm) in finished product, counting minor contributors petitgrain mandarin (~50 ppm), "
                 "tangerine cold-pressed (~50 ppm) and parsley leaf oil (~20 ppm).",
         "Limit": "1.0", "Limit_Basis": "IFRA Guidance 51st Amd s1.6.1.2 + Table 3 (sum rule); s7.13 + IFRA_STD_089 (15 ppm 5-MOP)"},
        {"Group_Name": "rose_ketone_isomers", "Rule_Type": "ifra_sum",
         "Members_CAS": cas_of("IFRA_STD_077"), "Members_Names": names_of("IFRA_STD_077"),
         "Rule": "sum(used_pct) over all rose-ketone isomers <= Limit", "Limit": cat4("IFRA_STD_077"),
         "Limit_Basis": "IFRA_STD_077 (Cat 4)"},
        {"Group_Name": "methyl_ionone_isomers", "Rule_Type": "ifra_sum",
         "Members_CAS": cas_of("IFRA_STD_063"), "Members_Names": names_of("IFRA_STD_063"),
         "Rule": "sum(used_pct) over all methyl ionone isomers <= Limit", "Limit": cat4("IFRA_STD_063"),
         "Limit_Basis": "IFRA_STD_063 (Cat 4)"},
        {"Group_Name": "cedrene_isomers", "Rule_Type": "ifra_sum",
         "Members_CAS": cas_of("IFRA_STD_197"), "Members_Names": names_of("IFRA_STD_197"),
         "Rule": "sum(used_pct) over cedrene isomers <= Limit", "Limit": cat4("IFRA_STD_197"),
         "Limit_Basis": "IFRA_STD_197 (Cat 4)"},
        {"Group_Name": "citral_isomers", "Rule_Type": "ifra_sum",
         "Members_CAS": cas_of("IFRA_STD_021"), "Members_Names": names_of("IFRA_STD_021"),
         "Rule": "sum(used_pct) over citral/geranial/neral <= Limit", "Limit": cat4("IFRA_STD_021"),
         "Limit_Basis": "IFRA_STD_021 (Cat 4)"},
        {"Group_Name": "mhc_moc", "Rule_Type": "ifra_sum",
         "Members_CAS": cas_of("IFRA_STD_062", "IFRA_STD_064"), "Members_Names": names_of("IFRA_STD_062", "IFRA_STD_064"),
         "Rule": "sum(MHC + MOC) <= Limit (the MHC limit); MOC alone must also respect its own Cat 4 limit",
         "Limit": cat4("IFRA_STD_062"), "Limit_Basis": "IFRA_STD_062 / IFRA_STD_064 notes"},
        {"Group_Name": "oakmoss_treemoss", "Rule_Type": "ifra_sum",
         "Members_CAS": cas_of("IFRA_STD_067", "IFRA_STD_080"), "Members_Names": names_of("IFRA_STD_067", "IFRA_STD_080"),
         "Rule": "sum(oakmoss + treemoss extracts) <= Limit", "Limit": cat4("IFRA_STD_067"),
         "Limit_Basis": "IFRA_STD_067 / IFRA_STD_080 notes"},
        {"Group_Name": "pah_pyrolysis_oils", "Rule_Type": "ifra_spec_coa",
         "Members_CAS": cas_of("IFRA_STD_119", "IFRA_STD_114", "IFRA_STD_078", "IFRA_STD_070"),
         "Members_Names": names_of("IFRA_STD_119", "IFRA_STD_114", "IFRA_STD_078", "IFRA_STD_070"),
         "Rule": "Only rectified grades allowed; PAH markers (benzopyrene + 1,2-benzanthracene) from all members "
                 "combined <= 1 ppb in final product. Not computable from formula %; requires supplier CoA -> FLAG.",
         "Limit": "0.0000001", "Limit_Basis": "IFRA_STD_119 / 114 / 078 / 070 specifications"},
    ]
    return pd.DataFrame(rows)


def main() -> None:
    for fn, builder in [("dataset1_perfumes.csv", build_perfumes), ("dataset2_notes.csv", build_notes),
                        ("dataset3_accords.csv", build_accords), ("ifra_limits.csv", build_ifra_limits),
                        ("group_rules.csv", build_group_rules)]:
        df = builder()
        df.to_csv(HERE / fn, index=False, encoding="utf-8")
        print(f"{fn:<24} {len(df):>5} rows  {len(df.columns):>2} cols")


if __name__ == "__main__":
    main()
