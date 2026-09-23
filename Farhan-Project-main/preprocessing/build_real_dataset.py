"""Step 1 of training/NEXT_STEPS_ML.md — turn the weakly-labelled reviews into an honest, balanced dataset.

    python preprocessing/build_real_dataset.py                 # writes 10_real_balanced.csv + 10_real_splits.csv

Why: 09_real_reviews_labelled_by_product.csv is 5,078 rows but 80 % of them are ONE perfume, so both training and
evaluation on it are meaningless (a model that always says 'Coach for Men' scores 80 %). Here every perfume is capped
at CAP reviews (longest first — a 60-word review says more than 'love it'), and the split is by PERFUME as well as by
row so the validation set contains perfumes whose reviews the model never saw, which is the real task.

Outputs
  10_real_balanced.csv   review_id, text, perfume_id, perfume, target_accord_id_primary, all_accord_ids, n_words, source
  10_real_splits.csv     review_id, split (train / val_seen / val_unseen)
      val_seen   — held-out reviews of perfumes that are also in train (the easier question)
      val_unseen — every review of perfumes held out entirely (the honest question)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
SRC = OUT / "09_real_reviews_labelled_by_product.csv"
CAP = 60                 # reviews kept per perfume
MIN_WORDS = 6            # 'love it!!' teaches nothing
VAL_SEEN_FRAC = 0.25     # of each perfume's kept reviews
UNSEEN_PERFUMES = 10     # perfumes held out entirely, chosen deterministically
SEED = 20260923


def main() -> int:
    if not SRC.exists():
        print(f"missing {SRC.name} — run preprocessing/label_reviews_by_product.py first")
        return 2
    df = pd.read_csv(SRC, dtype=str, keep_default_na=False)
    df["n_words"] = df["text"].map(lambda t: len(str(t).split()))
    before = len(df)
    df = df[(df["n_words"] >= MIN_WORDS) & (df["target_accord_id_primary"] != "")].copy()
    df = df.drop_duplicates("text")
    # cap per perfume: longest reviews first, ties by review_id so the choice is reproducible
    df = df.sort_values(["perfume", "n_words", "review_id"], ascending=[True, False, True])
    kept = df.groupby("perfume", sort=True).head(CAP).reset_index(drop=True)

    perfumes = sorted(kept["perfume"].unique())
    rng = pd.Series(perfumes).sample(frac=1.0, random_state=SEED).tolist()
    unseen = sorted(rng[:UNSEEN_PERFUMES])
    rows = []
    for perfume, g in kept.groupby("perfume", sort=True):
        g = g.sort_values(["n_words", "review_id"], ascending=[False, True])
        if perfume in unseen:
            for rid in g["review_id"]:
                rows.append({"review_id": rid, "split": "val_unseen"})
            continue
        n_val = max(1, int(round(len(g) * VAL_SEEN_FRAC)))
        for i, rid in enumerate(g["review_id"]):
            rows.append({"review_id": rid, "split": "val_seen" if i < n_val else "train"})
    splits = pd.DataFrame(rows)

    kept[["review_id", "text", "perfume_id", "perfume", "target_accord_id_primary", "target_accord_id_secondary",
          "all_accord_ids", "n_words"]].assign(source="real").to_csv(OUT / "10_real_balanced.csv", index=False, encoding="utf-8")
    splits.to_csv(OUT / "10_real_splits.csv", index=False, encoding="utf-8")

    m = kept.merge(splits, on="review_id")
    print(f"{before} labelled rows -> {len(kept)} balanced ({kept['perfume'].nunique()} perfumes, cap {CAP}, >= {MIN_WORDS} words)")
    print("split sizes:", m["split"].value_counts().to_dict())
    print("perfumes per split:", m.groupby("split")["perfume"].nunique().to_dict())
    print("largest perfume share:", round(100 * kept["perfume"].value_counts().iloc[0] / len(kept), 1), "% (was",
          round(100 * pd.read_csv(SRC, dtype=str, keep_default_na=False)["perfume"].value_counts().iloc[0] / before, 1), "%)")
    print("held out entirely:", ", ".join(unseen))
    return 0


if __name__ == "__main__":
    sys.exit(main())
