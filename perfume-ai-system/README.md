# AI Perfume Formulation System

User preferences → matched perfume → (on approval) a chemically balanced, IFRA-compliant,
UK-market-legal formula for a mixing machine. Read `CLAUDE.md` first — the two-zone rule
(LLM in Zone A only; deterministic chemistry + safety in Zone B) is the whole design.

## Status

| Task | | 
|---|---|
| 0 Architecture + data design | done |
| **1 Skeleton + `load_data.py`** | **done (2026-09-12)** — 40 tests |
| 2 `formula_builder.py` | next |
| 3 `safety_engine.py` | |
| 4 `optimizer.py` | |
| 5 Zone A matcher + input handler | |
| 6 Zone A describer | |
| 7 Streamlit app | |

## Quick start

```
pip install -r requirements.txt
python data/build_datasets.py     # regenerate data files from their sources (optional)
python load_data.py               # data report; exit 2 while catalogue defects remain
python -m pytest tests -q
```

`load_data.load_all()` returns a `Data` object with one cleaned DataFrame per table plus
`issues` (ERROR / WARNING / INFO), `unmatched_accord_notes`, `regulatory_overrides` and
`notes_regulated`. See `data/DATA_PROVENANCE.md` for where every file comes from and the
changes made in the 2026-09-11 IFRA audit.

## Known data defects (reported by the loader, must be fixed in the source workbooks)

- 50 notes carry a CAS number that fails the CAS checksum → CAS-based safety lookups miss them
- 102 accord note names (245 rows) have no match in the notes catalogue
- 50 note names appear with conflicting CAS / volatility; 72 exact duplicate rows
- 10 perfumes have their columns shifted in the source (repaired on load, Gender lost)

## Status (2026-09-18)

All seven build tasks plus the product-formulation and invention layers exist and are tested (`python -m pytest -q`, 199 tests). Read **CLAUDE.md → ⏩ RESUME HERE** for
what is done, what is open, and the next step.

```
python load_data.py                          # data report (exit 2 while the two decision lists are open)
python app.py "fresh woody for summer"       # match -> formula -> safety -> bottle formulation, no API key needed
python app.py --invent "citrus, mossy, rose" --family Chypre   # invent a new composition (Carles method)
streamlit run app.py                         # the UI (pip install streamlit)
python data/build_datasets.py                # regenerate data after editing a decision CSV
python data/reconcile_notes.py | python data/verify_cas.py --offline | python data/reconcile_accords.py
```

Safety results are **provisional** until the literature fractions in `constituents.csv` are replaced by supplier CoA values.
