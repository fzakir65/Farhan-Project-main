"""Measure the real-world gap: the Stage 1+2 checkpoint scored on REAL customer sentences with REAL labels.

    python training/evaluate_on_real_reviews.py          # needs preprocessing/outputs/09_real_reviews_labelled.csv

Text-only inference: demographics, occasion and descriptor inputs are unknown for a review, so they take the
out-of-vocabulary slot / zero vectors the model was built with. Reports top-1 / top-3 on the primary accord and
compares with the templated val/test numbers in training/outputs/metrics.json. Writes training/REAL_REVIEWS_EVAL.md.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_stage12 as rs  # noqa: E402  (model class, config, paths)

LABELLED = rs.PREP_OUT / "09_real_reviews_labelled.csv"
CKPT = rs.CKPT_DIR / "stage12_best.pt"
REPORT = HERE / "REAL_REVIEWS_EVAL.md"


def main() -> int:
    if not LABELLED.exists():
        print("run preprocessing/build_real_reviews.py first"); return 2
    df = pd.read_csv(LABELLED, dtype=str, keep_default_na=False)
    ck = torch.load(CKPT, weights_only=False, map_location="cpu")
    accord_ids, categories = ck["accord_ids"], ck["categories"]
    with open(rs.PREP_OUT / "07_input_vocab.json", encoding="utf-8") as f:
        vocab = json.load(f)
    from transformers import AutoModel, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(rs.BACKBONE)
    model = rs.Stage12Model(AutoModel.from_pretrained(rs.BACKBONE), vocab, len(accord_ids), len(categories))
    model.load_state_dict(ck["state_dict"])
    model.eval()
    aidx = {a: i for i, a in enumerate(accord_ids)}
    df = df[df["target_accord_id_primary"].isin(aidx)]
    y = np.array([aidx[a] for a in df["target_accord_id_primary"]])
    n = len(df)
    print(f"{n} labelled real reviews; label space {len(accord_ids)}")
    oov = {k: len(vocab[k]) for k in ("age_bucket_order", "gender", "region", "background_tag", "occasion_tag")}
    preds = []
    with torch.no_grad():
        for s in range(0, n, 64):
            texts = df["text"].iloc[s:s + 64].tolist()
            enc = tok(texts, padding="max_length", truncation=True, max_length=rs.MAX_LEN, return_tensors="pt")
            b = len(texts)
            batch = {"input_ids": enc["input_ids"], "attention_mask": enc["attention_mask"],
                     "age": torch.full((b,), oov["age_bucket_order"]), "gender": torch.full((b,), oov["gender"]),
                     "region": torch.full((b,), oov["region"]), "background": torch.full((b,), oov["background_tag"]),
                     "occasion": torch.full((b,), oov["occasion_tag"]),
                     "desc": torch.zeros((b, len(vocab["descriptors"]))), "avoid": torch.zeros((b, len(vocab["avoid_tokens"])))}
            out = model(batch)
            preds.append(out["primary_logits"].numpy())
    P = np.concatenate(preds)
    rank = np.argsort(-P, axis=1)
    top1 = float((rank[:, 0] == y).mean())
    top3 = float(np.any(rank[:, :3] == y[:, None], axis=1).mean())
    # any-accord hit: prediction in the perfume's full accord list (weak labels are a set, not one truth)
    sets = [set(x.split("|")) for x in df["all_accord_ids"]]
    any1 = float(np.mean([accord_ids[rank[i, 0]] in sets[i] for i in range(n)]))
    any3 = float(np.mean([any(accord_ids[rank[i, k]] in sets[i] for k in range(3)) for i in range(n)]))
    # majority-class baseline on the same rows
    maj = pd.Series(y).value_counts().iloc[0] / n
    tmpl = json.load(open(rs.OUT_DIR / "metrics.json", encoding="utf-8")) if (rs.OUT_DIR / "metrics.json").exists() else {}
    tv = tmpl.get("model", {}).get("val", {}); tt = tmpl.get("model", {}).get("test", {})
    lines = [f"# Real-review evaluation of stage12_best.pt ({pd.Timestamp.today().date()})", "",
             f"- rows: {n} real Amazon reviews naming a catalogue perfume (weak label = that perfume's accords)",
             f"- primary top-1: **{top1:.3f}**   top-3: **{top3:.3f}**   (majority-class baseline {maj:.3f})",
             f"- prediction anywhere in the perfume's accord set: top-1 {any1:.3f}, top-3 {any3:.3f}",
             f"- templated split for comparison: val top-1 {tv.get('primary_top1', float('nan')):.3f} / test {tt.get('primary_top1', float('nan')):.3f}; "
             f"val top-3 {tv.get('primary_top3', float('nan')):.3f} / test {tt.get('primary_top3', float('nan')):.3f}", "",
             "Reading: the templated numbers are an upper bound (labels leak into the text); this is what the model does on",
             "sentences real people wrote. Retraining with 09_real_reviews_labelled.csv in the train split is the next step",
             "(plan F.5) — keep a held-out slice of these reviews so the gain is measured on real text too."]
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
