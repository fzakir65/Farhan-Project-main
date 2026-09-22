"""Apply the book-review decisions (sections 1-5 of reference/book_review.md), 2026-09-22.

Principle for the layer (section 1): the layer is a volatility class. Where Carles lists the material his class stands (he is the
field's teaching standard - Ohloff 2e p.607); otherwise Curtis' 'usual function' is accepted only when the physics agrees with him
(boiling point as the RSC first approximation: < ~200 C top, ~200-270 heart, > ~270 base; tenacity where dataset2 has it); when a
single author stands against practice and physics, dataset2 keeps its class.
Principle for the maxima (section 3): IFRA Cat 4 + UK Annex III remain the ceilings (the industry and legal consensus for fine
fragrance). But four oils whose toxic constituents (thujone, pinocamphone, pulegone, menthofuran) no fine-fragrance standard limits
were allowed at 100 %: they get PROVISIONAL olfactory-style caps at Tisserand & Young's figure, in the table built for exactly that.
"""
import csv, os
import pandas as pd
ROOT = r"C:\Users\onedi\OneDrive\Documents\Farhan-Project-main\perfume-ai-system"
D = os.path.join(ROOT, "data")
CUR = "Curtis & Williams, An Introduction to Perfumery (1994)"
CARLES = "Carles, A Method of Creation in Perfumery, volatility table (reference/carles_volatility_table.csv)"
DEC = "ai (book-decided 2026-09-22: Carles > Curtis+physics > dataset2)"

# ---------------------------------------------------------------- section 1: layers
CHANGE = [  # note, new class, basis
    ("Aldehyde C-9", "Heart", f"{CARLES}: modifier; {CUR} PDF p.166: middle note; BP 191 C borderline — two authorities against the workbook's Top"),
    ("Aldehyde C10", "Heart", f"{CUR} PDF p.166: not a top note (basic); Carles treats the C-9 / C-11 homologues as modifiers; BP 208 C = RSC heart window"),
    ("Aldehyde C-11", "Heart", f"{CARLES}: modifier; {CUR} PDF p.167: basic note; BP 223-238 C"),
    ("Aldehyde C12 Lauric", "Heart", f"{CUR} PDF p.168: middle note; BP 258 C (RSC Ch 11: 200-270 C evaporates in the heart window)"),
    ("Aldehyde C-12 MNA", "Heart", f"{CUR} PDF p.168: basic note; BP 254 C — physics puts it in the heart window, Curtis below it; neither is Top"),
    ("Aldehyde C-14", "Base", f"{CUR} PDF p.169: basic note; BP 286-290 C, tenacity 4-10 h (dataset2) — gamma-undecalactone is a base material"),
    ("Aldehyde C-16", "Base", f"{CUR} PDF p.169: basic note; ethyl methylphenylglycidate boils above 270 C — a Top class was a workbook error"),
    ("Benzyl Butyrate", "Heart", f"{CUR} PDF p.176: middle note; BP ~240 C"),
    ("Isoeugenyl Acetate", "Base", f"{CUR} PDF p.197: basic note; BP > 280 C"),
    ("Lyral", "Base", f"{CUR} PDF p.210: basic note; BP 280-290 C, tenacity 4-10 h (dataset2); banned in the UK/EU in any case"),
    ("Para-Methyl Acetophenone", "Heart", f"{CUR} PDF p.212: middle note; BP ~226 C"),
    ("Phenylacetaldehyde", "Top", f"BP ~195 C (RSC Ch 11 first approximation) — {CUR} PDF p.223 says middle; the workbook's Base is contradicted by both"),
    ("Alpha-Terpineol", "Heart", f"{CUR} PDF p.228: middle note; BP 219 C; the lilac heart material of every Curtis base"),
    ("Galbanum Resin", "Base", f"{CUR} PDF p.274: the resinoid is a basic note (the oil is the top note); BP 280 C, tenacity 8-12 h (dataset2)"),
]
KEEP = [  # note, kept class, basis
    ("Benzyl Salicylate", "Base", f"{CARLES}: base; BP 300 C, tenacity 12-24 h — Curtis p.178 'top' stands alone"),
    ("Citral", "Top", "industry consensus (citrus top note; Poucher, Calkin & Jellinek); VP medium, BP 228 C — Curtis p.183 'middle' stands alone"),
    ("Citronellol", "Heart", "rose alcohol, heart by consensus; BP 225 C — Curtis p.184 'top' stands alone"),
    ("Dihydromyrcenol", "Top", "BP 211-215 C, VP high, tenacity 2-3 h — Curtis p.191 'middle' stands alone"),
    ("Isobutyl Quinoline", "Base", "leather base material by consensus, BP > 270 C — Curtis p.180 'middle' stands alone"),
    ("Hydroxycitronellal", "Heart", "muguet heart material by consensus (Ohloff p.626 Diorissimo heart); BP 241 C — Curtis p.205 'basic' stands alone"),
    ("Methyl Isoeugenol", "Heart", "BP 263 C in the heart window — Curtis p.215 'basic' stands alone"),
    ("Phenethyl Alcohol", "Heart", f"{CARLES}: modifier; BP 219 C — Curtis p.225 'top' stands alone"),
    ("Tarragon Oil", "Top", f"{CARLES}: top — Curtis p.294 'basic' stands alone"),
    ("Artemisia Oil", "Top", "herbaceous top note by consensus — Curtis p.259 'middle' alone"),
    ("Basil Oil", "Top", "linalool / estragole top note by consensus — Curtis p.260 'middle' alone"),
    ("Carrot Seed", "Heart", "tenacious earthy heart by consensus — Curtis p.262 'top' alone"),
    ("Cedarwood Virginia", "Base", "woody base by every classification — Curtis p.264 'top' alone"),
    ("Citronella", "Top", "citronellal-rich top note — Curtis p.268 'middle' alone"),
    ("Guaiac Wood Oil", "Base", "woody base by consensus — Curtis p.275 'middle' alone"),
    ("Juniper Berry Oil", "Top", "terpenic top note — Curtis p.276 'middle' alone"),
    ("Lemongrass Oil", "Top", "citral-rich top note — Curtis p.279 'middle' alone"),
    ("Litsea Cubeba Oil", "Top", "citral-rich top note — Curtis p.281 'middle' alone"),
    ("Mimosa Absolute", "Heart", "floral absolute, heart by consensus — Curtis p.282 'top' alone"),
    ("Orris Butter", "Base", "irone-rich base / fixative by consensus — Curtis p.286 'top' alone"),
    ("Rosemary Oil", "Top", "cineole / camphor top note — Curtis p.290 'middle' alone"),
]
ov_path = os.path.join(D, "note_field_overrides.csv")
ov = pd.read_csv(ov_path, dtype=str, keep_default_na=False)
notes = pd.read_csv(os.path.join(D, "dataset2_notes.csv"), dtype=str, keep_default_na=False)
new_rows = []
for note, val, basis in CHANGE:
    was = "/".join(sorted(set(notes.loc[notes.Note_Name == note, "Volatility_Class"])))
    ov = ov[~((ov.Note_Name == note) & (ov.Field == "Volatility_Class"))]
    new_rows.append({"Note_Name": note, "Field": "Volatility_Class", "Value": val, "Was": was, "Basis": basis, "Decided_By": DEC})
