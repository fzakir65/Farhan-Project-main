# AI Perfume Formulation System

User preferences → matched perfume → (on approval) a chemically balanced, IFRA-compliant,
UK-market-legal formula for a mixing machine. Read `CLAUDE.md` first — the two-zone rule
(LLM in Zone A only; deterministic chemistry + safety in Zone B) is the whole design.

## Status

Every build task is done and tested — `python -m pytest -q` runs **246 tests** (~4 min).

| Task | |
|---|---|
| 0 Architecture + data design | done |
| 1 Skeleton + `load_data.py` | done |
| 2 `formula_builder.py` + `accord_study.py` | done |
| 3 `safety_engine.py` | done |
| 4 `optimizer.py` + `pipeline.py` | done |
| 5 Zone A matcher, input handler, lexicon, questionnaire | done |
| 6 Zone A describer | done |
| 7 Streamlit app + CLI | done |
| — product formulation, invention, stability | done |
| **Zone C (machine control)** | **not started** — blocked on supplier CoA values |

All 455 library profiles and all 236 accords pass the full Zone B safety pass.

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

## Known data state (what `python load_data.py` reports today)

The defects this section used to list were worked through between 2026-09-15 and 2026-09-24.
What remains is deliberate, and the loader exits non-zero on the one ERROR by design:

- **1 ERROR** — 13 accord note names have no material in the notes catalogue, so those accords
  cannot be built. An honest floor: author the materials or drop the accords.
- 0 checksum-failing CAS numbers (corrected where two sources agreed, blanked where they did not —
  missing beats wrong). 85 notes have no CAS at all; accords and bases are expected among them.
- 3 CAS numbers are legitimately shared between notes; 5 more are a reported defect where a natural
  oil was given its chief constituent's number (`reference/note_expansion_cas_conflicts.csv`).
  That error makes the engine stricter than reality, never less strict.
- 54 materials disagree with PubChem on molecular weight or logP — reported, not silently replaced.
- The 10 column-shifted source rows are now repaired at build time rather than on load.

## Commands

Read **CLAUDE.md → ⏩ RESUME HERE** for what is done, what is open, and the next step.

```
python load_data.py                          # data report (exit 2 while the two decision lists are open)
python app.py "fresh woody for summer"       # match -> formula -> safety -> bottle formulation, no API key needed
python app.py --invent "citrus, mossy, rose" --family Chypre   # invent a new composition (Carles method)
python app.py --quiz                         # the 8-question path, fully deterministic
streamlit run app.py                         # the UI (pip install streamlit)
python data/build_datasets.py                # regenerate data after editing a decision CSV
python data/reconcile_notes.py | python data/verify_cas.py --offline | python data/reconcile_accords.py
```

Safety results are **provisional** until the literature fractions in `constituents.csv` are replaced by supplier CoA values.

Plain-English write-ups of the data problem and what new datasheets need are in [`docs/`](docs/).

## Not medical or legal advice

A research project. Nothing here has been reviewed by a qualified perfumer or a cosmetic safety assessor.
Do not put its output on skin or sell it without a proper Cosmetic Product Safety Report.
