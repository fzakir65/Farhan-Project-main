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
