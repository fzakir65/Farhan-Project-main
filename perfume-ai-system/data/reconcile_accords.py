"""Bridge dataset1's accord vocabulary (Fragrantica-style terms in Main_Accords: 'woody', 'fresh spicy', 'musky')
to dataset3's named accords (the rule recipes: 'Woody', 'Fresh Spicy', 'Clean Musk').

    python data/reconcile_accords.py        # prints the table, refreshes accord_name_aliases.csv (human rows kept)

Without this bridge a real perfume cannot be turned into a formula: only ~30 of ~250 dataset1 terms are dataset3
accord names verbatim. Tiers, as for the note reconciliation:
  AUTO      exact after normalisation, or the only accord whose name is the term plus a neutral prefix
            (Classic/Generic) or a spice suffix ('cinnamon' -> 'Cinnamon Spice')            -> Apply=Yes
  REVIEW    exactly one accord contains the term as a word, or the term is a dataset3 CATEGORY (several accords)
            -> a recommendation, human decides                                              -> Apply=No
  NO_MATCH  nothing in dataset3 carries the term (tuberose, jasmine, anis…) — an accord must be authored -> Apply=No
Deterministic. No LLM. Rows with Decided_By=human are never overwritten.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
PERFUMES_CSV = HERE / "dataset1_perfumes.csv"
ACCORDS_CSV = HERE / "dataset3_accords.csv"
ALIASES_CSV = HERE / "accord_name_aliases.csv"

NEUTRAL_PREFIXES = ("classic", "generic")
SPICE_TERMS = {"cinnamon", "clove", "nutmeg", "cardamom", "ginger", "pepper", "saffron"}
STOP = {"accord", "and", "the", "of"}


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", str(s or "").casefold())).strip()


def split_terms(cell: str) -> list[str]:
    """Main_Accords is ;-separated, but some cells hide a comma list inside one term."""
    out = []
    for part in re.split(r"[;,]", str(cell or "")):
        p = part.strip()
        if p:
            out.append(p)
    return out


def dataset1_terms(perfumes: pd.DataFrame) -> pd.Series:
    counts: dict[str, int] = {}
    for cell in perfumes["Main_Accords"]:
        for t in split_terms(cell):
            counts[norm(t)] = counts.get(norm(t), 0) + 1
    return pd.Series(counts).sort_values(ascending=False)


def reconcile(perfumes: pd.DataFrame, accords: pd.DataFrame) -> pd.DataFrame:
    names = sorted(set(accords["Accord_Name"].astype(str).str.strip()) - {"nk", ""})
    by_norm = {norm(n): n for n in names}
    cats = accords.groupby("Accord_Category")["Accord_Name"].agg(lambda s: sorted(set(s)))
    cats_by_norm = {norm(c): v for c, v in cats.items() if norm(c)}
    n_notes = accords.groupby("Accord_Name").size()
    rows = []
    for term, count in dataset1_terms(perfumes).items():
        if not term:
            continue
        cands: list[str] = []
        conf, tier, rule, reason, rec = 0.0, "NO_MATCH", "none", "no dataset3 accord carries this term", ""
        if term in by_norm:
            rec, conf, tier, rule, reason = by_norm[term], 1.0, "AUTO", "exact", "same name after case/whitespace normalisation"
        elif term.rstrip("s") in by_norm or term + "s" in by_norm:
            rec = by_norm.get(term.rstrip("s")) or by_norm[term + "s"]
            conf, tier, rule, reason = 0.95, "AUTO", "plural", "singular/plural variant"
        else:
            pref = [by_norm[k] for k in by_norm if any(k == f"{p} {term}" for p in NEUTRAL_PREFIXES)]
            spice = [by_norm[k] for k in by_norm if term in SPICE_TERMS and k == f"{term} spice"]
            word = [by_norm[k] for k in by_norm if term in k.split() and term not in STOP]
            if len(pref) == 1:
                rec, conf, tier, rule, reason = pref[0], 0.9, "AUTO", "neutral_prefix", "the only accord named '<Classic|Generic> term'"
            elif len(spice) == 1:
                rec, conf, tier, rule, reason = spice[0], 0.9, "AUTO", "spice_suffix", "the only accord named 'term Spice'"
            elif len(word) == 1:
                rec, conf, tier, rule, reason, cands = word[0], 0.7, "REVIEW", "single_word_match", "the only accord whose name contains the term", word
            elif len(word) > 1:
                # recommend the accord with the shortest name (closest to the bare term), deterministic
                cands = sorted(word, key=lambda n: (len(n.split()), len(n), n))
                rec, conf, tier, rule, reason = cands[0], 0.6, "REVIEW", "several_word_matches", f"{len(word)} accords contain the term"
            elif term in cats_by_norm:
                cands = cats_by_norm[term]
                rec = sorted(cands, key=lambda n: (-int(n_notes.get(n, 0)), n))[0]
                conf, tier, rule, reason = 0.6, "REVIEW", "category", f"term is a dataset3 Accord_Category with {len(cands)} accords; recommended the one with most notes"
        rows.append({"Dataset1_Term": term, "Dataset3_Accord": rec, "Confidence": f"{conf:.2f}", "Tier": tier, "Rule": rule,
                     "Reason": reason, "Candidates": "; ".join(cands[:8]), "Perfumes_Using": int(count),
                     "Apply": "Yes" if tier == "AUTO" else "No", "Decided_By": "auto", "Note": ""})
    df = pd.DataFrame(rows)
    order = {"AUTO": 0, "REVIEW": 1, "NO_MATCH": 2}
    return df.sort_values(["Tier", "Perfumes_Using", "Dataset1_Term"],
                          key=lambda s: s.map(order) if s.name == "Tier" else (-s if s.name == "Perfumes_Using" else s)).reset_index(drop=True)


def merge_with_existing(fresh: pd.DataFrame, path: Path = ALIASES_CSV) -> pd.DataFrame:
    if not path.exists():
        return fresh
    old = pd.read_csv(path, dtype=str, keep_default_na=False)
    human = old[old["Decided_By"].str.lower().isin(["human", "ai"])]     # decided rows (human or AI) survive re-runs
    keep = fresh[~fresh["Dataset1_Term"].isin(set(human["Dataset1_Term"]))]
    return pd.concat([human[fresh.columns.intersection(human.columns)], keep], ignore_index=True)


def main() -> int:
    perfumes = pd.read_csv(PERFUMES_CSV, dtype=str, keep_default_na=False)
    accords = pd.read_csv(ACCORDS_CSV, dtype=str, keep_default_na=False)
    merged = merge_with_existing(reconcile(perfumes, accords))
    merged.to_csv(ALIASES_CSV, index=False, encoding="utf-8")
    for tier in ("AUTO", "REVIEW", "NO_MATCH"):
        sub = merged[merged["Tier"] == tier]
        print(f"\n### {tier} ({len(sub)} terms, used in {sub['Perfumes_Using'].astype(int).sum()} perfume slots)")
        for r in sub.head(60).itertuples(index=False):
            print(f"  {r.Dataset1_Term:<28} -> {r.Dataset3_Accord or '—':<32} {r.Confidence} {r.Rule:<20} x{r.Perfumes_Using}")
    print(f"\n{len(merged)} terms -> {ALIASES_CSV.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
