# Farhan Project — Perfumery ML System

Repository for the perfume-recipe ML project: turn a natural-language scent description into a manufacturable perfume formula.

## Layout

```
.
├── PERFUMERY_ML_PLAN.md                     # Full architecture/EDA/preprocessing plan (review §L)
├── DATA_ISSUE_FOR_BOSS.txt                  # Plain-English summary of dataset limitations
├── document_text.txt                        # Extracted text from the handoff document
├── Document_1_Perfumery_Science_*.html      # Original handoff document (HTML)
├── Document_1_Perfumery_Science_*.docx      # Original handoff document (Word)
├── *.xlsx                                   # Source datasets (4 workbooks)
├── eda/
│   ├── run_eda.py                           # End-to-end EDA pipeline (one-shot)
│   ├── EDA_REPORT.md                        # Consolidated report w/ executive summary
│   ├── figures/                             # 40 charts produced by run_eda.py
│   └── tables/                              # 78 CSV outputs (preprocessing-ready)
└── preprocessing/
    ├── run_preprocessing.py                 # End-to-end preprocessing pipeline (plan §F, one-shot)
    ├── PREPROCESSING_REPORT.md              # Generated report: decisions + review items
    └── outputs/                             # Note bridge, clean recipes, blends, features, splits
```

## Reproducing the EDA

```bash
pip install pandas openpyxl matplotlib seaborn numpy
python3 eda/run_eda.py


```

Outputs land under `eda/figures/`, `eda/tables/`, and `eda/intermediate/` (the last is gitignored — regenerated from source on demand).

## Reproducing the preprocessing

```bash
pip install pandas openpyxl numpy
python3 preprocessing/run_preprocessing.py
```

Outputs land under `preprocessing/outputs/` (committed) and `preprocessing/intermediate/` (gitignored cache); the run also regenerates `preprocessing/PREPROCESSING_REPORT.md`. Deterministic (seed 42). Implements plan §F at Tier-0 scope: note-vocabulary bridge + unified note ids (F.1), recipe dedup/renormalisation and blended pair recipes (F.2), note feature table with imputation flags (F.3), training multi-hot features + Stage-1 feature spec (F.4), and stratified 80/10/10 splits with class weights (F.5). Chemistry (SMILES/OpenPOM) and text embeddings are deferred and bolt onto `06_note_features.csv` by `note_id`.

## Status

- [x] Document analysis
- [x] Dataset inventory and EDA (19 sections, 40 figures, 78 tables)
- [x] Architecture plan (§A–§L in `PERFUMERY_ML_PLAN.md`)
- [x] Preprocessing pipeline (plan §F — see `preprocessing/PREPROCESSING_REPORT.md`; bridge review pending)
- [ ] Stage 1+2 model training (next)
- [ ] Stage 3 note re-ranker
- [ ] Stage 4 dosage delta head
- [ ] (Optional) Stage 5 IFRA / safety filter

## Key data-quality findings (see EDA report §0 for full list)

1. The 10K training examples are templated; descriptors leak verbatim 43% of the time.
2. The dosage table is a deterministic auto-formula (`recipe_version=v0.1-auto`), not perfumer-curated.
3. Rule-recipe and real-perfume vocabularies are essentially disjoint (50 of 883 notes overlap).
4. Reference perfume tag matches the labelled primary accord only 1.91% of the time.
5. Constraint tables (IFRA, reactivity, allergens) referenced by the design doc don't exist.

See `DATA_ISSUE_FOR_BOSS.txt` for a non-technical summary.