ov = pd.concat([ov, pd.DataFrame(new_rows)], ignore_index=True)

# potency rows: add the book corroboration where Curtis / Ohloff agree
cur = pd.read_csv(os.path.join(D, "reference", "curtis_monographs.csv"), dtype=str, keep_default_na=False)
import sys
sys.path.insert(0, ROOT)
from load_data import load_all
data = load_all()
chk = data.curtis_check
agree = {r.Dataset2_Name: r for r in chk.itertuples() if r.Intensity_Agrees and r.Curtis_Intensity in ("1", "2", "5", "6")}
oh = {r.Dataset2_Name: r for r in data.ohloff_potency_check.itertuples() if r.Agrees}
n_corr = 0
for i, r in ov.iterrows():
    if r.Field != "Odor_Strength" or "consistent with" in r.Basis:
        continue
    adds = []
    if r.Note_Name in agree:
        a = agree[r.Note_Name]; adds.append(f"consistent with Curtis 1994 odour strength {a.Curtis_Intensity}/6 ({a.Source.split(', ')[-1]})")
    if r.Note_Name in oh:
        o = oh[r.Note_Name]; adds.append(f"consistent with Ohloff 2e dose ca. {o.Ohloff_Pct:g} % in {o.Perfume}")
    if adds:
        ov.at[i, "Basis"] = r.Basis + "; " + "; ".join(adds); n_corr += 1
ov.to_csv(ov_path, index=False)
print(f"overrides: {len(new_rows)} layer decisions written, {n_corr} potency rows gained book corroboration")

