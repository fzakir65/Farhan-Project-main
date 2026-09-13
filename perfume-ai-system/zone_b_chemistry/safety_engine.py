"""Task 3 — safety engine (NOT YET IMPLEMENTED; skeleton only).

Order of checks, every one a deterministic CSV lookup by CAS (any CAS in All_CAS):
  1. regulatory_uk.csv   BANNED (GB or EU) -> REJECT; RESTRICTED -> cap  (overrides IFRA)
  2. ifra_limits.csv     Restriction -> cap at Category_4_Limit / CONCENTRATE_FRACTION
                         Prohibition -> REJECT
                         Specification -> FLAG (CoA requirement)
                         combined types: prohibited grade unknown -> REJECT
  3. group_rules.csv     furocoumarin_ncs sum-of-fractions <= 1.0 (the 8 oils ONLY);
                         isomer sums; MHC+MOC; oakmoss+treemoss; PAH group -> FLAG
  4. safety_caps.csv     cap at Max_Safe_Percent (Grade_Note may require rectified grade)
  5. reaction_rules.csv  flag / sum / reduce
  6. constituents.csv    natural-oil contributions (TODO — table not yet available)

Every adjustment is logged with its source row. If the formula cannot be made safe -> REJECT.
"""
from __future__ import annotations

# IFRA MACs apply to the finished product. We treat the formula as the finished product
# (neat, Category 4). Zone C may later set the true concentrate fraction (0 < f <= 1);
# effective caps become limit / CONCENTRATE_FRACTION. Never set above 1.0, never LLM-supplied.
CONCENTRATE_FRACTION = 1.0

IFRA_CATEGORY = "Category_4_Limit"     # fine fragrance; body spray -> Category 2, hair mist -> min(4, 7B)


def check_formula(*args, **kwargs):
    raise NotImplementedError("Task 3 — implement after Task 2 is confirmed (see CLAUDE.md)")
