# CLAUDE.md — AI Perfume Formulation System

This file is the primary guidance for Claude Code. Read it fully before writing any code.

> Revision 2026-09-11: data audited against the official IFRA 51st Amendment (see
> `data/DATA_PROVENANCE.md` and `../../Downloads/ifra rules/IFRA_RULES_REVIEW.md`).
> Changes vs the original spec are marked **[rev]**.
> Revision 2026-09-16: data-blocker cleanup (name reconciliation, CAS audit) + Task 2 built; Carles' text and
> Pybus & Sell *The Chemistry of Fragrances* (RSC 1999) read and folded in as cited reference tables — marked **[rev2]**.
> Revision 2026-09-18: Tasks 3–7 built (safety engine, optimizer, accord bridge, Zone A, app). **[rev3]**
> Revision 2026-09-19: Tisserand & Young 2e mined into `constituents.csv` (page-cited, tool `data/mine_tisserand.py`); Poucher's
> after-shave / product-base figures added; optimizer rounds pinned notes down. **[rev5]**
> Revision 2026-09-19 (later): Curtis & Williams *An Introduction to Perfumery* (OCR'd scan) and Ohloff *Scent and Chemistry* 2e
> mined — floral bases, type formulas, stability table, olfactory families, usage levels; `stability.py`, `book_accords.py`;
> 27 Curtis aroma chemicals added to dataset2; Lyral given its HICC CAS (it could not be rejected before). **[rev6]**

## ⏩ RESUME HERE (read this first in a new session)

**State on 2026-09-19 (late):** everything requested is built and tested — `python -m pytest -q` → 216 passing (~2-7 min, the
all-accord and all-perfume sweeps dominate).
`python app.py "fresh woody for summer"` runs match → formula → safety → rebalance → **product formulation**
(ethanol / water / additives / allergen label); `python app.py --invent "citrus, mossy, rose" --family Chypre` **invents**
a new composition the Carles way; `streamlit run app.py` is the UI (Buttons / Free text / Invent). All on `main`.

Numbers that describe the data state (`python load_data.py`): 1 ERROR (13 accord note names with no dataset2
equivalent — Cannabis/Hemp/Egg/Mushroom accords etc., an honest floor), 0 checksum-failing CAS (fixed or blanked),
3 legitimately shared CAS, 2582/2593 perfume-accord slots resolve, **450/450 catalogue perfumes PASS Zone B** (415 fully
complete; 35 are built without one accord note that has no dataset2 material — `require_complete=False`, as the app runs it;
the six REJECTs of 2026-09-18 were optimizer rounding instability, now fixed), **236/236 accords PASS**. Safety step 0
(constituent roll-up) runs on `constituents.csv` — **256 rows, 87 naturals, every fraction a page-cited Tisserand & Young 2e
upper bound** (`python data/mine_tisserand.py` regenerates it from the PDF) — and every verdict stays **PROVISIONAL** until
those fractions are replaced by supplier CoA values. Two consequences a perfumer must know: vetiver oil is capped near
1.5 % (isoeugenol 0–1.3 %, T&Y p.1740, vs the UK 0.02 % limit) and basil / tarragon / estragole-type materials near
0.02 % (IFRA estragole 0.014 %) — both are exactly what the books say; a CoA showing less lifts them.

What was decided by AI, not a human (all traceable, `Decided_By=ai` in the CSV, sign-off needed before shipping):
- `accord_edits.csv`: Costus → Carrot Seed (earthy accords) / Skatole trace (animalic accords); Birch Tar → Birch Tar
  Rectified; Cade Oil → Cade Oil Rectified (new note); Styrax Resin → Styrax Resinoid; Peru Balsam → Tolu Balsam.
- `note_additions.csv`: 7 new dataset2 rows (Vanilla Absolute, Cinnamon Bark Oil, Cade Oil Rectified, Geosmin, Davana,
  Mace, Lentisque). `note_name_aliases.csv` 91/104 applied; `accord_name_aliases.csv` 88/96 applied.
- `cas_corrections.csv`: 90 rows — 6 auto + 2 human + AI single-source fixes; 36 hopeless CAS **blanked** (missing beats wrong).
- `note_additions.csv`: +27 aroma chemicals the Curtis floral bases need (alpha-terpineol, amyl/hexyl cinnamal, methyl benzoate,
  methyl salicylate, aurantiol, benzyl/methyl isoeugenol, p-cresyl esters …) — CAS verified on PubChem (CID in the row), layer =
  Curtis' T/M/B, potency class coarse. `cas_corrections.csv`: Lyral (NOTE-0685) had no CAS at all → 31906-04-4 from
  regulatory_uk / IFRA_STD_044, so the ban now fires. `note_field_overrides.csv`: Patchouli / Patchouli Oil Strong → Medium
  (Ohloff p.627: ca. 20 % in Angel).
- `constituents.csv`: no longer AI-recalled — generated from the T&Y 2e text by `data/mine_tisserand.py`; what IS a decision
  there is the hand-maintained map dataset2 CAS → profile / grade word (`M` in the tool) and the choice to use the highest
  upper bound across a profile's variants (Bulgarian vs Turkish rose, six Boswellia species…). Treemoss atranol is deliberately
  not rolled up (IFRA CoA spec governs); Turkish rose absolute uses the Provence (R. centifolia) absolute profile as the closest
  published one — flagged in the row's Note.

What is still open, in order:
1. **Supplier CoA values** for constituents.csv (turns PROVISIONAL into real), and a perfumer's smell-test of the
   AI substitutions above. 2. dataset2 chemistry columns: 53 MW/logP disagreements with PubChem
   (`data.pubchem_mismatches`) — replace from `reference/pubchem_properties.csv` when a human confirms the identities.
3. The 13 accord notes with no material (author them or drop the accords). 4. EU allergen list expansion
   (Reg 2023/1545) in `allergens_uk.csv`. 5. Zone C (stock solutions, pumps) — only after 1.
6. ML: `../Farhan-Project-main/preprocessing/build_real_reviews.py` builds a REAL customer-language corpus (Amazon
   Reviews 2023, research licence) weak-labelled by catalogue perfume mentions; `training/evaluate_on_real_reviews.py`
   measures the real-world gap of the trained checkpoint; retraining with those rows (plan F.5) is the next ML step.

How to check where things stand: `python load_data.py`, `python app.py --report`, the three reconcile/verify scripts
(`data/reconcile_notes.py`, `data/verify_cas.py --offline`, `data/reconcile_accords.py`), `data/enrich_pubchem.py --offline`,
`python data/mine_tisserand.py --dry-run` (re-parses the book and reports unmapped constituent names), `python data/mine_ohloff.py`,
`python data/mine_curtis.py` (rewrite the Ohloff / Curtis reference tables from the transcriptions inside the scripts).

Books read and where they landed (all page-cited in the CSVs; see `data/DATA_PROVENANCE.md`): Carles → `reference/carles_*.csv`
+ builder rules; IFRA 51st → `ifra_limits` / `group_rules`; RSC *Chemistry of Fragrances* → layer physics, Fig 9.1 product base,
Table A2 product types, vanillin rule; **Tisserand & Young 2e** → `constituents.csv`; **Poucher 9/10e** → after-shave product
type + auxiliaries (`product_types.csv` Cross_Check column, `product_bases.csv`); **Curtis & Williams 1994** → `reference/curtis_*.csv`
(7 floral bases with parts and Curtis' T/M/B, 5 type formulas + the Exp. 11.22 cologne, 36 stability statements) →
`zone_b_chemistry/stability.py` (colour / hydrolysis / haze advisories in every product) and `book_accords.py` (book accords for
invention, Curtis sketches as families); **Ohloff/Pickenhagen/Kraft 2e** → `reference/ohloff_*.csv` (nine olfactory families with
155 materials, 12 basic accords, rose trials + Eternity scheme with parts, 20 landmark-perfume dosages that now cross-check the
potency classes in `load_data`). The perfumery chat transcript → DPG as diluent.

**Water, colour and smell (the user's question, answered by the books and now by the engine):** water itself is inert; what it
does is (1) hydrolyse esters back to alcohol + acid — vinegar / butyric off-notes, autocatalytic (Curtis p.525-526), so the
product layer flags `ESTER_HYDROLYSIS` above 10 % water; (2) drop the alcohol strength — below 75 % terpene-rich citrus oils
come out of solution as haze (Curtis p.561) → `TERPENE_SOLUBILITY`; (3) it must be distilled / deionised — salts and iron
discolour eugenol, vanillin, clove, cassia (Curtis p.195, 230, 263, 270) → `IRON_SENSITIVE`. Colour change is mostly NOT the
water: it is light and air on citral, musk ketone, indole, vanillin (p.183, 206, 219, 230, 554) → `LIGHT_SENSITIVE` /
`OXIDATION_PRONE`, and Schiff-base browning when an amine (indole, anthranilates, orange-flower / jasmin absolutes) meets an
aldehyde (p.146, 183, 213, 554) → `SCHIFF_BASE_COLOUR`. The bottle therefore carries BHT + benzophenone-3 by default, uses
purified water, keeps water ≤ 12 % for EdP/EdT, and every product printout lists these advisories with their pages.

## PROJECT OVERVIEW

An AI-powered fragrance system that takes a user's preferences (buttons or text), matches them to a
perfume, and — on approval — generates a chemically balanced, IFRA-compliant, **UK-market-legal**
formula for a physical mixing machine.

**Project type:** AI application with a deterministic chemistry engine + LLM front-end + (future)
hardware actuation.

## ⚠️ THE TWO-ZONE RULE (MOST IMPORTANT)

The system is split into two zones. **This boundary must NEVER blur.**

### ZONE A — LLM-Powered (soft logic)
- Interpreting user input (text → structured values)
- Matching preferences to perfumes in the catalog
- Generating descriptions
- Failure = a slightly-off recommendation (LOW risk)

### ZONE B — Own Code, NO LLM (hard logic)
- Chemistry formula construction
- IFRA safety enforcement **and UK/EU regulatory enforcement [rev]**
- Usage caps + reaction flagging
- Failure = unsafe or illegal product on skin (HIGH risk)
- **LLMs are FORBIDDEN in this zone.**

### ZONE C — Physical Hardware (future)
Formula % → stock solutions → pump volumes → mixing

| Aspect | Zone A (LLM) | Zone B (Own Code) |
|---|---|---|
| Determinism required | No | **Yes** |
| Safety-critical | No | **Yes** |
| Correct tool | LLM | **Hardcoded rules + CSV lookups** |

## SYSTEM FLOW

```
USER INPUT (buttons OR text)
    ↓
[ZONE A] LLM: interpret + match against catalog → recommend perfume
    ↓
[ZONE A] Display: notes + accords + description
    ↓
  USER APPROVES?
    ↓ YES
[ZONE B] Structural formula builder (top/heart/base)
    ↓
[ZONE B] Apply accord weights → proportions
    ↓
[ZONE B] SAFETY: constituent roll-up → regulatory bans → IFRA (single + group rules) → usage caps → reactions
    ↓
[ZONE B] Optimization pass → normalize to 100% with capped materials PINNED → re-run SAFETY until stable
    ↓
OUTPUT: safe formula (+ flags + traceability log)
    ↓
[ZONE C] (future) physical mixing
```

## TECH STACK

- **Language:** Python 3.12
- **Data:** pandas (CSV/Excel)
- **LLM:** Claude API or OpenAI (Zone A ONLY)
- **Chemistry engine:** pure Python (Zone B)
- **Interface:** Streamlit (early)
- **Tests:** pytest
- **Version control:** Git

## PROJECT STRUCTURE

```
perfume-ai-system/
├── data/
│   ├── dataset1_perfumes.csv        # catalog (450 perfumes)
│   ├── dataset2_notes.csv           # notes + chemistry, CAS is the join key (720 notes)
│   ├── dataset3_accords.csv         # accord composition + weights (1518 rows)
│   ├── ifra_limits.csv              # IFRA 51st Amd Category 4 limits (81 materials)  [rev][rev2]
│   ├── group_rules.csv              # IFRA combination rules (furocoumarins, isomer sums…) [rev]
│   ├── regulatory_uk.csv            # UK/EU cosmetics bans + restrictions (REJECT layer)  [rev]
│   ├── safety_caps.csv              # olfactory usage caps
│   ├── reaction_rules.csv           # pairwise incompatibilities
│   ├── product_types.csv            # fine-fragrance dilution ranges (RSC Table A2) -> CONCENTRATE_FRACTION presets [rev2]
│   ├── note_name_aliases.csv        # dataset3 -> dataset2 note-name reconciliation (Rule 10); Apply/Decided_By  [rev2]
│   ├── cas_corrections.csv          # checksum-failing CAS -> verified corrections; Apply/Decided_By            [rev2]
│   ├── accord_name_aliases.csv      # dataset1 Main_Accords term -> dataset3 accord (the Zone A -> B bridge)     [rev3]
│   ├── constituents.csv             # natural -> restricted constituent -> fraction (safety step 0); GENERATED by mine_tisserand.py [rev5]
│   ├── note_additions.csv           # new dataset2 rows the accords need (Vanilla Absolute, Cade Oil Rectified…)   [rev4]
│   ├── accord_edits.csv             # substitutions for banned / wrong-grade notes inside accords (AI, sign-off)    [rev4]
│   ├── note_field_overrides.csv     # coarse relabels, e.g. Odor_Strength potency class (Very strong/Strong/Low), AI  [rev4]
│   ├── product_bases.csv            # bottle auxiliaries: ethanol, water, DPG, BHT, UV absorber… with legal basis  [rev4]
│   ├── allergens_uk.csv             # the 26 declarable allergens (UK/EU), leave-on threshold 0.001 %              [rev4]
│   ├── reference/ifra_51st_standards_overview.csv   # official IFRA table (source of truth)
│   ├── reference/carles_*.csv       # Carles' volatility table, worked chypre, family signatures, 35 base accords [rev2]
│   ├── reference/rsc_physical_properties.csv        # RSC Table 11.1                                          [rev2]
│   ├── reference/pubchem_cas_cache.json             # cached PubChem answers so the CAS audit reproduces offline [rev2]
│   ├── reference/pubchem_properties.csv             # PubChem MW / XLogP / IUPAC for 137 defined molecules      [rev4]
│   ├── enrich_pubchem.py            # fetches the above; load_data WARNs on MW/logP disagreement                  [rev4]
│   ├── mine_tisserand.py            # Tisserand & Young 2e PDF -> constituents.csv (page-cited); text cache gitignored [rev5]
│   ├── mine_ohloff.py               # Ohloff 2e -> reference/ohloff_{families,accords,formulas,usage_levels,practice}.csv [rev6]
│   ├── mine_curtis.py               # Curtis 1994 -> reference/curtis_{floral_bases,formulas,stability}.csv (+ winocr.ps1 OCR) [rev6]
│   ├── build_datasets.py            # regenerates dataset1/2/3 (+ applies aliases & CAS fixes), ifra_limits, group_rules
│   ├── reconcile_notes.py           # Step 1 tool: proposes note-name aliases, tiers AUTO / REVIEW / NO_MATCH   [rev2]
│   ├── verify_cas.py                # Step 2 tool: audits bad CAS against IFRA table / project tables / PubChem [rev2]
│   ├── reconcile_accords.py         # accord-term bridge tool, same tiers                                        [rev3]
│   └── DATA_PROVENANCE.md
├── zone_a_llm/                      # Tasks 5-6 — DONE 2026-09-18 [rev3]
│   ├── llm_client.py                # the ONLY module that talks to an LLM (anthropic SDK, optional; FakeClient for tests)
│   ├── input_handler.py             # buttons / free text -> Preferences, clamped to the catalogue vocabulary
│   ├── matcher.py                   # deterministic explainable ranking; LLM may re-rank the shortlist only (grounded)
│   └── describer.py                 # template prose; LLM prose rejected if it contains numbers / safety words
├── zone_b_chemistry/
│   ├── formula_builder.py           # Task 2 — DONE 2026-09-16
│   ├── accord_study.py              # Carles' ratio-study method as a deterministic variation generator [rev2]
│   ├── safety_engine.py             # Task 3 — DONE 2026-09-18 (step 0 NOT IMPLEMENTED -> provisional)
│   ├── optimizer.py                 # Task 4 — DONE 2026-09-18 (fills an all-pinned remainder with DPG diluent)
│   ├── pipeline.py                  # run_zone_b / run_zone_b_for_perfume: build -> safety -> rebalance [rev3]
│   ├── product_formulation.py       # concentrate -> bottle (RSC Fig 9.1), safety at product %, allergen label [rev4]
│   ├── invention.py                 # new compositions from terms: family signature + Carles ratio series      [rev4]
│   ├── book_accords.py              # Curtis floral bases / Ohloff accords / Curtis sketches as builder rows      [rev6]
│   └── stability.py                 # colour / hydrolysis / haze advisories per bottle (curtis_stability.csv)  [rev6]
├── zone_c_machine/                  # future
│   ├── stock_solutions.csv
│   ├── pump_mapping.csv
│   └── machine_control.py
├── tests/
├── load_data.py
├── app.py                           # Task 7 — DONE 2026-09-18: streamlit UI + `python app.py "<text>"` CLI
├── CLAUDE.md
├── README.md
└── requirements.txt
```

## DATA SCHEMAS

**dataset1_perfumes.csv**
`Perfume_ID, Perfume_Name, Brand, Fragrance_Family, Main_Accords, Top_Notes, Middle_Notes, Base_Notes, Gender, Season, Longevity, Sillage, Description, Mood_Vibe, Occasion`
Multi-value fields are `;`-separated. `Longevity`/`Sillage` are source text (e.g. "Long lasting", "Moderate");
`load_data` adds `Longevity_Score`/`Sillage_Score` (1–5). `Mood_Vibe`/`Occasion` currently have **no source** and are empty. **[rev]**

**dataset2_notes.csv** (practical fields used by engine)
`Note_ID, Note_Name, Chemical_Name, CAS, Volatility_Class(Top/Heart/Base, may be "Top/Heart"), Odor_Strength, Accords_Used_In` + chemistry fields
(`Molecular_Weight, Boiling_Point_C, Vapor_Pressure, LogP, Odor_Threshold_mg_L, Tenacity_hrs, …`) + `Source_CAS` (the workbook value
before `cas_corrections.csv` was applied) **[rev2]**.
**`CAS` is the join key to IFRA and regulatory tables — never join on names. [rev]**
Known state **[rev2]**: 44 rows still carry a checksum-failing CAS (flagged in `cas_corrections.csv`, human must verify) and
**25 checksum-valid CAS are shared by unrelated notes** (e.g. Cade Oil carries cedarwood's 8000-27-9) — `load_data` WARNs per CAS
(`data.shared_cas`). The chemistry fields (thresholds, BP…) differ between duplicate rows of the same note and are unverified.

**dataset3_accords.csv**
`Accord_ID, Accord_Name, Accord_Category, Note_ID, Note_Name, Note_Role(Driver/Support/Modifier), Layer, Importance_Weight(1-5), Typical_Presence(0-1), Blend_Compatibility(0-1), Stability_Class`
+ `Source_Note_Name, Source_Note_ID` (workbook values before `note_name_aliases.csv` renamed them) **[rev2]**.
Known state **[rev2]**: 69 note names (167 rows) still do not resolve in dataset2 — 44 need a human decision in
`note_name_aliases.csv` (REVIEW tier), 25 need a new dataset2 row (NO_MATCH). 87 exact duplicate rows and 30 differing
duplicate (accord, note) pairs exist; the formula builder de-duplicates and flags them.

**note_name_aliases.csv / cas_corrections.csv** **[rev2]** — hand-maintained decision tables generated by
`data/reconcile_notes.py` / `data/verify_cas.py`. Only rows with `Apply=Yes` are applied by `build_datasets.py`; set
`Decided_By=human` to make a decision permanent (re-runs never overwrite human rows). Auto-application requires exact
match after normalisation (names) or two independent sources agreeing (CAS) — never a guess.

**product_types.csv** **[rev2/rev5]** — `Product_Type, Concentrate_Min_Pct, Concentrate_Max_Pct, Alcohol_Pct_Range, Source, Cross_Check`
(RSC Appendix Table A2: extrait 15–30 %, EdP 8–15, EdT 4–15, cologne 3–5, after shave 2–8, splash 2–3; Poucher's independent
figures in `Cross_Check` — cologne 2–4 %, EdT ≤ 10 %, after-shave ~1 % p.362 — and his Formula VI after-shave lotion as its own
row: 1–2 % fragrance, 50–65 % ethanol, p.373). Zone C picks one; `CONCENTRATE_FRACTION` must lie in that range.

**constituents.csv** **[rev4/rev5]** — `Natural_Name, Natural_CAS, Grade_Word, Constituent_Name, Constituent_CAS, Typical_Min_Pct,
Typical_Max_Pct, Fraction_Used, Basis, Source, Note, Provisional`. Generated by `data/mine_tisserand.py` — edit the map `M` or
`CANON` in the tool, never the numbers. `Grade_Word` (bark/leaf, expressed/distilled/FCF, absolute/oil/otto, linalool/estragole,
rectified/unrectified, virginia/texas, globulus/citriodora) picks the profile from the note name; when a CAS has several
grades every row carries a grade word (blank rows would double-count) and no grade word in the note name → worst case of every
grade. `Fraction_Used` = highest upper bound across the profile's variants, isomers of one CAS summed, capped at 1.0.

**note_additions.csv / accord_edits.csv** **[rev4]** — hand-maintained; applied by `build_datasets.py` (additions appended to
dataset2 after CAS corrections; edits applied to dataset3 after the aliases, matched on the workbook or current note name).

**product_bases.csv** **[rev4]** — `Component, INCI, CAS, Role, Default_Pct, Min_Pct, Max_Pct, Phase, When_To_Use, Legal_Basis,
Source, Note`: ethanol (DEB), water, DPG, BHT (SCCS ≤ 0.8 %), tocopherol, benzophenone-3 (Annex VI ≤ 0.5 % product protection),
PPG-20 methyl glucose ether, polysorbate 20, magnesium carbonate (filter aid); **[rev5]** propylene glycol (after-shave humectant
4–6 %, Poucher p.373 — added automatically for after-shave product types), menthol (0.1 % cooling, optional), diisopropyl adipate
(emollient ester, optional). Baseline = RSC Fig 9.1 EdP; after-shave = Poucher Formula VI.

**allergens_uk.csv** **[rev4]** — the 26 Annex III allergens with `All_CAS`; leave-on 0.001 % / rinse-off 0.01 %.

**data/reference/carles_*.csv** **[rev2]** — transcribed from Jean Carles, *A Method of Creation in Perfumery*, every row cited
by page: `carles_volatility_table` (his Top/Modifier/Base labels, cross-checked against dataset2 by `load_data`),
`carles_formulas` (his worked chypre with parts — the builder's golden test), `carles_family_signatures` (chypre / fougère /
foin / trèfle skeletons), `carles_chypre_compatibility`, `carles_student_accords` (35 real oakmoss base accords with parts).

**ifra_limits.csv** **[rev]**
`Material_Name, CAS, IFRA_Type, Category_4_Limit, Phototoxic(Yes/No), Notes, IFRA_Key, IFRA_Standard_Name, All_CAS, Amendment, Prohibition_Scope, Prohibited_Grades, Allowed_Grades`
- `Prohibited_Grades` / `Allowed_Grades` (`|`-separated words, from `build_datasets.GRADE_RULES`) resolve grade-scoped
  prohibitions: the safety engine matches them against the grade text it is given (the pipeline reads the grade from the
  formula's own note names, e.g. "Birch Tar Rectified"); no grade word → REJECT. **[rev3]**
- `IFRA_Type` ∈ {Restriction, Prohibition, Specification} or `_`-joined combinations exactly as in the official table.
- `All_CAS` is `|`-separated: match a note if **any** listed CAS matches (rose ketones cover 16 CAS).
- Generated by `data/build_datasets.py` from `data/reference/…overview.csv`; **never edit numbers by hand.**

**group_rules.csv** **[rev]**
`Group_Name, Rule_Type(ifra_sum | ifra_sum_of_fractions | ifra_spec_coa), Members_CAS(|-sep), Members_Names, Rule, Limit, Limit_Basis`

**regulatory_uk.csv** **[rev]**
`Material_Name, CAS, Jurisdiction(GB+EU | GB | EU), Status(BANNED | RESTRICTED), Fine_Fragrance_Limit_Pct, Legal_Basis, Note, Confidence`

**safety_caps.csv** **[rev]**
`Material_Name, CAS, Max_Safe_Percent, Reason, Grade_Note, Provisional(Yes/No)` — `Provisional=Yes` rows were derived from typical
constituent levels and must be recomputed from supplier CoAs.

**reaction_rules.csv** **[rev]**
`Material_A, CAS_A, Material_B, CAS_B, Rule_Type(ifra | ifra_spec | olfactory), Issue, Action, Limit_Basis, Equivalence_B, Sum_Limit_Pct`
- optional numeric pair: `A + Equivalence_B × B ≤ Sum_Limit_Pct` is applied (vanillin + 3 × ethyl vanillin ≤ 4 %, RSC Ch 7 p.141);
  rows without numbers are flagged, not applied. **[rev3]**

**accord_name_aliases.csv** **[rev3]** — `Dataset1_Term, Dataset3_Accord, Confidence, Tier, Rule, Reason, Candidates, Perfumes_Using,
Apply, Decided_By, Note`. Generated by `data/reconcile_accords.py`; only `Apply=Yes` rows are used by `pipeline.perfume_to_accords`.
36 terms auto-applied cover 1908/2593 perfume-accord slots; the k-th accord in `Main_Accords` gets weight 0.85^k.

## CHEMISTRY ENGINE RULES (Zone B — Jean Carles method)

### Structural pyramid **[rev — aligned with Carles]**

| Layer | Carles' term (a *volatility class*) | Target % | Default |
|---|---|---|---|
| Top | top notes (very volatile, no tenacity) | 15–30 % | **25 %** |
| Heart | "modifiers" (intermediate volatility) | 15–25 % — **never above 25 %** | **20 %** |
| Base | base notes (low volatility, high tenacity) | 45–65 % — always the largest share | **55 %** |

Carles (p. 23): modifiers "should not exceed 20 to 25 % of the total weight of the composition, since an
excess … would severely interfere with its lasting character"; a 20/30/50 base/modifier/top split "will lack
tenacity" (p. 7). The old spec's Heart 30–40 % contradicted this and has been removed. Place each note by
`Volatility_Class` from dataset2 **only**; a note tagged "Top/Heart" may sit in either layer.
Physical meaning of the layers **[rev2]** (Pybus & Sell Ch 7 p.141; Ch 11 p.190/200): top ≈ the first 15 min of evaporation,
heart ≈ the next 3–4 h, base ≈ the final 5–8 h; vapour pressure is the best predictor, boiling point / molecular mass the first
approximation. `load_data` WARNs when a `Volatility_Class` contradicts the note's BP/tenacity, and when it disagrees with
Carles' own table (`data.carles_disagreements`) — reported, never silently overridden.

### How `formula_builder.build_formula()` applies this **[rev2 — Task 2, implemented]**
1. **Resolve** each accord note in dataset2 by exact name (Rule 10). Not found → `UNPLACEABLE` ERROR, listed in `result.unplaced`;
   never dropped. Several dataset2 rows for one name → the checksum-valid-CAS row with the note's most common class is used and
   `NOTE_CONFLICT` says which alternatives existed.
2. **Place** by `Volatility_Class`. A two-layer tag takes the accord's own `Layer` if allowed, else the allowed layer furthest below
   its target. Accord `Layer` that contradicts dataset2 → dataset2 wins, `LAYER_OVERRIDDEN` says so.
3. **Weigh**: `Importance_Weight × Typical_Presence × accord weight`; Odor_Strength damps the share — `Very strong` ×0.25
   (trace materials: indole, skatole, aldehydes, damascones, calone…), `Strong` ×0.5, `Medium`/`Low` ×1 (`ODOR_DAMPED`;
   Carles' accessory products, RSC Ch 8 p.149). The classes come from `note_field_overrides.csv` (216 AI relabels from
   general usage-level knowledge — olfactory balance only, never a safety input) on top of the workbook's labels.
   `Blend_Compatibility < 0.7` scales by itself (`LOW_COMPATIBILITY`).
   Duplicate accord rows: exact repeats ignored, differing repeats keep the strongest statement and WARN — never summed.
4. **Layers**: 25/20/55 defaults; an empty layer's share is redistributed (`EMPTY_LAYER`), Heart is then re-capped at 25 with the
   excess to Base, Base must stay the largest; anything outside the Carles ranges → `LAYER_OUT_OF_RANGE`. Within a layer, notes
   split the layer % by adjusted weight. Total is exactly 100.000 (rounding residual on the largest component).
5. **Shape** (RSC Ch 7 p.141): an accord whose placed notes all sit in one layer → `ACCORD_SINGLE_LAYER` WARNING.
6. **Trace**: `result.trace` has one row per accord row with every factor; `result.flags` is sorted ERROR → WARNING → INFO.
Golden test: Carles' chypre (Top 4 Sweet Orange / 1 Bergamot; Modifiers 3 Rose / 1 Civet 10 %; Base 6 Oakmoss / 4 Ambergris /
1 Musk Ketone) must come out 20/5 | 15/5 | 30/20/5. `accord_study.py` generates Carles' 9:1…5:5 base series, third-material
extension, modifier/top steps and substitution variants — Zone B generates and weighs, a human or Zone A **chooses**.
Do not confuse Carles' "modifiers" (= the Heart layer, a volatility class) with dataset3's
`Note_Role = Modifier` (a weight-1 trace role inside an accord that can sit in any layer) — the role never
affects layer placement.

### Weight → proportion

| Note_Role | Weight | Relative % |
|---|---|---|
| Driver | 5 | Highest |
| Driver | 4 | High |
| Support | 3 | Medium |
| Support/Modifier | 2 | Low |
| Modifier | 1 | Trace |

### General rules
- Total must sum to 100 %
- Base notes get the largest share
- Powerful materials (low odor threshold) get SMALLER % (e.g., IsoButyl Quinoline ≈ 0.5–1 %, not 15 %) — Carles' "accessory products"
- Reduce low `Blend_Compatibility` pairs when combined
- Carles' materials lists are pre-regulation (musk ambrette is banned; oakmoss is 0.1 % max). Any accord seeded from them goes
  through the full Zone-B safety pass like everything else.

## SAFETY RULES (Zone B — NON-NEGOTIABLE)

### Documented assumption: formula = finished product **[rev]**

IFRA limits are Maximum Acceptable Concentrations **in the finished consumer product, not in the fragrance
concentrate** (Guidance §1.3). This engine applies the Category 4 limits **directly to the 100 % formula**,
i.e. it treats the dispensed liquid as the finished product, applied like a fine fragrance (pulse points,
small skin area). Category 4 = "hydroalcoholic and **non-hydroalcoholic** fine fragrance of all types"
(Guidance Table 11, p. 45), so a neat oil used as a fine fragrance is Category 4.

- **Dilution:** treating the formula as the finished product is conservative with respect to dilution —
  any later dilution only lowers the finished-product concentration.
- **Use pattern is a separate question.** Guidance §6.5.16 / Table 10 says an attar-type neat oil cannot be
  assigned one category by IFRA: fine-fragrance or EDT use → Cat 4; body-oil/lotion-like use over large
  areas → **Cat 5A** (much stricter, e.g. coumarin 0.38 % vs 1.5 %); intimate exposure → Cat 8; and "the
  most stringent outcome" when the end use is unspecified. **Assumption for v1: fine-fragrance use only**
  (small-area application); if the product could be applied like a body oil, switch the limits column to
  Category 5A.
- Zone C's design ("formula % → stock solutions → pump volumes") suggests the real product will be
  pre-diluted materials, so the finished-product concentration may be lower than the formula %. When Zone C
  fixes the stock concentrations, a single Zone-B constant `CONCENTRATE_FRACTION` (default **1.0**, meaning
  neat) may be set to the actual concentrate-in-product fraction, and effective caps become
  `limit / CONCENTRATE_FRACTION`. It must never be set above 1.0 and must never be LLM-supplied.
  Its allowed values come from `data/product_types.csv` (RSC Table A2, p.260) **[rev2]**.
- **Never add "quenching"** (citral safe with 25 % limonene, cinnamic aldehyde with eugenol, …) to `reaction_rules.csv`:
  it appears in the 1999 RSC text (Ch 10) but IFRA withdrew the concept — zero mentions in the 51st Amendment. **[rev2]**
- Category 4 includes aftershave splashes. If the product could be used as a **body spray** it becomes
  **Category 2** (stricter) unless labelled "not for use on the axillae"; if marketed as a **hair mist**, take
  the lower of Cat 4 and Cat 7B per ingredient (Guidance §6.5.6, §6.5.17). Changing category = changing the
  limits column, which `build_datasets.py` can emit from the official table.

### Order of checks (each is a deterministic CSV lookup by CAS)

0. **Constituent roll-up** **[rev — TODO, blocks v1 sign-off]** — IFRA limits apply to a substance however it
   enters the formula, directly or as a constituent of a natural (Guidance §1.4: contributions "must be considered
   in the calculations of the levels of the restricted substance"; FAQ 7.12). So the level every later step
   judges is `effective_%(CAS) = direct_% + Σ(natural_% × constituent_fraction)`: clove → eugenol, cinnamon bark →
   cinnamic aldehyde, nutmeg → safrole + methyl eugenol, saffron → safranal, rose → methyl eugenol, basil/tarragon →
   estragole. Needs `constituents.csv` (natural CAS → constituent CAS → typical %) from the IFRA *Annex on
   contributions from other sources* (not yet obtained) or supplier CoAs. Until it exists the `Provisional=Yes`
   caps in `safety_caps.csv` stand in for it.
1. **Regulatory REJECT layer (`regulatory_uk.csv`)** **[rev]** — target market is the **UK**. Great Britain runs
   the retained UK Cosmetics Regulation (Annex II bans / Annex III restrictions); Northern Ireland follows the EU
   regulation. `BANNED` in **either** GB or EU → REJECT. `RESTRICTED` → the effective cap is
   **`min(UK/EU limit, IFRA Category 4 limit)`** — neither list ever raises the other's ceiling. Where the two
   systems disagree today:
   - **Lilial** — IFRA 1.4 %, UK/EU banned → REJECT
   - **HICC / Lyral** — IFRA 0.2 %, UK/EU banned → REJECT
   - **Dihydrocoumarin** — IFRA 0.21 %, UK/EU banned → REJECT
   - **Hydroxycitronellal** — IFRA 2.1 %, UK/EU 1.0 % → cap 1.0
   - **Isoeugenol** — IFRA 0.11 %, UK/EU 0.02 % → cap 0.02
   - **Methyl eugenol** — IFRA 0.011 %, UK/EU 0.01 % → cap 0.01
   - **Musk ketone** — IFRA spec only, UK/EU 1.4 % → cap 1.4
   - Musk ambrette, Costus, Verbena oil, Peru balsam crude, Tagetes erecta — banned in both systems.
   - **Safrole** — prohibited *as such* in both systems (direct addition → REJECT); only its **natural-content**
     contribution is tolerated, ≤ 0.01 % (100 ppm) in the finished product, enforced through step 0.
2. **IFRA verdict by type (`ifra_limits.csv`)**
   - `RESTRICTION` → cap at `Category_4_Limit`
   - `PROHIBITION` (no Cat 4 value) → REJECT material
   - `SPECIFICATION` → FLAG (purity / peroxide / PAH requirement — a supplier-CoA check, not a %-check)
   - Combined types carry a `Prohibition_Scope` column that says what the prohibition applies to: **[rev]**
     - `grade` — a grade or species is banned, another is restricted (crude Peru balsam; crude cade / birch tar /
       styrax gum; *Tagetes erecta*; verbena *oil* vs absolute). **If the grade is unknown → REJECT.**
     - `category` — banned only in other IFRA categories (p-BMHCA in Cat 1 & 6) → the Cat 4 cap applies.
     - `as_such` — banned when added as an ingredient; natural-contribution ceiling applies (safrole) → direct use
       REJECT, contribution capped via step 0.
     - `all` — pure prohibition.
3. **IFRA group rules (`group_rules.csv`)** **[rev]**
   - **Furocoumarin rule — applies ONLY to the 8 furocoumarin-containing oils** (angelica root, bergamot expressed,
     bitter orange expressed, cumin, grapefruit expressed, lemon cold-pressed, lime expressed, rue), Guidance
     §1.6.1.2 / Table 3 / IFRA_STD_089:
     ```
     total = sum( used_% / cat4_limit for each member of group "furocoumarin_ncs" )
     if total > 1.0: FLAG("furocoumarin combination exceeds 100%") and scale members down
     ```
     The five Table 2 materials — AHMI, Methyl N-methylanthranilate, Methyl β-naphthyl ketone, Tagetes, Methyl
     2-(formylamino)benzoate — are phototoxic **in their own right** and are capped individually; they are **not**
     in the sum. Alternative test when bergapten (5-MOP) is analytically known (Guidance §7.13, IFRA_STD_089):
     total 5-MOP ≤ 15 ppm (0.0015 %) in the finished product, counting minor contributors such as petitgrain
     mandarin (~50 ppm), tangerine cold-pressed (~50 ppm) and parsley leaf oil (~20 ppm), which are otherwise
     unrestricted.
   - Isomer sums: rose ketones, methyl ionones, cedrene, citral — sum of all member CAS ≤ group limit
   - MHC + MOC ≤ MHC limit (and MOC ≤ its own limit); oakmoss + treemoss ≤ 0.1 %
   - PAH pyrolysis-oil group (cade, birch tar, styrax, opoponax) → rectified grades only; FLAG for CoA
4. **Usage caps (`safety_caps.csv`)** → cap at `Max_Safe_Percent`; `Grade_Note` may require a rectified grade
5. **Reaction rules (`reaction_rules.csv`)** → flag / sum / reduce as stated
6. **Normalisation re-check** — Task 4 rebalances to 100 % by redistributing only across **unconstrained**
   materials; every material at a cap or limit stays pinned. After rebalancing, steps 0–5 run again; the loop ends
   only when nothing changes. A normalisation that would push any material over a ceiling is itself a REJECT.

### How `safety_engine.check_formula()` implements this **[rev3 — Task 3, implemented]**
`check_formula(formula, data, concentrate_fraction=1.0, grades=None) -> SafetyResult(verdict PASS|ADJUSTED|REJECT, formula,
rejections, adjustments, flags, pinned, log, ceilings, provisional=True)`. Per material the LOWEST of {UK/EU restriction,
IFRA Cat 4 / concentrate_fraction, safety cap} binds and the others are listed as not binding; BANNED / Prohibition /
as-such / unknown-or-prohibited grade → the whole formula is REJECT (Zone B never removes a note by itself — the caller
rebuilds without it); group rules scale members (sum, sum-of-fractions) and pin them; specifications and provisional caps
are flags; a note without CAS is UNVERIFIED (warning). `optimizer.optimize()` then redistributes the removed mass across
unpinned notes (same layer first, Heart ≤ 25), renormalises to 100 and re-runs `check_formula` until nothing changes;
if nothing unpinned can absorb the mass → REJECT. `pipeline.run_zone_b()` chains build → safety → optimize.

### Product layer and invention **[rev4]**
`product_formulation.formulate_product(concentrate, data, product_type, concentrate_pct)` turns the 100 % concentrate into a
bottle: alcohol share of the solvent from `product_types.csv` (RSC Table A2, upper bound), water the rest, auxiliaries from
`product_bases.csv`; re-runs `check_formula` with `concentrate_fraction = concentrate %`; emits the allergen declaration
(direct materials + constituent contributions) and the maturation / chill / filter process (RSC Fig 9.1).
`invention.invent(terms, data, family=…, book_accords="fallback")` maps terms → accords (a term dataset3 cannot cover falls back
to a Curtis floral base or an Ohloff basic accord; `"always"` adds them next to the dataset3 accord), enforces a family signature
(Carles chypre / fougère / foin / trèfle, or a Curtis sketch: `chypre (curtis)`, `fougere (curtis)`, `lavender water`, `eau de
cologne`, `floral-aldehydic` — floral bases inside a sketch reduced to their three largest materials), varies the two strongest
base materials through 9:1 … 5:5, runs every variant through safety + rebalance and ranks them — Zone A or the user chooses.
A banned material a book accord brings in (Lyral in every 1994 muguet base) is dropped by the INVENTOR, reported as
`removed_banned`, and the structure rebuilt — Zone B itself never removes a note. Known limit: the builder's 25/20/55 pyramid
inflates the few base-class materials of a floral base (phenylacetic acid at 10 % dilution can end up at several %); pair book
bases with a family sketch that supplies a real base, and read the trace of the candidate. Odour-active "fixatives" (musks, Ambroxan, resinoids) live inside the concentrate; DPG is a diluent, not a
fixative (perfumery_chat_transcript.pdf, RSC Ch 9).

### Safety principles
- All safety checks are deterministic (table lookups, never LLM)
- Every adjustment must be traceable and cite its source row ("Vanillin 6 % → 4 %: safety_caps.csv";
  "Isoeugenol 0.05 % → 0.02 %: regulatory_uk.csv Annex III"; "Lilial REJECTED: regulatory_uk.csv BANNED")
- Same input → same output, always
- **If a formula can't be made safe, REJECT it — never output unsafe formulas**
- Also emit the **allergen declaration** (v2 — labelling, not a cap; this is cosmetics law, **not** an IFRA
  rule): UK Cosmetics Regulation (retained Reg (EC) 1223/2009) Art. 19(1)(g) + Annex III — in GB the 26 listed
  fragrance allergens above 0.001 % in leave-on products must be named on the label; the EU (and therefore
  Northern Ireland) expanded the list to ~80 substances via Reg (EU) 2023/1545 (new products from 31 Jul 2026 —
  verify). Keep the list in a CSV with a `Jurisdiction` column like `regulatory_uk.csv`; never hard-code "26". **[rev]**

## LLM RULES (Zone A only)
- LLM is used ONLY for: input interpretation, perfume matching, description generation
- LLM must NEVER determine quantities, safety limits, IFRA values, regulatory status, or reactions
- Matching prompt MUST include the catalog and instruct: "Only recommend from this list" (prevents inventing perfumes)
- Free text → LLM converts to button-equivalent values → hands to matching logic
- If the API is down, the button path must still work (graceful degradation)

## CODING CONVENTIONS
- Zone A and Zone B code live in **separate modules**. Never import LLM calls into `zone_b_chemistry/`.
- Chemistry functions must be **pure** (same input → same output, no side effects)
- All data loaded via pandas from `/data` through `load_data.py` — never hardcode data in logic files
- Safety caps, IFRA limits, group rules and regulatory bans live in **CSV files**, not code (so they're updatable)
- `ifra_limits.csv` and `group_rules.csv` are **generated** from the official IFRA table by `data/build_datasets.py`;
  change the material list in that script, never the CSV numbers
- Join every safety lookup **by CAS** (any CAS in `All_CAS`), never by name
- Log every safety adjustment for traceability
- Write tests that deliberately breach limits and confirm the engine flags them

## 11 NON-NEGOTIABLE RULES
1. LLM never touches chemistry, safety, IFRA, regulatory status, or quantities
2. All safety checks are deterministic
3. Formulas must sum to 100 %
4. IFRA limits are hard ceilings (regulatory)
5. **UK/EU cosmetics bans override IFRA — a banned material is rejected even if IFRA allows it** **[rev]**
6. If a formula can't be made safe, reject it
7. Every safety decision must be traceable to a source row
8. Same input → same output, always
9. Button path must work without the LLM/API
10. Note names must match exactly across Dataset 2 & 3; safety lookups join on CAS
11. Never let the LLM invent perfumes — always ground it in the catalog

## BUILD TASK SEQUENCE (do ONE at a time, test, then next)

- **Task 1 — DONE (2026-09-12)** — Project skeleton + `load_data.py` (read/clean/validate all data CSVs into DataFrames;
  cross-checks between tables; `python load_data.py` prints a data report and exits non-zero on errors).
- **Data cleanup — DONE (2026-09-15/16)** **[rev2]** — Step 1 note-name reconciliation (35 aliases auto-applied, 44 REVIEW,
  25 NO_MATCH), Step 2 CAS audit (6 fixed with two sources, 44 flagged, 25 shared-CAS hazards reported), Step 3 baseline
  (fig leaf absolute + 3 coumarins + 2-hexenal added to `ifra_limits`, physics/shared-CAS/Carles checks in `load_data`,
  Carles & RSC reference tables, `product_types.csv`).
- **Task 2 — DONE (2026-09-16)** — `zone_b_chemistry/formula_builder.py` + `accord_study.py`; tests in
  `tests/test_formula_builder.py` (golden Carles chypre, unplaceable-note, conflict, empty-layer, shape, determinism cases).
- **Task 3 — DONE (2026-09-18)** — `zone_b_chemistry/safety_engine.py`; 36 deliberate-breach tests. Step 0 runs on the T&Y-derived
  `constituents.csv` since 2026-09-19 (`CONSTITUENT_BANNED_AS_SUCH` warns when a banned-as-ingredient molecule arrives as natural content).
- **Task 4 — DONE (2026-09-18)** — `zone_b_chemistry/optimizer.py` + `pipeline.py`.
- **Accord bridge — DONE (2026-09-18)** — `data/reconcile_accords.py` → `accord_name_aliases.csv`; `pipeline.perfume_to_accords`.
- **Task 5 — DONE (2026-09-18)** — `zone_a_llm/input_handler.py` + `matcher.py` (+ `llm_client.py`); button path needs no API.
- **Task 6 — DONE (2026-09-18)** — `zone_a_llm/describer.py`.
- **Task 7 — DONE (2026-09-18)** — `app.py` (Streamlit UI + terminal CLI).

After each task: show the result and wait for confirmation before proceeding.

## CURRENT STATUS

See **⏩ RESUME HERE** at the top: everything is built and tested (216 tests); the data blockers of September are closed
(constituents from Tisserand & Young, accords re-authored, decision CSVs worked, PubChem check run). What remains needs a
human or a supplier: CoA values for `constituents.csv`, sign-off of the `Decided_By=ai` rows, the 13 material-less accord
notes, the 53 PubChem MW/logP disagreements, the EU allergen list, Zone C, and the ML retrain (`../Farhan-Project-main/
training/NEXT_STEPS_ML.md`). `python load_data.py` exits non-zero on that one ERROR (13 notes) by design.
