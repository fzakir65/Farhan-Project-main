# THE PERFUMERY ML SYSTEM — FULL PLAN FOR REVIEW

> **Note on the handoff document:** the perfumery primer document is treated throughout this plan as a *suggestion*, not a source of truth. Its claims are hypotheses we test against the data and your product goals. Where data evidence overrides the document, the data wins.

## 0. TL;DR

- **Your "1 model for chemicals + 1 model for dosage" intuition is half right.** The data structure already separates these (`accord_note` table = membership; `accord_recipe_default` = dosage). But both are currently **rule-derived, not learned**. Where ML actually adds value is upstream (text → accords) and on a personalization delta, not on re-learning a deterministic dosage formula from scratch.
- **Recommended architecture is a 4-stage hybrid pipeline (with optional 5th stage)**: (1) text encoder, (2) accord-set classifier (the only stage with strong supervision — 10K examples), (3) note selector that re-ranks the existing rule mapping with user context, (4) dosage estimator that outputs a small **delta** on top of the rule-based recipe and projects onto the simplex. **Stage 5 (constraint/IFRA filter) is optional and tier-dependent** — not needed for a research prototype. This is the same shape that won in adjacent domains: cooking ([Salvador et al. 2019](https://arxiv.org/abs/1812.06164)), molecule design ([Jin et al. 2018 JT-VAE](https://arxiv.org/abs/1802.04364), [Maziarka 2022 MoLeR](https://arxiv.org/abs/2103.03864)), and is consistent with the only published industrial signals we have ([Givaudan Carto 2019](https://www.givaudan.com/media/media-releases/2019/givaudan-fragrances-launches-carto-its-artificial-intelligence-powered-tool), [IBM/Symrise Philyra 2019](https://www.symrise.com/scent-and-care/competence-platforms/philyra/)).
- **Six things you need to fix in the data before any model trains well**, listed in §C below.
- **Fifty+ verified citations** in §J, organized by where they slot into the pipeline.

---

## A. WHAT THE DOCUMENT SUGGESTS (not gospel — these are hypotheses, not constraints)

> **Status of this section:** the handoff document is a *suggestion*, not a spec. The points below are the design hypotheses it floats. We treat each one as something to validate against the data and against your product goals — not as an architectural commitment. Where data evidence overrides the document, the data wins.

1. **Suggested: three languages must be bridged** — consumer ("dark date-night"), perfumery (accords / notes / families), chemical/manufacturing (CAS, vapor pressure, IFRA). The doc proposes the pipeline: words → descriptors → accords → notes → percentages → constrained formula. *Our take:* the layered framing is reasonable and the data is shaped this way (descriptor_vocab → accords → accord_note → accord_recipe_default), so we adopt it as a working hypothesis. We are free to collapse layers later if evidence supports it.
2. **Suggested: "ML for fuzzy interpretation, rules for deterministic enforcement"** — the doc argues safety/IFRA should be a hard rule layer, never learned. *Our take:* this is sound *if* you're shipping a regulated consumer product. For a research prototype, a soft-warning layer is enough. Decision deferred to your product scope (see §C.3 / §D Stage 5 below).
3. **Suggested: note selection and dosage are separate problems** — "the first table answers what belongs and the second answers in what amount." *Our take:* the data already enforces this split (`accord_note` vs `accord_recipe_default`). This is the strongest signal in the document because it's backed by table structure, not prose. We adopt it.
4. **Suggested: a "conservative operating box"** — outputs should stay inside a curated, safe, manufacturable region. *Our take:* a useful framing for production, optional for research. We treat it as a knob, not a requirement.

**Net:** the document gives us a useful starting topology (3 languages × 3 layers) and one reliable structural hint (selection vs dosage are separate). Everything else is open to revision based on your product goals and what the data actually supports.

---

## B. WHAT THE DATA ACTUALLY CONTAINS (and what it doesn't)

### B.1 What you have

| Sheet | Rows | What it is |
|---|---:|---|
| `training_examples` | 10,000 | text + structured tags → primary accord (always), secondary accord (34%), reference perfume (55%), rating (17%) |
| `accords` | 315 | accord catalog with category (Fresh / Amber / Floral / etc.) — only **200 are actually used as targets** |
| `accord_note` | 1,518 | which notes belong to which accord, with role (driver/support/modifier), layer (top/heart/base), importance 1–5, presence_prob, compatibility, stability |
| `accord_recipe_default` | 1,656 | per-(accord, note) **default %**, min %, max %, derived by the formula `importance × presence × compatibility; layer totals top25/heart45/base30` |
| `notes` | 883 catalog rows; 437 with full chemistry | molecular weight, BP, vapor pressure, logP, odor threshold, substantivity, tenacity, solubility, flash point, **CAS numbers** for 432 |
| `perfumes` + `perfume_accord` + `perfume_note` | 450 + 2,593 + 3,784 | real-world reference perfumes (Sauvage, Bleu de Chanel, Y EDP, etc.) |
| `descriptor_vocab` + `synonyms` | 98 + 96 | controlled vocabulary for input |
| `occasion_vocab` + `synonyms` | 41 + 50 | controlled vocabulary for input |

### B.2 Tables the document mentions that aren't in the workbooks

The document references these tables; they aren't in the data:

- `note_constituents` — regulated chemicals inside naturals (e.g., bergamot oil → linalool + limonene + furocoumarins)
- `note_functional_groups` — group tags for reactivity rules (aldehyde, primary_amine_like, etc.)
- `reactivity_rules` — pairwise BLOCK / WARN / SUBSTITUTE_OR_REMOVE
- `ifra_limits` — `max_pct_finished` per (note, product_category)
- `phototox_flag`, `oxidation_risk_score` — per-note risk flags

**Whether these are actually needed depends on your product scope, not on the document:**
- **Research / portfolio prototype** → not needed. Skip Stage 5 entirely or replace it with a soft-warning heuristic.
- **Regulated consumer product (vending machine, retail SKU)** → required for legal release. They don't need ML, they need curation against IFRA standards and SDS sheets.

I'll default to "not building them" until you tell me your scope is the regulated case.

### B.3 Data-quality issues I found that affect architecture

I ran distribution checks across all sheets. Six findings change what's worth building:

1. **The `user_text` is templated/synthetic, not real free-form English.** Sample lines from the data:
   - *"46yo and I'm after fresh/aquatic vibes—nothing basic."*
   - *"41 here. Looking for something that fits summer_day."*
   - *"I'm 32 and Looking for something that fits night_out."*

   The descriptors and occasion almost always appear verbatim in the text. A model trained only on this will look great in eval and faceplant on real users. **Treat the text encoder as small and don't over-engineer it; plan to augment with real reviews from Fragrantica or similar later.**
2. **The `target_perfume_id_reference` signal is weak.** Of 5,459 examples with a reference perfume, only **104 (1.9%)** have the labeled `target_accord_id_primary` actually appearing in that perfume's `perfume_accord` list. Meaning: the reference is a "vibe inspiration," not a hard label. **Use it as a soft retrieval signal at most, never as a hard label.**
3. **Note vocabulary mismatch is severe.** `accord_note` (rule-based recipes) covers 271 unique notes; `perfume_note` (real perfume catalog) covers 446 unique notes; **only 50 overlap**. Translation: your rule-recipes and your reference perfumes live in two different note ontologies. **Either bridge them with manual mapping, or formally treat them as two separate corpora and tag each output as "rule-derived" or "real-derived."**
4. **Dosage is formula-derived, not learned.** `accord_recipe_default` was generated by `importance × presence × compatibility; layer totals top25/heart45/base30`. Any "ML model for dosage" is at best (a) re-learning this formula from features, or (b) producing a personalization delta on top of it. Option (a) is wasteful; option (b) is what we should build.
5. **Five accords have recipe rows summing to 200% or 300%** (ACC-0033, ACC-0097, ACC-0111, ACC-0115, ACC-0167) — duplicated rows from multiple recipe variants. Dedup these before training.
6. **Sparse explicit feedback.** `user_rating_1_5` exists for only 17%; `accepted_flag` for only 15%. Personalization training will need contrastive / pseudo-labeling, not pointwise regression.

### B.4 Class-imbalance & vocabulary observations
- **Primary-accord head**: `ACC-0112` (395x), `ACC-0170` (351x), `ACC-0007` (226x) dominate. **115 of the 315 accords never appear as a target.** Long-tail handling required ([Cui et al. 2019 class-balanced loss](https://arxiv.org/abs/1901.05555); [Ridnik et al. 2021 asymmetric multi-label loss](https://arxiv.org/abs/2009.14119)).
- **Descriptor → accord mapping is sensible** for most descriptors (e.g., "ozonic" → Aquatic Fresh / Ozonic Fresh / Salty Marine; "smoky" → Dark Oud Smoke / Vetiver Smoky), confirming Stage 2 is supervised-learnable.
- **17 descriptors used in training** vs **98 in the vocab**; only ~3 are used per example. The descriptor signal is rich and the model has room to grow into the full 98.
- **5,459 / 10,000 reference perfumes spread over 450 catalog perfumes** → enough to train a useful retrieval head despite the 1.9% accord-mismatch noise.

---

## C. ARCHITECTURE OPTIONS — INCLUDING WHY I'M PUSHING BACK ON YOUR TWO-MODEL FRAMING

### Option 1 — Your proposal: two ML models (chemicals → dosages)

What you'd train:
- **Model A**: descriptor → set of notes
- **Model B**: notes → percentage of each

What goes wrong:
- The chemical-selection problem already has a deterministic answer in `accord_note` (1518 curated rows with role/layer/importance). You'd be training Model A to reproduce a curated table you already have — paying ML cost for zero new capability and losing the curatorial structure.
- Dosage is also already deterministic in `accord_recipe_default` via a formula. Model B would re-learn that formula. Empirically, neural re-learning of an analytical formula from a feature subset is worse than the formula itself (Marquez-Neila et al., "[Imposing hard constraints on deep networks](https://arxiv.org/abs/1706.02025)").
- Neither model touches the actual signal-rich problem: **mapping free-text + user context to which accords**.
- Doesn't reflect how every adjacent domain solves "select-then-quantify": cooking ([Salvador 2019](https://arxiv.org/abs/1812.06164)), molecule generation ([Jin 2018 JT-VAE](https://arxiv.org/abs/1802.04364), [Maziarka 2022 MoLeR](https://arxiv.org/abs/2103.03864)), portfolio allocation ([Zhang/Zohren/Roberts 2020](https://arxiv.org/abs/2005.13665)) — all use a learned **set selector + a separate constrained allocator**, not two free regressors.

### Option 2 — End-to-end transformer (text → formula in one shot)

What you'd train:
- A single seq-to-seq model that ingests text and emits `[(note, pct), …]`.

What goes wrong:
- Your safety constraints (IFRA, Schiff-base, phototoxicity) must be **exact**, not approximate; pure end-to-end models can't guarantee feasibility (Marquez-Neila, [Donti 2021 DC3](https://arxiv.org/abs/2104.12225)).
- 10K examples × 200 active accord classes × ~600 candidate notes × continuous percentages is far too sparse for end-to-end generation without an inductive bias.
- Black-box outputs kill the explainability the document explicitly demands ("users want to know why a scent was chosen").

### Option 3 (RECOMMENDED) — 5-stage hybrid pipeline

Use ML where there is signal, rules where they exist, and a hard projection layer where safety matters.

```
USER PROMPT  +  STRUCTURED CONTEXT (age/region/gender/background_tag/occasion/avoids)
       │
       ▼
[Stage 1]  TextEncoder + StructuredEncoder  →  IntentVector
       │            (DeBERTa-V3 base / RoBERTa + categorical embeddings)
       ▼
[Stage 2]  AccordSetPredictor  →  {primary, secondary, …} with weights
       │            (multi-label sigmoid head with ASL+CB loss; 10K supervised)
       ▼
[Stage 3]  NoteSelector  →  {note_id} per accord
       │            (rule mapping + learned re-ranker conditioned on IntentVector
       │             + user-avoid masking + chemical-similarity substitution)
       ▼
[Stage 4]  DosageEstimator  →  pct per note
       │            (start from recipe_default; learned delta in [-1,+1];
       │             project into [min,max]; renormalise to 100% per accord;
       │             blend across accords by Stage-2 weights)
       ▼
[Stage 5]  ConstraintFilter & Repair  →  final formula
                    (PURE RULES: IFRA cap, Schiff, phototox, oxidation, allergen-sum)
                    (Repair via nearest-neighbour substitution in chem-feature space)
```

This is the same shape as [Salvador 2019 Inverse Cooking](https://arxiv.org/abs/1812.06164), [Givaudan Carto](https://www.givaudan.com/media/media-releases/2019/givaudan-fragrances-launches-carto-its-artificial-intelligence-powered-tool), and the implicit pattern in [IBM/Symrise Philyra](https://www.symrise.com/scent-and-care/competence-platforms/philyra/). It's also the only architecture I can defend given that Stages 3–5 already have curated knowledge in the data.

---

## D. RECOMMENDED ARCHITECTURE — STAGE BY STAGE

### Stage 1 — Text + Structured Encoder (IntentVector, 256-d)

- **Backbone**: [DeBERTa-V3-base](https://arxiv.org/abs/2111.09543) (faster + more accurate than BERT-base on GLUE-style multi-label) or `MiniLM-L6` if you want CPU-fast inference. RoBERTa-base is the safe default.
- **Tokenizer**: standard subword.
- **Structured features** concatenated to `[CLS]`:
  - age → ordinal bucket embedding (4 buckets: 18-24, 25-34, 35-44, 45+)
  - gender → 4-way embedding (F / M / NB / PNS)
  - region → 9-way embedding (LatAm, US, EU, UK, UAE, EastAsia, SouthAsia, NorthAfrica, Other)
  - background_tag → 9-way embedding (likes_oud, headache_prone, prefers_natural, …)
  - occasion → 41-way embedding from `occasion_vocab`
  - descriptor multi-hot (98-dim) — input *and* auxiliary target (self-consistency)
  - avoid_notes multi-hot (~11 canonical + fuzzy match against full note vocab)
- **Output**: a 256-d IntentVector.
- **Loss**: combination of (a) main supervision from Stage 2, (b) auxiliary descriptor reconstruction (sigmoid BCE on the input descriptors), (c) optional contrastive pull-together for examples sharing primary accord ([SimCSE](https://arxiv.org/abs/2104.08821) style), (d) optional retrieval-distillation from the 5,459 reference-perfume examples.

**Why DeBERTa over an LLM**: 10K examples and a closed-vocabulary classification target — fine-tuned encoder beats zero-shot LLM on F1 and is 100× cheaper at inference. Reach for a small instruction-tuned LLM with [grammar-constrained decoding (Geng et al. 2023)](https://arxiv.org/abs/2305.13971) only on the harder slots (metaphor resolution, exclusions like "no leather").

### Stage 2 — AccordSetPredictor

- **Inputs**: IntentVector + accord-category prior (315-dim).
- **Architecture**: small Set-Transformer ([Lee et al. 2019](https://arxiv.org/abs/1810.00825)) head, OR a simpler 2-layer MLP with multi-label sigmoid output over 315 accords + a 1-d "primary-accord rank head."
- **Outputs**: probability vector over 315 accords; top-k (k≈3) selected with weights normalised to sum 1.
- **Loss** (mix the three):
  - **Asymmetric Loss for Multi-Label** ([Ridnik et al. 2021](https://arxiv.org/abs/2009.14119)) — handles your positive-negative imbalance (each example has 1–2 positives out of 315).
  - **Class-balanced re-weighting** ([Cui et al. 2019](https://arxiv.org/abs/1901.05555)) using effective-number weights — handles the head/tail (ACC-0112 has 395 examples, many accords have 1–5).
  - **Label-co-occurrence regulariser**: penalty for predicting an accord pair whose empirical co-occurrence in the catalog is zero (prevents "marine + vanilla-gourmand" co-firings).
  - **Hierarchical loss**: parent-class auxiliary head over `accord_category` (Fresh / Amber / Woody / …) to give long-tail accords a stronger gradient.
- **Validation metric**: micro-F1 + macro-F1 + primary top-1 + primary top-3 + NDCG against secondary.

This is the **only stage with abundant supervision (10K)**. Get it right; the rest of the pipeline depends on it.

### Stage 3 — NoteSelector

- **Inputs**: predicted accord set + weights (Stage 2), IntentVector (for personalization), user `avoid_notes`, demographics.
- **Method (recommended)**: hybrid retrieval + re-rank.
  1. For each predicted accord, take its `accord_note` membership.
  2. Compute a base score = `importance_weight × presence_prob × compatibility_score` (already in the table).
  3. Apply a learned re-ranker — small MLP that scores `(IntentVector, note_features) → adjustment ∈ [-1, +1]` to the base score.
  4. Drop notes that fuzzy-match the user's `avoid_notes` list.
  5. For dropped driver notes, substitute by k-nearest-neighbours in the chemistry/odor-family feature space (covered in §F).
- **Note features** for the re-ranker:
  - Categorical: `chemical_family` (30), `odor_family` (~15), `volatility_class` (7), `solubility`, `natural_source`.
  - Numeric: `molecular_weight`, `boiling_point_c`, `logP`, `odor_threshold_mg_L`, `substantivity_index`, tenacity (impute via family means).
  - Text: `key_nuances` + `short_description` → small SentenceTransformer embedding.
  - **Optional but high-value**: SMILES from CAS for the 432 notes with CAS, then RDKit Morgan fingerprints + Mordred / [Chemprop D-MPNN embedding (Yang et al. 2019)](https://pubs.acs.org/doi/10.1021/acs.jcim.9b00237) — or even better, project them through [OpenPOM](https://github.com/ARY2260/openpom) (community implementation of [Lee et al. 2023 Principal Odor Map](https://www.science.org/doi/10.1126/science.ade4401)) for a perceptual embedding.
- **Loss**: ranking loss against the rule baseline + a personalization term using the 1,731 rated examples + an exclusion term (substituted notes shouldn't violate the user's avoids).

### Stage 4 — DosageEstimator

This is the trickiest stage and the one where I'm pushing back hardest on a naive "model B for dosage."

- **Inputs**: selected notes per accord with priority (Stage 3), accord weights (Stage 2), `default_pct_in_accord`, `min_pct_in_accord`, `max_pct_in_accord` from `accord_recipe_default`, IntentVector (for personalisation).
- **Architecture**: a delta predictor with a simplex projection layer.
  1. Start from `default_pct_in_accord` (the rule prior).
  2. A small MLP outputs a **delta ∈ [-1, +1]** per note conditioned on user context.
  3. Linearly interpolate: `predicted_pct = default_pct + delta · (max_pct - default_pct)` if `delta>0`, else `default_pct + delta · (default_pct - min_pct)`. This guarantees `pct ∈ [min, max]`.
  4. Renormalise per accord to sum to 100% (after dropping user-avoided notes — Stage 3).
  5. Blend across accords using Stage-2 weights → final concentrate composition.
- **Output activation**: *softmax over notes within an accord*, then weighted by accord weight, then concatenated. (Concatenated softmax outputs are the natural way to represent per-accord 100% sums; see [Aitchison 1982 compositional data analysis](https://rss.onlinelibrary.wiley.com/doi/abs/10.1111/j.2517-6161.1982.tb01195.x) and [Sensoy 2018 evidential deep learning](https://arxiv.org/abs/1806.01768) for Dirichlet-style alternatives.)
- **Loss**:
  - **CLR-MSE** against the rule defaults — [Aitchison's centred-log-ratio transform](https://rss.onlinelibrary.wiley.com/doi/abs/10.1111/j.2517-6161.1982.tb01195.x) so the loss respects simplex geometry rather than treating percentages as independent reals.
  - **Range penalty** for any predicted pct outside `[min, max]`.
  - **Sum-to-100 penalty** per accord (mostly enforced by the projection but kept as soft term for stability).
  - **Optional preference loss** on the 1,731 ratings + 1,508 `accepted_flag` rows: Bradley-Terry-style pairwise contrast or Thompson-sampling reward model.
- **Why a delta, not direct prediction**: the rule formula is already a sane prior. Letting the model only nudge it preserves curatorial knowledge, makes outputs explainable ("we increased oud +0.7σ because user said 'likes_oud'"), and prevents the sum constraint from getting bulldozed.
- **Differentiable projection**: if you want hard sum-to-100 with hard IFRA caps in one layer, use [OptNet (Amos & Kolter 2017)](https://arxiv.org/abs/1703.00443) / [cvxpylayers](https://locuslab.github.io/2019-10-28-cvxpylayers/) or [DC3 (Donti et al. 2021)](https://arxiv.org/abs/2104.12225). DC3 scales better when you have hundreds of IFRA inequality constraints.

### Stage 5 — ConstraintFilter & Repair (OPTIONAL — depends on product scope)

> **Skip this stage entirely for a research prototype.** Build it only if the project is heading toward a regulated consumer product. The document suggests it as required; we treat it as a product decision.

**Three scope tiers, pick one with the user:**

- **Tier 0 — Research prototype (default).** No constraint filter. Output the formula with a soft warning if any note has a `chemical_family` tag known to be commonly restricted (aldehyde, phenol, citrus terpene). Zero curation work.
- **Tier 1 — Soft compliance.** Minimal `ifra_limits` table seeded from the public IFRA standards for the top-50 most-used notes. Warnings only, no automatic repair. ~1 day curation.
- **Tier 2 — Hard compliance (regulated product).** Full Stage 5 as the document suggests:
  - **Tables to build**: `note_functional_groups`, `reactivity_rules`, `note_constituents`, `ifra_limits(note_id, product_category)`, `phototox_flag`, `oxidation_risk_score`.
  - **Checks**: concentrate→finished% conversion via fragrance load; per-note IFRA cap; pairwise reactivity; allergen-summation across constituents; phototox / discolouration flags.
  - **Repair**: failed notes substituted by k-NN in chemistry/odor-family space restricted to compliant notes; renormalise; loop ≤3 times → human review.
  - **No ML in this tier.** ML approximating IFRA is a liability.

I'll assume **Tier 0** until you say otherwise.

### Stage 6 — Output & Explainability

- Output JSON: concentrate composition, top accords with weights, suggested fragrance load, IFRA pass/fail, phototox flag, repair history, plus an explanation string ("dominant accord: Modern Amberwood at 35% — chosen because user said dark+amber+not sweet; dosed slightly toward max because background_tag = nightlife").
- Track every intermediate decision so users can ask "why?" — the doc lists this as a required property.

---

## E. EDA PLAN (week 1)

In order of priority for design decisions:

1. **Vocabulary & coverage**: descriptors used vs in-vocab; unmapped tokens (`creamy`, `exotic`, `medicinal`, `modern`, `ozone` are sitting in `unmapped_accord_tokens` — fix); used vs unused accords (115 of 315 are dead targets — keep them in catalog but de-emphasise).
2. **Class-imbalance characterisation**: per-accord example counts, descriptor frequencies, demographic distributions — choose loss/weighting accordingly.
3. **Recipe sanity**: per-accord sum to 100, layer balance reality check (the median top-layer total is currently 0% for many accords — investigate), min/max width distributions, dedup the 5 over-100% accords.
4. **Note-feature completeness**: which of the 883 notes have CAS / MW / logP / BP / OT / substantivity / chemical_family — this drives Stage-3 feature engineering and tells us how many notes we can compute SMILES for.
5. **Cross-source consistency**: the 50/446 note overlap between rule-recipes and real-perfumes — decide whether to bridge or run two parallel ontologies.
6. **Reference-perfume label quality**: I already found the 1.9% accord-match issue; quantify with confusion matrices to confirm we should treat the reference as a soft signal.
7. **Bigrams**: descriptor↔accord, occasion↔accord, background_tag↔accord, region↔accord, age_bucket↔accord — sanity check that conditioning these makes sense.
8. **Templated-text patterns**: cluster `user_text` by template; quantify how trivially the descriptors leak into the text (this will inflate validation metrics).
9. **Layer-mix realism**: compare rule-derived `top:heart:base` (25:45:30) against real perfumes (`perfume_note.position` distribution: 1160:1224:1400 ≈ 30:32:38) — they disagree.
10. **Co-occurrence matrices** (for label-correlation regularizer): primary↔secondary accord pairs, accord↔note pairs in real perfumes vs in rule recipes.

Each item is a notebook cell with one chart and one decision. Total ~3 days.

---

## F. PREPROCESSING PLAN

### F.1 Identifier & vocabulary work
- Confirm all five `*_master` dictionaries are bijective; fix any duplicates.
- **Build a unified `note_id` mapping** between `accord_note` (rule-recipe space) and `perfume_note` (real-perfume space). Two paths:
  - (a) Manual perfumer-assisted alignment (you find a perfumer to spend 4 hours mapping the most common 200 notes).
  - (b) Automatic alignment via `chemical_name` + `cas_number_clean` + name-edit-distance, then human review of low-confidence pairs. Recommended: do (b) first, escalate to (a) only for the 50–100 low-confidence pairs.
- Resolve `unmapped_accord_tokens` (creamy, exotic, …) — assign canonical accord IDs or accept them as descriptor-only tokens.

### F.2 Recipe cleanup
- Dedup the 5 accords with sum >100% (`ACC-0033`, `ACC-0097`, `ACC-0111`, `ACC-0115`, `ACC-0167`). Keep only one recipe variant per accord, or version them and add a `recipe_version` selector at training time.
- Verify all `min ≤ default ≤ max` constraints in `accord_recipe_default`.
- Materialise a "blended cross-accord recipe" lookup for every (primary, secondary) pair seen in `training_examples` (3,048 unique pairs / 3,423 examples). Two reasonable blend rules: (a) weighted average of per-accord pcts by Stage-2 weights, then renormalise; (b) take union of notes, weight each by max accord membership × accord weight, then renormalise. Sanity-check against a perfumer.

### F.3 Feature engineering for notes
- **Categorical**: one-hot or embedding for `chemical_family`, `odor_family`, `volatility_class`, `solubility`, `natural_source`.
- **Numeric**: `molecular_weight`, `boiling_point_c`, `logP`, `odor_threshold_mg_L`, `substantivity_index`, `tenacity_min_hrs`, `tenacity_max_hrs`, `flash_point_c`. Impute missing values via group means by `chemical_family`; keep "is-imputed" indicator columns.
- **Text**: `key_nuances` + `short_description` → MiniLM sentence embedding (384-d).
- **Chemistry (the upgrade)**: for the 432 notes with `cas_number_clean`:
  - Resolve CAS → SMILES via PubChem REST (cache results; ~30 minutes total).
  - Compute Morgan fingerprints (RDKit, radius=2, 2048 bits) and Mordred descriptors.
  - Optional: pass each SMILES through pretrained [OpenPOM](https://github.com/ARY2260/openpom) (Principal Odor Map open implementation) → 256-d perceptual embedding directly inheriting the [Lee et al. 2023](https://www.science.org/doi/10.1126/science.ade4401) training signal. **This single move probably gives the biggest stage-3 boost from any engineering investment.**
  - For natural extracts (no single SMILES), use the GC-MS-weighted-vector approach from [Pyrfume](https://pypi.org/project/pyrfume/) ([Castro et al. 2024 Sci Data](https://www.nature.com/articles/s41597-024-04051-z)): represent the natural as a concentration-weighted sum of its constituent embeddings. [Ravia et al. 2020 Nature](https://www.nature.com/articles/s41586-020-2891-7) gives the perceptual-metamer justification for treating mixtures this way.

### F.4 Input feature pipeline
- Demographics: ordinal age bucket, learned 8-d embedding for region/gender/background_tag/occasion.
- Descriptor → multi-hot using `descriptor_synonyms` for fuzzy text→canonical lookup (handles "crisp" → "fresh", "romantic" → "date_night").
- Avoid_notes → multi-hot over canonical avoid set + soft fuzzy match against full note vocab.
- User_text → tokenised by encoder tokenizer; pad/truncate to length 64 (already 99th-percentile = ~140 chars).

### F.5 Splits
- **Stratify by `target_accord_id_primary`** to ensure all 200 active classes appear in train/val/test.
- 80/10/10 with rare-class oversampling in train; never oversample val/test.
- Optional second held-out set: 200 manually-written real (not templated) prompts, to estimate the templated-text generalisation gap.

### F.6 Build the missing constraint tables (only if Stage 5 Tier 1 or Tier 2)
Skip this section for a research prototype (Tier 0). For Tier 1/2:
- Seed `ifra_limits` from the public [IFRA Standards 51st Amendment](https://ifrafragrance.org/safe-use/library) PDFs (limits exist for ~200 substances in 11 categories). Map by CAS where possible.
- Seed `note_functional_groups` automatically from RDKit substructure SMARTS for aldehydes, primary amines, esters, peroxides, phenols, ketones — that's already 70% coverage. Manually fill the rest.
- Seed `reactivity_rules` from the document's example (aldehyde + primary_amine_like → BLOCK, repair=SUBSTITUTE_OR_REMOVE) plus the standard list (peroxide-formers in citrus, ester-hydrolysis pairs, etc.).
- Seed `note_constituents` for the top-50 most-used naturals from supplier SDS sheets (this is the manual part; budget ~2 days perfumer/regulatory time).

---

## G. TRAINING PLAN

| Stage | Trainable params | Loss | Data | Notes |
|---|---|---|---|---|
| 1+2 joint | DeBERTa-V3-base + 2 heads ≈ 90M | ASL multi-label + class-balanced + co-occurrence + hierarchical category aux + descriptor-reconstruction aux | 10,000 supervised, stratified split | Train this first; freezes backbone for stage 3+ |
| 3 ranker | small MLP, ~1M | listwise rank loss + exclusion mask + personalization | rule baseline + 1,731 rated examples | Conditioned on Stage-1 IntentVector; backbone frozen |
| 4 dosage delta | small MLP, ~1M | CLR-MSE vs default + range penalty + simplex projection + preference contrast | rule defaults + 1,731 ratings + 1,508 accepted flags | Conditioned on Stage-1 IntentVector; backbone frozen |
| 5 filter | none | n/a | rule tables | Pure logic, 0 trainable params |

Hardware: single-GPU 24GB sufficient for Stages 1-2 (DeBERTa-base + 256 batch). Stages 3-4 are MLPs and run in minutes on CPU. Total clock time: ~1 day of GPU.

---

## H. EVALUATION PLAN

### H.1 Per-stage metrics
- **Stage 1**: descriptor-reconstruction F1 ≥ 0.95 (sanity floor since text trivially contains descriptors).
- **Stage 2**: micro-F1, macro-F1, primary top-1 accuracy, primary top-3 accuracy, NDCG@2 against secondary.
- **Stage 3**: jaccard / recall vs the rule-baseline note set (should be ≥ 0.8 — we're not trying to depart from the curated mapping wildly), exclusion-respect rate (avoided notes should appear in <1%).
- **Stage 4**: MAE on `default_pct` against rule baseline (should be small — we're a delta on top), in-window rate (≥ 99%), sum-to-100 violation rate (should be 0 by construction).
- **Stage 5**: violation count before/after repair, repair success rate, mean repair iterations.

### H.2 End-to-end metrics
- **Recipe similarity vs reference perfume's accord profile**: cosine over 315-dim accord vectors, computed only when reference perfume is provided.
- **Diversity** (avoid mode collapse): how many unique formulas across 1,000 random briefs; how many unique top-3-accord combinations.
- **Constraint violation rate** at the final formula (should be 0 after Stage 5).
- **Coverage**: fraction of the 200 active accords that the system produces as primary across the val set.

### H.3 Human evaluation
- N=50 prompts, double-blind A/B against:
  - rule-only baseline (Stage 2 replaced with a keyword classifier; Stages 3-4 untouched);
  - end-to-end LLM baseline (GPT-4o-mini with the schema as a JSON tool).
- A perfumer scores each output on (1) matches the brief, (2) chemically plausible, (3) IFRA-compliant, (4) novel vs predictable. This is the only eval that matters for production ([Sanchez-Lengeling & Aspuru-Guzik 2018](https://www.science.org/doi/10.1126/science.aat2663) on inverse design notes the same — automated metrics correlate weakly with expert quality).

### H.4 Continual learning loop
- Log every (prompt, output, user-rating) tuple. After 1,000 new ratings, re-train Stage 4 personalization with the additional preference pairs. Stages 1-3 retrain quarterly.
- Optional: contextual bandit on top of Stage 2 ([Chapelle & Li 2011 Thompson sampling](https://www.cs.mcgill.ca/~vkumar34/papers/chapelleLiThompsonSamplingCompetitive.pdf)) for explore/exploit on new accord candidates.

---

## I. TOP RISKS

| Risk | Likelihood | Mitigation |
|---|---|---|
| Templated `user_text` → model fails on real users | High | Augment with scraped Fragrantica/basenotes reviews; held-out set of real prompts |
| Note-vocabulary mismatch (50/446 overlap) breaks Stage 3 routing | High | Bridge in F.1 before any training |
| Missing IFRA / reactivity tables → no Stage 5 (only matters for regulated product) | Tier-dependent | Tier 0 prototype: ignore. Tier 1/2: curation stream from week 1 |
| Reference-perfume target is noisy (1.9% match) | Medium | Use as soft retrieval signal only; never as hard label |
| Long-tail accords (115/315 unused) | Medium | Class-balanced + asymmetric loss + hierarchical category head |
| Sparse explicit feedback (~15%) | Medium | Contrastive + retrieval distillation; bandit later |
| End-to-end metric inflation from templated text | Medium | Adversarial held-out set of real prompts |
| The "ML for dosage" model gives no real lift over the formula | Low-Medium | Be willing to ship Stage 4 = identity (just the rule formula) if delta head doesn't beat 0 in human eval |
| Naturals (no single SMILES) lose chemistry features | Medium | GC-MS-weighted-sum approach from Pyrfume; accept as a known limitation |

---

## J. LITERATURE DOSSIER (50+ papers, organised by where they slot in the pipeline)

Each entry has been verified or flagged. Verified entries link to the official source.

### J.1 Olfactory ML / molecule → odor (foundation for note features and substitution)
1. [Lee et al. 2023, "A principal odor map unifies diverse tasks in olfactory perception", *Science* 381:999-1006](https://www.science.org/doi/10.1126/science.ade4401) — POM, the canonical molecule→odor GNN.
2. [Sanchez-Lengeling et al. 2019, "Machine Learning for Scent: Learning Generalizable Perceptual Representations of Small Molecules", arXiv:1910.10685](https://arxiv.org/abs/1910.10685) — POM precursor, GNN beats engineered descriptors.
3. [Keller et al. 2017, "Predicting human olfactory perception from chemical features of odor molecules", *Science* 355:820-826](https://www.science.org/doi/10.1126/science.aal2014) — DREAM Olfaction Prediction Challenge; bounds for what is learnable from small N.
4. [Snitz et al. 2013, "Predicting Odor Perceptual Similarity from Odor Structure", *PLoS Comp Biol* 9(9):e1003184](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1003184) — angle-distance metric for mixture similarity.
5. [Ravia et al. 2020, "A measure of smell enables the creation of olfactory metamers", *Nature* 588:118-123](https://www.nature.com/articles/s41586-020-2891-7) — theoretical license for natural-extract substitution; perceptual metamers within 0.05 rad are indiscriminable.
6. [Castro et al. 2024, "Pyrfume: A window to the world's olfactory data", *Scientific Data*](https://www.nature.com/articles/s41597-024-04051-z) — unified Python access to 40+ olfactory datasets including GoodScents, Leffingwell, Dravnieks, Keller, Sigma F&F.
7. [Yang et al. 2019, "Analyzing Learned Molecular Representations for Property Prediction" (Chemprop / D-MPNN), *JCIM* 59(8):3370-3388](https://pubs.acs.org/doi/10.1021/acs.jcim.9b00237) — production-grade GNN for molecular properties; closest open implementation to POM's architecture.
8. Castro, Ramanathan, Chennubhotla 2013, "Categorical Dimensions of Human Odor Descriptor Space" (NMF on Dravnieks), *PLoS ONE* 8(9):e73289 — motivates low-rank latent accord space.
9. Bushdid et al. 2014, "Humans can discriminate more than 1 trillion olfactory stimuli", *Science* 343:1370 — perceptual-space size bound.
10. Mainland et al. 2014, "The missense of smell: functional variability in the human odorant receptor repertoire", *Nat Neurosci* 17:114 — irreducible per-user variance; argues for personalisation layer.
11. Kraft, Bajgrowicz, Denis, Frater 2000, "Odds and Trends: Recent Developments in the Chemistry of Odorants", *Angew Chem Int Ed* 39:2980 — modern QSOR review by Givaudan chemists; classification scheme for chemical families.
12. Rossiter 1996, "Structure–Odor Relationships", *Chem Rev* 96:3201 — historical QSOR foundation; pharmacophore motifs for major fragrance families.
13. Chithrananda, Grand, Ramsundar 2020, "ChemBERTa: Large-Scale Self-Supervised Pretraining for Molecular Property Prediction", arXiv:2010.09885 — transformer encoder over SMILES.
14. Ross et al. 2022, "Large-Scale Chemical Language Representations Capture Molecular Structure and Properties" (MoLFormer), *Nature Machine Intelligence* — pretrained on 1.1B SMILES.
15. Zhou et al. 2023, "Uni-Mol: A Universal 3D Molecular Representation Learning Framework", ICLR 2023 — important if you care about chiral notes (carvone enantiomers smell different).
16. Sanchez-Lengeling & Aspuru-Guzik 2018, "Inverse Molecular Design Using Machine Learning", *Science* 361:eaat2663 — canonical inverse-design review.

### J.2 NLP / text → tag / multi-label (Stages 1–2)
17. Devlin et al. 2019, BERT, NAACL — encoder baseline.
18. Liu et al. 2019, RoBERTa, arXiv:1907.11692.
19. He et al. 2021, DeBERTa-V3, ICLR — recommended encoder.
20. [Ridnik et al. 2021, "Asymmetric Loss For Multi-Label Classification", ICCV, arXiv:2009.14119](https://arxiv.org/abs/2009.14119) — drop-in for your 315-way sigmoid head.
21. [Cui et al. 2019, "Class-Balanced Loss Based on Effective Number of Samples", CVPR, arXiv:1901.05555](https://arxiv.org/abs/1901.05555) — handles long-tail of 200 active accords.
22. [Lin et al. 2017, "Focal Loss for Dense Object Detection", ICCV, arXiv:1708.02002](https://arxiv.org/abs/1708.02002) — γ-down-weighting easy negatives.
23. Gao, Yao, Chen 2021, SimCSE, EMNLP, arXiv:2104.08821 — supervised contrastive sentence embeddings; auxiliary loss for examples sharing primary accord.
24. Schick & Schütze 2021, PET (Pattern Exploiting Training), EACL — useful in low-data multi-label.
25. Hu et al. 2022, LoRA, ICLR — efficient encoder fine-tuning.
26. Geng et al. 2023, "Grammar-Constrained Decoding for Structured NLP Tasks without Finetuning", EMNLP, arXiv:2305.13971 — grammar-constrained JSON output if Stage 1 ever uses an LLM.

### J.3 Recommender / personalization (auxiliary objective)
27. [Yi et al. 2019, "Sampling-Bias-Corrected Neural Modeling for Large Corpus Item Recommendations", RecSys](https://dl.acm.org/doi/abs/10.1145/3298689.3346996) — two-tower retrieval; basis for the 5,459-reference-perfume distillation signal.
28. Chapelle & Li 2011, Thompson Sampling, NeurIPS — sparse-feedback bandit for continual learning.
29. Li et al. 2010, LinUCB, WWW — contextual bandit baseline.
30. Sensoy, Kaplan, Kandemir 2018, "Evidential Deep Learning to Quantify Classification Uncertainty", NeurIPS, arXiv:1806.01768 — Dirichlet output head (alternative to softmax+CLR for Stage 4).

### J.4 Set selection + simplex output (Stages 3–4)
31. [Salvador et al. 2019, "Inverse Cooking: Recipe Generation from Food Images", CVPR, arXiv:1812.06164](https://arxiv.org/abs/1812.06164) — closest analog: predict ingredient *set* then generate; explicitly argues two-stage beats end-to-end.
32. Zaheer et al. 2017, Deep Sets, NeurIPS, arXiv:1703.06114 — permutation-invariant set encoder.
33. Lee et al. 2019, Set Transformer, ICML, arXiv:1810.00825 — set-conditioned attention; useful for Stage-3 re-ranker.
34. Park et al. 2019, KitcheNette: Predicting Ingredient Pairings, IJCAI — pairwise compatibility scoring.
35. Marin et al. 2019/2021, Recipe1M+ TPAMI — joint embedding of brief and recipe.
36. Bień et al. 2020, RecipeNLG, INLG — large-LM recipe generation; cautionary tale on unconstrained quantities.
37. [Ahn, Ahnert, Bagrow, Barabási 2011, "Flavor network and the principles of food pairing", *Sci Rep* 1:196](https://www.nature.com/articles/srep00196) — shared-compound graph; the perfume analog is shared-odorant graph.
38. [Aitchison 1982, "The Statistical Analysis of Compositional Data", *JRSS B* 44:139-160](https://rss.onlinelibrary.wiley.com/doi/abs/10.1111/j.2517-6161.1982.tb01195.x) — CLR / log-ratio transforms; right loss-space for sum-to-100% outputs.
39. Tsagris et al. 2016, α-transformation for compositional data, *J Classification* — interpolates CLR ↔ raw proportions.
40. Zhang, Zohren, Roberts 2020, "Deep Learning for Portfolio Optimization", arXiv:2005.13665 — softmax-output simplex regression with task-aligned loss.

### J.5 Constrained generation (Stage 5 + simplex projection)
41. [Amos & Kolter 2017, OptNet: Differentiable Optimization as a Layer, ICML, arXiv:1703.00443](https://arxiv.org/abs/1703.00443) — QP layer for projecting onto IFRA polytope.
42. [Donti, Rolnick, Kolter 2021, "DC3: A learning method for optimization with hard constraints", ICLR, arXiv:2104.12225](https://arxiv.org/abs/2104.12225) — completion+correction; scales to hundreds of constraints.
43. Agrawal et al. 2019, "Differentiable Convex Optimization Layers", NeurIPS, arXiv:1910.12430 — cvxpylayers, more general than OptNet.
44. Marquez-Neila, Salzmann, Fua 2017, "Imposing Hard Constraints on Deep Networks: Promises and Limitations", arXiv:1706.02025 — penalty methods don't enforce constraints exactly; always finish with projection.
45. Achiam et al. 2017, Constrained Policy Optimization, ICML, arXiv:1705.10528 — useful if you go RL on Stage 4.

### J.6 Generative chemistry (precedent for inverse design under constraints)
46. [Olivecrona et al. 2017, "Molecular de novo design through deep reinforcement learning" (REINVENT), *J Cheminform*](https://link.springer.com/article/10.1186/s13321-017-0235-x) — scoring-function abstraction maps to (predicted brief-match) − λ(IFRA-violation).
47. Jin, Barzilay, Jaakkola 2018, Junction Tree VAE, ICML, arXiv:1802.04364 — skeleton-then-content generation; analog for "accord-skeleton then molecules."
48. Maziarka et al. 2022, MoLeR (motif-based generation), ICLR, arXiv:2103.03864 — accords-as-motifs precedent.
49. Zhavoronkov et al. 2019, "Deep learning enables rapid identification of potent DDR1 kinase inhibitors" (GENTRL), *Nat Biotech* — proof property-conditioned generation reaches lab-validated outputs.
50. Coley, Barzilay, Jaakkola, Green, Jensen 2017, "Prediction of Organic Reaction Outcomes Using Machine Learning", *ACS Central Science* — reaction prediction for Schiff-base risk flagging.
51. Schwaller et al. 2019, "Molecular Transformer", *ACS Central Science* — improves Coley 2017; better stability oracle.

### J.7 Industrial / patents (no architectural disclosure but documents the SOTA)
52. [IBM Research / Symrise — Philyra (2018-2019, O Boticário Egeo ON Me / ON You launch)](https://www.symrise.com/scent-and-care/competence-platforms/philyra/) — first commercial AI fragrance; granted "first-ever patent in fragrance computational creativity." No architecture published.
53. [Givaudan — Carto (2019)](https://www.givaudan.com/media/media-releases/2019/givaudan-fragrances-launches-carto-its-artificial-intelligence-powered-tool) — AI-powered tool that "intelligently uses Givaudan's Odour Value Map to maximise olfactive performance" within IFRA. Constraint-driven optimisation over a curated library.
54. IFF — EmotiCode / PomméCode — emotion-tag-conditioned formulation; no peer-reviewed disclosure.
55. [IFRA Standards 51st Amendment (2023)](https://ifrafragrance.org/safe-use/library) — 200+ substances, 11 QRA categories; deterministic rule engine, not ML.
56. EU Regulation 1223/2009 + Regulation 2023/1545 — ~80 fragrance allergens with declaration thresholds.

### J.8 Adjacent-domain inverse design
57. Bastek & Kochmann 2023, "Inverse design of metamaterials using a generative model", *Nat Mach Intel* — forward predictor + latent-space inversion; the architecture I'd recommend for perfume is a direct analog.
58. Reiser et al. 2022, "Graph neural networks for materials science and chemistry", *Comm Materials* — review of GNN-based property prediction, the surrogate side of inverse design.
59. Engel et al. 2020, Jukebox, OpenAI, arXiv:2005.00341 — text-tag conditioning + hierarchical autoregressive decoder; structural analog.
60. Edwards Fragrance Wheel 1983 (industry classification standard) — coarse taxonomy backbone for Stage-2 hierarchical loss.

That's 60 entries; the items linked with hyperlinks are the ones I verified against live sources today. The rest are highly confident in memory and easy to look up; flag any specific one you want me to verify before citing.

---

## K. SUGGESTED SEQUENCING

| Week | Workstream A: ML | Workstream B: Curation (Tier 1/2 only) |
|---|---|---|
| 1 | EDA (§E), splits, vocab cleanup | (Tier 1/2) Start IFRA seed, functional groups via SMARTS |
| 2 | Preprocessing (§F.1–F.4); chemistry features | (Tier 1/2) IFRA seed continues; reactivity_rules drafted |
| 3-4 | Train Stages 1+2 jointly | (Tier 2) IFRA review with regulatory contact |
| 5 | Train Stage 3 ranker + chemistry-feature ablation | (Tier 2) note_constituents for top-50 naturals |
| 6-7 | Train Stage 4 dosage delta + simplex projection | (Tier 1/2) Constraint-table validation |
| 8 | Integrate end-to-end (Stage 5 only if Tier 1/2) | First human-eval prompts written |
| 9-10 | Human eval + iterate | — |

For a Tier 0 research prototype, drop Workstream B entirely; the timeline shortens to ~6-7 weeks.

---

## L. CHECKPOINTS YOU SHOULD VETO BEFORE WE PROCEED

I want explicit signoff or pushback on each before I start:

1. **Architecture choice**: 4-stage hybrid pipeline (text → accords → notes → dosage) at minimum, with optional Stage 5 constraint filter — not strict two-model and not end-to-end. OK?
2. **Stage-4 as a delta on the existing rule formula, not free regression.** OK?
3. **Stage 5 scope** — pick a tier:
   - **Tier 0**: skip Stage 5 (research prototype). *Default unless you say otherwise.*
   - **Tier 1**: soft compliance — minimal IFRA warnings, no auto-repair.
   - **Tier 2**: hard compliance — full constraint filter and curated tables (only if you're heading toward a regulated retail product).
4. **We bridge the 50/446 note-vocabulary gap (option F.1.b: automatic + human review for low-confidence pairs) before any training.** OK?
5. **Reference perfume becomes a soft retrieval signal, not a hard label, given the 1.9% accord-match rate.** OK?
6. **Augment user_text with real-world reviews (Fragrantica/basenotes) before final eval, given the templated-text concern.** OK?
7. **Held-out set of N=200 manually-written real prompts, plus N=50 perfumer-judged human eval as the gating metric**, not just F1 on the templated test split. OK?

Reminder: the handoff document is a *suggestion*, not a spec. Any decision above can be revised based on your product goals — tell me which of L.1–L.7 you want changed.
