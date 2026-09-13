# Data provenance

All files in this folder are either **generated** by `build_datasets.py` from a named source, or
**hand-maintained** with every row citing its legal/olfactory basis. Regenerate with:

```
python data/build_datasets.py
python load_data.py          # validation report; exit 2 while ERROR-level defects remain
```

| File | Kind | Source | Notes |
|---|---|---|---|
| `reference/ifra_51st_standards_overview.csv` | reference copy | IFRA, *51st Amendment — IFRA Standards overview* (notified 30 Jun 2023), CSV export | 263 Standards. IFRA's own disclaimer: the individual Standards prevail over this table. |
| `ifra_limits.csv` | generated | `reference/…overview.csv`, material selection in `build_datasets.IFRA_MATERIALS` | Category 4 (fine fragrance) limits, 76 materials. Numbers are looked up by `IFRA_Key`; the build asserts every CAS maps to its key and that `Phototoxic` agrees with the official "intrinsic property" column. `All_CAS` carries every CAS the Standard covers. `Prohibition_Scope` (grade / category / as_such / all) says what the Prohibition part of a combined type applies to (`build_datasets.PROHIBITION_SCOPE`). |
| `group_rules.csv` | generated | same | Furocoumarin sum-of-fractions (8 oils only), isomer sums, MHC+MOC, oakmoss+treemoss, PAH pyrolysis group. |
| `regulatory_uk.csv` | hand-maintained | UK Cosmetics Regulation (retained Reg (EC) 1223/2009 Annex II/III as amended in GB); EU Reg 1223/2009 for Northern Ireland | Target market UK. `Jurisdiction` GB+EU / GB / EU. 2026-09-12: Annex III entries 72/73/97/102 and Annex II entries 18/360/414–450 verified against legislation.gov.uk; GB Lilial dates verified (placing 2022-10-15, off-shelf 2022-12-15). Entries citing only "Annex II (retained …)" without a number are post-2009 additions not yet re-read from the legal text. `Confidence` < high → verify before shipping. |
| `safety_caps.csv` | hand-maintained | project olfactory judgement | `Provisional=Yes` rows were lowered on 2026-09-11 from typical constituent levels and must be recomputed from supplier CoAs. |
| `reaction_rules.csv` | hand-maintained | IFRA Standards notes (ifra / ifra_spec rows); olfactory judgement (olfactory rows) | |
| `dataset1_perfumes.csv` | generated | `../Farhan-Project-main/perfume_system_master_with_recipes.xlsx :: perfumes` | 450 perfumes. `Mood_Vibe`, `Occasion` have no source and are empty. Rows P000291–P000300 are column-shifted in the source; `load_data` repairs them. |
| `dataset2_notes.csv` | generated | `../Farhan-Project-main/notes_dataset_normalized.xlsx :: notes_raw` | 720 rows / 437 unique names. **Known defects:** 72 exact duplicate rows; 50 name groups with conflicting CAS or volatility; 50 CAS numbers fail the CAS checksum (e.g. Norlimbanol listed as 66355-00-4, real CAS 70788-30-6). |
| `dataset3_accords.csv` | generated | `../Farhan-Project-main/accord_dataset_normalized_v2.xlsx :: accord_raw` | 1518 rows / 236 accords. **Known defect:** 102 note names (245 rows) have no match in dataset2. |

## Changes made in the 2026-09-11 audit (vs the original PDFs in `Downloads/ifra rules/`)

`ifra_limits.csv`
- Lilial 0.06 → **1.4** (official Cat 4; 0.06 was the Cat 5A value) — and BANNED via `regulatory_uk.csv`
- Raspberry ketone 0.27 → **1** (0.27 was the Cat 3/5C value)
- **Ambrettolide removed** — no IFRA Standard exists (value had been copied from Exaltolide)
- Tagetes type → `Prohibition_Restriction_Specification`
- 23 materials added: MHC, MOC, Costus, Cade, Birch tar, Styrax, Musk ambrette, Musk ketone, Jasmine ×2, Ylang,
  Opoponax, Verbena absolute, Melissa, Tea leaf, Hexyl salicylate, Acetylated vetiver, Methyl eugenol, Estragole,
  Safranal, Safrole, HICC, Dihydrocoumarin
- Notes completed (oakmoss/treemoss specs, isomer sums, own-phototoxicity materials marked "NOT part of furocoumarin sum")

`safety_caps.csv`
- **Costus Oil removed** (IFRA-prohibited; UK/EU-banned)
- Styrax Resinoid 3 → 0.6 (IFRA Cat 4 0.64)
- Cinnamon Oil 2 → Cinnamon Leaf Oil 2 + Cinnamon Bark Oil 0.3 (cinnamic aldehyde 0.25 %)
- Nutmeg Oil 3 → 0.3 (safrole 0.01 %, methyl eugenol 0.011 %) — provisional
- Saffron 3 → 0.1 (safranal 0.012 %) — provisional
- Cade Oil / Birch Tar: rectified-grade requirement added
- CAS added where known; six naturals still lack a CAS

`reaction_rules.csv`
- `Rule_Type` and `Limit_Basis` added; MHC/MOC and oakmoss/treemoss rules now point at real limits

## Still open
- `constituents.csv` (natural → constituent → typical %) from the IFRA *Annex on contributions from other sources*
- `Grade` field on notes (crude vs rectified; oil vs absolute) so combined IFRA types can be resolved
- Fix the 50 bad CAS numbers and the 102 unmatched accord notes in the source workbooks
- Sources for `Mood_Vibe` and `Occasion`