# ---------------------------------------------------------------- section 3: provisional caps for the unregulated toxic constituents
caps_path = os.path.join(D, "safety_caps.csv")
caps = pd.read_csv(caps_path, dtype=str, keep_default_na=False)
TY = "Tisserand & Young, Essential Oil Safety 2e (2014)"
NEW_CAPS = [
    ("Sage Oil (Dalmatian)", "8022-56-8", "0.4", f"{TY} p.1558-1559: 60 % thujone, dermal thujone limit 0.25 % (neurotoxicity) — no IFRA / Annex III limit exists, so without this cap the oil was allowed at 100 %", "Salvia officinalis (Dalmatian); Spanish sage 8016-65-7 is capped separately"),
    ("Sage Oil (Spanish)", "8016-65-7", "12.5", f"{TY} p.1564: 12.5 % dermal maximum (camphor / sabinyl acetate content)", "Salvia lavandulifolia"),
    ("Hyssop Oil", "8006-83-5", "0.3", f"{TY} p.1188-1189: 82 % pinocamphone / isopinocamphone / thujone, dermal limit 0.25 % (neurotoxicity) — no IFRA / Annex III limit", "pinocamphone CT"),
    ("Peppermint Oil", "8006-90-4", "5.4", f"{TY} p.1467: 8 % menthofuran (limit 0.5 %) and 3 % pulegone (limit 1.2 %) — hepatotoxicity; no IFRA / Annex III limit", "Mentha x piperita"),
    ("Palo Santo Oil", "959130-05-3", "3.4", f"{TY} p.1439: 11.8 % menthofuran / 1.2 % pulegone, same limits as peppermint; no IFRA / Annex III limit", "Bursera graveolens"),
]
have = set(caps.CAS)
added = 0
for name, cas, pct, reason, grade in NEW_CAPS:
    if cas in have:
        continue
    caps = pd.concat([caps, pd.DataFrame([{c: "" for c in caps.columns} | {"Material_Name": name, "CAS": cas, "Max_Safe_Percent": pct, "Reason": reason, "Grade_Note": grade, "Provisional": "Yes"}])], ignore_index=True)
    added += 1
caps.to_csv(caps_path, index=False)
print(f"safety_caps: {added} provisional caps added ({len(caps)} rows)")

# ---------------------------------------------------------------- decisions file for the review
dec_rows = [{"Section": "1 layer", "Dataset2_Name": n, "Decision": "changed", "Value": v, "Basis": b} for n, v, b in CHANGE]
dec_rows += [{"Section": "1 layer", "Dataset2_Name": n, "Decision": "kept", "Value": v, "Basis": b} for n, v, b in KEEP]
dec_rows += [{"Section": "3 T&Y maxima", "Dataset2_Name": n, "Decision": "provisional cap", "Value": p, "Basis": r} for n, c, p, r, g in NEW_CAPS]
dec_rows += [{"Section": "3 T&Y maxima", "Dataset2_Name": n, "Decision": "kept (IFRA Cat 4 / Annex III are the fine-fragrance consensus; TY_ADVISORY stays visible)", "Value": "", "Basis": b} for n, b in (
    ("Cinnamon Bark Oil", "engine 0.3 % = IFRA 51st cinnamaldehyde 0.25 % / 0.757 content; T&Y 0.07 % is their aromatherapy figure from the older IFRA 0.05 %"),
    ("Clove Bud Oil", "engine 2.0 % (olfactory cap; IFRA 51st eugenol 2.5 % Cat 4); T&Y 0.5 % is the IFRA body-lotion category figure"),
    ("Sandalwood Oil", "IFRA 51st has no sandalwood Standard; T&Y 2 % rests on 0.34 % patch-test reactions and photoallergy in one population; Ohloff p.626 records 25 % in Samsara — kept, advisory only"),
    ("Thyme Oil", "irritation-based 1.3 % (T&Y); no IFRA / Annex III limit; the engine flags TY_ADVISORY — a cap needs a perfumer's judgement on the chemotype (thymol vs linalool CT share one CAS)"),
    ("Litsea Cubeba Oil / Tea Absolute", "engine and T&Y agree within rounding (citral 0.6 % / 0.744; tea 0.21 vs 0.20)"))]
dec_rows += [{"Section": "4 Ch13 vs Ch14", "Dataset2_Name": "Benzoin Siam / Blackcurrant bud", "Decision": "kept", "Value": "", "Basis": "grade- and form-specific parse is the correct one; Ch 14 quotes the Sumatra grade and the oil"}]
dec_rows += [{"Section": "5 sign-off", "Dataset2_Name": "(all AI rows)", "Decision": "evidence attached, sign-off still human", "Value": "", "Basis": "potency overrides now cite Curtis / Ohloff where the books agree; a perfumer's smell-test remains the last step"}]
with open(os.path.join(D, "reference", "book_review_decisions.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["Section", "Dataset2_Name", "Decision", "Value", "Basis"]); w.writeheader(); w.writerows(dec_rows)
print(len(dec_rows), "decisions recorded")
