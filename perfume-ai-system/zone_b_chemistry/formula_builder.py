"""Task 2 — structural formula builder (NOT YET IMPLEMENTED; skeleton only).

Contract (pure function, no side effects):
    build_formula(accord_rows: pd.DataFrame, notes: pd.DataFrame, *,
                  layer_targets=LAYER_TARGETS) -> pd.DataFrame[Note_ID, Note_Name, CAS, Layer, Pct]

Layer targets follow Jean Carles (CLAUDE.md "Structural pyramid"):
  Top 15-30 % (default 25), Heart/modifiers 15-25 % — never above 25 (default 20),
  Base 45-65 % — always the largest share (default 55).
"""
from __future__ import annotations

LAYER_TARGETS = {          # (min %, default %, max %)
    "Top": (15.0, 25.0, 30.0),
    "Heart": (15.0, 20.0, 25.0),
    "Base": (45.0, 55.0, 65.0),
}

ROLE_WEIGHT = {"Driver": 5, "Support": 3, "Modifier": 1}   # Importance_Weight refines within the role


def build_formula(*args, **kwargs):
    raise NotImplementedError("Task 2 — implement after Task 1 is confirmed (see CLAUDE.md)")
