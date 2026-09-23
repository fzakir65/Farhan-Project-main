"""The number that decides whether a retrain is worth it: how well does the DETERMINISTIC Zone A path
(perfume-ai-system's user_lexicon.csv + matcher) do on the same real reviews the model scored ~0 % on?

    python training/evaluate_lexicon_baseline.py        # needs preprocessing/outputs/10_real_balanced.csv

Task (identical to training/evaluate_on_real_reviews.py): given a real customer sentence, predict the perfume's primary
accord. Compared against the majority-class baseline and the model's published numbers. Writes LEXICON_BASELINE.md.

Note on fairness: the reviews describe a product the customer already owns, while the lexicon was built to read a wish.
Both systems face that gap equally, so the comparison is fair even though neither number is the app's real accuracy.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PREP = ROOT / "preprocessing" / "outputs"
ENGINE = ROOT.parent / "perfume-ai-system"
REPORT = HERE / "LEXICON_BASELINE.md"


def main() -> int:
    src = PREP / "10_real_balanced.csv"
    if not src.exists():
        print("run preprocessing/build_real_dataset.py first")
        return 2
    sys.path.insert(0, str(ENGINE))
    from load_data import load_all                      # noqa: E402
    from zone_a_llm.input_handler import interpret      # noqa: E402
    from zone_a_llm.matcher import shortlist            # noqa: E402

    df = pd.read_csv(src, dtype=str, keep_default_na=False)
    splits = pd.read_csv(PREP / "10_real_splits.csv", dtype=str, keep_default_na=False)
    df = df.merge(splits, on="review_id")
    data = load_all()
    acc = pd.read_csv(ENGINE / "data" / "dataset3_accords.csv", dtype=str, keep_default_na=False)
    id2name = dict(zip(acc["Accord_ID"], acc["Accord_Name"]))
    alias = pd.read_csv(ENGINE / "data" / "accord_name_aliases.csv", dtype=str, keep_default_na=False)
    alias = alias[alias["Apply"] == "Yes"]
    acc2term: dict[str, str] = {}
    for r in alias.itertuples():
        acc2term.setdefault(r.Dataset3_Accord, r.Dataset1_Term)

    def target_terms(row) -> tuple[str, set[str]]:
        prim = acc2term.get(id2name.get(row["target_accord_id_primary"], ""), "")
        allt = {acc2term.get(id2name.get(a, ""), "") for a in row["all_accord_ids"].split("|")} - {""}
        return prim, allt

    rows = []
    for r in df.itertuples():
        row = {"review_id": r.review_id, "split": r.split, "perfume": r.perfume}
        prim, allt = target_terms({"target_accord_id_primary": r.target_accord_id_primary, "all_accord_ids": r.all_accord_ids})
        p = interpret(r.text, data, log=False)
        pred = p.accords
        row["n_pred"] = len(pred)
        row["primary_ok"] = bool(prim) and bool(pred) and pred[0] == prim
        row["primary_top3"] = bool(prim) and prim in pred[:3]
        row["any_ok"] = bool(pred) and pred[0] in allt
        row["any_top3"] = bool(allt & set(pred[:3]))
        row["covered"] = bool(pred)
        # the perfume-level question the app actually answers: is the right perfume in the top 5 the matcher returns?
        if pred:
            ms = shortlist(p, data, top_k=5)
            row["perfume_top1"] = bool(ms) and ms[0].perfume_id == r.perfume_id
            row["perfume_top5"] = any(m.perfume_id == r.perfume_id for m in ms)
        else:
            row["perfume_top1"] = row["perfume_top5"] = False
        rows.append(row)
    res = pd.DataFrame(rows)

    prim_terms = [acc2term.get(id2name.get(a, ""), "") for a in df["target_accord_id_primary"]]
    maj = pd.Series([t for t in prim_terms if t]).value_counts()
    maj_rate = float(maj.iloc[0] / max(1, len(prim_terms)))

    tmpl = json.load(open(HERE / "outputs" / "metrics.json", encoding="utf-8")) if (HERE / "outputs" / "metrics.json").exists() else {}
    tv = tmpl.get("model", {}).get("val", {})

    def block(sub: pd.DataFrame, name: str) -> str:
        if not len(sub):
            return f"- **{name}**: no rows\n"
        return (f"- **{name}** ({len(sub)} reviews, {sub['perfume'].nunique()} perfumes): "
                f"accord top-1 **{sub['primary_ok'].mean():.3f}**, top-3 {sub['primary_top3'].mean():.3f}; "
                f"any of the perfume's accords top-1 {sub['any_ok'].mean():.3f}, top-3 {sub['any_top3'].mean():.3f}; "
                f"perfume top-1 {sub['perfume_top1'].mean():.3f}, top-5 {sub['perfume_top5'].mean():.3f}; "
                f"read something in {sub['covered'].mean():.3f} of reviews\n")

    lines = [f"# Deterministic lexicon baseline on real reviews ({pd.Timestamp.today().date()})", "",
             f"Zone A's `user_lexicon.csv` + matcher, no model and no LLM, on `10_real_balanced.csv` "
             f"({len(df)} reviews, {df['perfume'].nunique()} perfumes, largest {100 * df['perfume'].value_counts().iloc[0] / len(df):.0f} %).", ""]
    for split in ("train", "val_seen", "val_unseen"):
        lines.append(block(res[res["split"] == split], split))
    lines.append(block(res, "all rows"))
    lines += ["", f"- majority-class accord baseline on the same rows: {maj_rate:.3f} (most common: {maj.index[0]!r})",
              f"- Stage 1+2 model, for comparison: ~0.00 top-1 on real reviews (training/REAL_REVIEWS_EVAL.md); "
              f"{tv.get('primary_top1', float('nan')):.3f} on its own templated split", "",
              "Reading: the lexicon reads a sentence with no training at all. A retrain is only worth it if the model can beat",
              "these numbers on `val_unseen` — reviews of perfumes it never saw. Note both systems are judged on text that",
              "describes an owned product, not a wish, so neither figure is the app's real accuracy; it is a like-for-like race."]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    res.to_csv(HERE / "outputs" / "lexicon_baseline_rows.csv", index=False) if (HERE / "outputs").exists() else None
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
