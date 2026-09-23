"""Zone A — append every free-text interpretation to data/logs/input_log.csv.

    text | keyword terms | lexicon terms | llm terms | final terms | avoid | strength | source | unmatched words | timestamp

Why: the log is the review queue for the lexicon (data/review_input_log.py turns unmatched words and LLM additions into
candidate rows a human promotes) and, once labelled, the training set the future model learns real customer language
from. Nothing personal is stored beyond the sentence typed. The file is gitignored; the folder keeps a README.
"""
from __future__ import annotations

import csv
import datetime as _dt
from pathlib import Path

COLS = ["Timestamp", "Text", "Keyword_Terms", "Lexicon_Terms", "LLM_Terms", "Final_Terms", "Avoid", "Strength", "Source", "Unmatched"]


def log_path() -> Path:
    from load_data import DATA_DIR
    return Path(DATA_DIR) / "logs" / "input_log.csv"


def append(text: str, kw, base, llm_terms: list[str], result) -> None:
    p = log_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    new = not p.exists()
    unmatched = ""
    for n in result.notes:
        if n.startswith("unmatched words: "):
            unmatched = n[len("unmatched words: "):]
    with open(p, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        if new:
            w.writeheader()
        w.writerow({"Timestamp": _dt.datetime.now().isoformat(timespec="seconds"), "Text": text.strip(),
                    "Keyword_Terms": "|".join(kw.accords), "Lexicon_Terms": "|".join(t for t in base.accords if t not in kw.accords),
                    "LLM_Terms": "|".join(llm_terms), "Final_Terms": "|".join(result.accords), "Avoid": "|".join(result.avoid),
                    "Strength": result.strength if result.strength is not None else "", "Source": result.source, "Unmatched": unmatched})


__all__ = ["append", "log_path", "COLS"]
