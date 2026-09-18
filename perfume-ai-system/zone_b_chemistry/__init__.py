"""ZONE B — deterministic chemistry + safety. NO LLM CALLS MAY BE IMPORTED HERE.

Modules (built one task at a time, see CLAUDE.md):
  formula_builder.py  Task 2 — top/heart/base structure from accord weights (Carles)   DONE 2026-09-16
  accord_study.py     Carles' ratio-study method as a deterministic variation generator
  safety_engine.py    Task 3 — regulatory REJECT -> IFRA cap/reject/flag -> group rules -> caps -> reactions
  optimizer.py        Task 4 — rebalance after safety cuts, normalise to 100 % (diluent if all pinned)
  pipeline.py         run_zone_b / run_zone_b_for_perfume
  product_formulation.py  concentrate -> bottle (ethanol, water, auxiliaries, allergen label)
  invention.py        new compositions from preference terms (Carles signature + ratio series)

All data comes from load_data.load_all(); nothing is hard-coded.
"""
