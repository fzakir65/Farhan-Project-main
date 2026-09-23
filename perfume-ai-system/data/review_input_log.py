"""The lexicon review loop: turn the input log into candidate lexicon rows, and promote the ones a human approved.

    python data/review_input_log.py              # -> data/lexicon_candidates.csv (words nothing matched, LLM additions)
    python data/review_input_log.py --promote    # rows with Apply=Yes in lexicon_candidates.csv -> user_lexicon.csv

Candidates come from two places in data/logs/input_log.csv: (1) 'Unmatched' words — what customers typed that neither the
catalogue vocabulary nor the lexicon recognised, ranked by how often they occur; (2) LLM additions — terms the LLM added
for a sentence, offered as a phrase -> terms row so the deterministic path learns them and the LLM is needed less next time.
A human fills Accord_Terms (or accepts the LLM's) and sets Apply=Yes; --promote appends them with Source='input log'.
"""
from __future__ import annotations

import collections
import csv
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
LOG = HERE / "logs" / "input_log.csv"
CAND = HERE / "lexicon_candidates.csv"
LEX = HERE / "user_lexicon.csv"
COLS = ["Phrase", "Suggested_Terms", "Accord_Terms", "Seen", "Example", "Origin", "Apply", "Decided_By"]


def build_candidates() -> int:
    if not LOG.exists():
        print("no input log yet (data/logs/input_log.csv)"); return 0
    log = pd.read_csv(LOG, dtype=str, keep_default_na=False)
    lex = pd.read_csv(LEX, dtype=str, keep_default_na=False) if LEX.exists() else pd.DataFrame(columns=["Phrase"])
    known = set(lex["Phrase"].str.casefold())
    old = pd.read_csv(CAND, dtype=str, keep_default_na=False) if CAND.exists() else pd.DataFrame(columns=COLS)
    decided = {r.Phrase: r for r in old.itertuples() if r.Apply.strip().lower() in ("yes", "no")}
    seen: collections.Counter = collections.Counter(); example: dict[str, str] = {}; suggested: dict[str, str] = {}; origin: dict[str, str] = {}
    for r in log.itertuples():
        for w in [x.strip() for x in str(r.Unmatched).split(",") if x.strip()]:
            if w in known:
                continue
            seen[w] += 1; example.setdefault(w, r.Text[:120]); origin.setdefault(w, "unmatched word")
        if r.LLM_Terms:
            key = r.Text.strip().casefold()[:80]
            if key not in known:
                seen[key] += 1; example.setdefault(key, r.Text[:120]); suggested[key] = r.LLM_Terms.replace("|", ":0.7;") + ":0.7"; origin[key] = "LLM addition"
    rows = []
    for phrase, n in seen.most_common():
        if phrase in decided:
            d = decided[phrase]
            rows.append({c: getattr(d, c) for c in COLS} | {"Seen": n})
        else:
            rows.append({"Phrase": phrase, "Suggested_Terms": suggested.get(phrase, ""), "Accord_Terms": "", "Seen": n, "Example": example[phrase],
                         "Origin": origin[phrase], "Apply": "", "Decided_By": ""})
    with open(CAND, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS); w.writeheader(); w.writerows(rows)
    print(f"{len(rows)} candidates -> {CAND.name} ({sum(1 for r in rows if not r['Apply'])} undecided)")
    return 0


def promote() -> int:
    if not CAND.exists():
        print("no candidates file"); return 0
    cand = pd.read_csv(CAND, dtype=str, keep_default_na=False)
    lex = pd.read_csv(LEX, dtype=str, keep_default_na=False)
    known = set(lex["Phrase"].str.casefold())
    sys.path.insert(0, str(HERE.parent))
    from load_data import load_all
    from zone_a_llm.input_handler import vocabulary
    terms = set(vocabulary(load_all())["accords"])
    added = []
    for r in cand.itertuples():
        if r.Apply.strip().lower() != "yes" or r.Phrase in known:
            continue
        spec = r.Accord_Terms or r.Suggested_Terms
        pairs = [x for x in spec.split(";") if ":" in x]
        bad = [x for x in pairs if x.rsplit(":", 1)[0] not in terms]
        if not pairs or bad:
            print(f"skip {r.Phrase!r}: terms missing or unknown {bad}"); continue
        added.append({"Phrase": r.Phrase, "Accord_Terms": ";".join(pairs), "Family": "", "Gender": "", "Season": "", "Strength": "", "Kind": "input log",
                      "Source": f"input log — seen {r.Seen}x, e.g. '{r.Example}'", "Decided_By": r.Decided_By or "human", "Apply": "Yes"})
    if added:
        pd.concat([lex, pd.DataFrame(added)], ignore_index=True).to_csv(LEX, index=False)
    print(f"{len(added)} rows promoted into {LEX.name}")
    return 0


if __name__ == "__main__":
    sys.exit(promote() if "--promote" in sys.argv else build_candidates())
