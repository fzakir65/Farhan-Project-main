# CLAUDE.md — AI Perfume Formulation System

This file is the primary guidance for Claude Code. Read it fully before writing any code.

> Revision 2026-09-11: data audited against the official IFRA 51st Amendment (see
> `data/DATA_PROVENANCE.md` and `../../Downloads/ifra rules/IFRA_RULES_REVIEW.md`).
> Changes vs the original spec are marked **[rev]**.

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
│   ├── ifra_limits.csv              # IFRA 51st Amd Category 4 limits (75 materials)  [rev]
│   ├── group_rules.csv              # IFRA combination rules (furocoumarins, isomer sums…) [rev]
│   ├── regulatory_uk.csv            # UK/EU cosmetics bans + restrictions (REJECT layer)  [rev]
│   ├── safety_caps.csv              # olfactory usage caps
│   ├── reaction_rules.csv           # pairwise incompatibilities
│   ├── reference/ifra_51st_standards_overview.csv   # official IFRA table (source of truth)
│   ├── build_datasets.py            # regenerates dataset1/2/3, ifra_limits, group_rules
│   └── DATA_PROVENANCE.md
├── zone_a_llm/
│   ├── input_handler.py
│   ├── matcher.py
│   └── describer.py
├── zone_b_chemistry/
│   ├── formula_builder.py
│   ├── safety_engine.py
│   └── optimizer.py
├── zone_c_machine/                  # future
│   ├── stock_solutions.csv
│   ├── pump_mapping.csv
│   └── machine_control.py
├── tests/
├── load_data.py
├── app.py
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
(`Molecular_Weight, Boiling_Point_C, Vapor_Pressure, LogP, Odor_Threshold_mg_L, Tenacity_hrs, …`).
**`CAS` is the join key to IFRA and regulatory tables — never join on names. [rev]**

**dataset3_accords.csv**
`Accord_ID, Accord_Name, Accord_Category, Note_ID, Note_Name, Note_Role(Driver/Support/Modifier), Layer, Importance_Weight(1-5), Typical_Presence(0-1), Blend_Compatibility(0-1), Stability_Class`

**ifra_limits.csv** **[rev]**
`Material_Name, CAS, IFRA_Type, Category_4_Limit, Phototoxic(Yes/No), Notes, IFRA_Key, IFRA_Standard_Name, All_CAS, Amendment`
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
`Material_A, CAS_A, Material_B, CAS_B, Rule_Type(ifra | ifra_spec | olfactory), Issue, Action, Limit_Basis`

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
- **Task 2** — `zone_b_chemistry/formula_builder.py` (structural top/heart/base builder from accord weights)
- **Task 3** — `zone_b_chemistry/safety_engine.py` (constituent roll-up → regulatory REJECT → IFRA cap/reject/flag → group rules → caps → reactions)
- **Task 4** — `zone_b_chemistry/optimizer.py` (rebalance after safety cuts with capped materials pinned, normalize to 100 %, re-run safety until stable)
- **Task 5** — `zone_a_llm/matcher.py` + `input_handler.py` (input → matched perfume, grounded in catalog)
- **Task 6** — `zone_a_llm/describer.py` (generate notes/accords/description output)
- **Task 7** — `app.py` integration + Streamlit interface

After each task: show the result and wait for confirmation before proceeding.

## CURRENT STATUS

Phase 0 (architecture + data design) and **Task 1** are complete. Data in `/data` is generated and validated
(`python load_data.py`). Open data items before Task 3 can be signed off: `constituents.csv` (natural-oil
contributions), a `Grade` column on notes (crude vs rectified / oil vs absolute), sources for `Mood_Vibe` and
`Occasion` in dataset1, and CAS numbers for the six naturals in `safety_caps.csv` that have none.
**Next: Task 2.** Do not build the LLM yet.
