"""ZONE B — deterministic chemistry + safety. NO LLM CALLS MAY BE IMPORTED HERE.

Modules (built one task at a time, see CLAUDE.md):
  formula_builder.py  Task 2 — top/heart/base structure from accord weights (Carles)
  safety_engine.py    Task 3 — regulatory REJECT -> IFRA cap/reject/flag -> group rules -> caps -> reactions
  optimizer.py        Task 4 — rebalance after safety cuts, normalise to 100 %

All data comes from load_data.load_all(); nothing is hard-coded.
"""
