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
| `note_name_aliases.csv` | hand-maintained (auto-seeded) | `reconcile_notes.py` | 2026-09-15. dataset3 → dataset2 note-name reconciliation. Tiers: AUTO (exact after normalisation, or chemical identity confirmed by dataset2's own Chemical_Name/CAS) → `Apply=Yes`; REVIEW / NO_MATCH → `Apply=No` until a human decides (`Decided_By=human` rows survive re-runs). 35/44/25 today. |
| `cas_corrections.csv` | hand-maintained (auto-seeded) | `verify_cas.py` (+ `reference/pubchem_cas_cache.json`) | 2026-09-15. FIX only when two independent sources agree (official IFRA table / project tables / PubChem / same-note / check-digit / sibling). 6 FIX, 44 FLAG. PubChem is queried only for synthetics and defined molecules. |
| `accord_name_aliases.csv` | hand-maintained (auto-seeded) | `reconcile_accords.py` | 2026-09-18. dataset1 `Main_Accords` term → dataset3 accord. 36 AUTO / 29 REVIEW / 31 NO_MATCH. |
| `constituents.csv` | **generated** by `data/mine_tisserand.py` from the Tisserand & Young 2e PDF | Tisserand & Young, *Essential Oil Safety* 2e (2014), "Key constituents" of 122 mapped profiles, every row cites the PDF page | 2026-09-19. 256 rows, 87 natural CAS; highest published upper bound across a profile's variants (isomers of one CAS summed); only constituents the safety tables know are written; ALL Provisional=Yes until supplier CoA values replace them. The 86 recalled rows of 2026-09-18 are gone. |
| `note_additions.csv` | hand-maintained (AI 2026-09-18) | CAS cited per row (PubChem for geosmin) | 7 new dataset2 rows the accords need. |
| `accord_edits.csv` | hand-maintained (AI 2026-09-18, perfumer sign-off required) | IFRA_STD_071/078/114/119, UK Annex II | Costus / Peru balsam / crude tars replaced by legal materials of the same olfactive role. |
| `product_bases.csv` | hand-maintained | RSC Fig 9.1 p.160; SCCS/1636/21 (BHT); UK/EU Annex VI entry 4 (benzophenone-3); perfumery_chat_transcript.pdf | bottle auxiliaries with legal basis. |
| `allergens_uk.csv` | hand-maintained | UK Cosmetics Regulation Annex III entries 67–92 (retained Reg 1223/2009) | 26 allergens; EU 2023/1545 expansion not yet encoded. |
| `reference/pubchem_properties.csv` | generated | `enrich_pubchem.py` (PubChem PUG REST) | MW / XLogP / IUPAC for 137 defined molecules; 53 disagree with dataset2 → reported, not overwritten. |
| `product_types.csv` | hand-maintained | Pybus & Sell, *The Chemistry of Fragrances* (RSC 1999), Appendix Table A2 p.260 | dilution ranges → `CONCENTRATE_FRACTION` presets |
| `reference/carles_*.csv` | hand-maintained | Jean Carles, *A Method of Creation in Perfumery* (Downloads/ifra rules/A-Method-of-Creation-Perfumery.pdf), pages cited per row | volatility table p.3; worked chypre pp.5–7; family signatures p.17; chypre compatibility pp.16–17; 35 student base accords pp.18–20. Columns re-extracted in pypdf layout mode 2026-09-16 (the plain extraction interleaves table columns). |
| `reference/rsc_physical_properties.csv` | hand-maintained | RSC Table 11.1 p.190 | 9 reference materials (RMM, BP, VP, sp, logP) |
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

## Changes made 2026-09-15/16 (data cleanup + book review)

- `ifra_limits.csv`: **Fig leaf absolute** (IFRA_STD_142, prohibited, phototoxic), 6-/7-methylcoumarin (prohibited),
  7-methoxycoumarin (as-such prohibition, natural contribution ≤ 0.01 %), 2-hexenal (restriction) added → 81 materials.
  Gap exposed by RSC Ch 10; numbers taken from the official table as always.
- `dataset2_notes.csv`: 6 CAS corrected (`Source_CAS` keeps the original); `load_data` now WARNs on 25 checksum-valid CAS
  shared by unrelated notes, on Volatility_Class contradicting BP/tenacity (17), and on disagreement with Carles' table (11).
- `dataset3_accords.csv`: 98 rows renamed to dataset2 names (`Source_Note_Name`/`Source_Note_ID` keep the originals).
- NOT applied, deliberately: the 1999 RSC IFRA numbers (superseded) and IFRA "quenching" (withdrawn).

## Changes made 2026-09-18 (Tasks 3–7)

- `ifra_limits.csv`: `Prohibited_Grades` / `Allowed_Grades` columns (from `build_datasets.GRADE_RULES`) for the six
  grade-scoped Standards (Peru balsam, Tagetes, cade, birch tar, styrax, verbena).
- `reaction_rules.csv`: `Equivalence_B` / `Sum_Limit_Pct` on the vanillin + ethyl vanillin row (3, 4 %; RSC Ch 7 p.141).
- `cas_corrections.csv`: two human-decided rows — Cade Oil and Juniper Tar 8000-27-9 (cedarwood) → 8013-10-3 (IFRA_STD_119).
- `load_data`: leading-zero CAS stripped for joining (14 rows, e.g. anisaldehyde 0123-11-5 → 123-11-5).

## Changes made 2026-09-18 (evening): step 0, data decisions, product layer

- Safety step 0 implemented on `constituents.csv`; the optimizer fills an all-pinned remainder with dipropylene glycol.
- All 50 checksum-failing CAS resolved: 8 FIX, 36 blanked (`Action=BLANK`); shared-CAS paste errors fixed or blanked
  (Bitter Orange Oil → 68916-04-1, Opoponax → 8021-36-1, Green Tea → 84650-60-2, Pink Pepper → 68917-52-2, Fixolide → 1506-02-1 …).
- Accords re-authored (`accord_edits.csv`), 7 notes added, aliases decided → 444/450 perfumes PASS Zone B.

## Changes made 2026-09-19: two more books mined, numbers page-cited

- `constituents.csv` regenerated from **Tisserand & Young 2e** by `data/mine_tisserand.py` (text cache and parsed profiles are
  gitignored — copyright; the tool re-extracts them from the PDF with pypdf). 400 profiles parsed, 122 mapped to dataset2
  CAS (hand-maintained map `M` in the tool, grade words for bark/leaf, expressed/distilled/FCF, oil/absolute, otto/absolute,
  linalool/estragole chemotypes, rectified/unrectified, Virginian/Texan). Consequences worth knowing: vetiver oil lists
  isoeugenol 0–1.3 % (p.1740) → with the UK 0.02 % isoeugenol limit vetiver is capped at ~1.5 % until a CoA says otherwise;
  saffron's safranal 47–60 % (p.1552) reproduces the book's own 0.02 % maximum; lavender *absolute* carries coumarin 4.3 % and
  herniarin 2.3 % (p.1249-50) that the oil does not; basil linalool CT vs estragole CT differ by 40× in estragole.
  Deliberately NOT rolled up: atranol / chloroatranol in treemoss (p.1704) — the legal control is the IFRA CoA specification
  (`group_rules.csv`), not a percentage; combined GC peaks ("safrole + p-cymen-8-ol") are booked whole to the regulated member.
- `safety_engine` step 0: a constituent that is BANNED as an ingredient (benzyl cyanide in tuberose / orange flower absolute,
  T&Y p.1706 / p.1416) now raises `CONSTITUENT_BANNED_AS_SUCH` (WARNING, CoA check) instead of a silent INFO.
- `optimizer`: pinned notes round *down* to 3 dp so a ceiling such as 0.01 / 0.023 = 0.4348 % never rounds up and re-triggers a
  cut — the one accord that used to REJECT on instability now PASSes (236/236).
- **Poucher's Perfumes, Cosmetics and Soaps** (Butler ed., 9th/10th edn): `product_types.csv` gained a `Cross_Check` column
  (eau de cologne 2–4 %, eau de toilette up to 10 %, after-shave ~1 %, PDF p.362) and the row *After-shave lotion (Poucher
  Formula VI)* (1–2 % fragrance, ethanol 50–65 %, PDF p.373); `product_bases.csv` gained propylene glycol (4–6 % after-shave
  humectant, p.373), menthol (0.10 % cooling, Formula VII p.374) and diisopropyl adipate (emollient ester, 1.10 % Formula
  VIII p.374), plus Poucher corroboration on the UV-absorber, DPG-diluent and chill-filter rows (Ch 24 p.732; p.373).
  `formulate_product` adds the humectant automatically for after-shave product types and cites the Poucher procedure.
  The rest of Poucher is cosmetics (antiperspirants, hair, soap, emulsions) — outside this system's scope.

## Still open
- `constituents.csv`: supplier CoA values to replace the literature upper bounds (Provisional=Yes); the IFRA *Annex on
  contributions from other sources* would be the official cross-check
- `Grade` field on notes (crude vs rectified; oil vs absolute) so combined IFRA types can be resolved
- 44 bad CAS (flagged in `cas_corrections.csv`) and 69 unmatched accord notes (`note_name_aliases.csv` REVIEW/NO_MATCH) await human decisions; 25 shared-CAS hazards need verified CAS (Cade Oil first)
- Sources for `Mood_Vibe` and `Occasion`
