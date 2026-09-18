"""Second labelling pass: match the PRODUCT TITLE (Amazon metadata) to a catalogue perfume, then label every review
of that product — reviews rarely repeat the perfume's name in their own text.

    python preprocessing/label_reviews_by_product.py     # streams meta_All_Beauty.jsonl (~210 MB), joins on parent_asin

Outputs: 09_real_reviews_labelled_by_product.csv (+ updates 09_real_reviews_report.md)
"""
from __future__ import annotations

import io
import json
import re
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_real_reviews import DATASET1, MASTER, OUT, perfume_patterns  # noqa: E402

META_URL = "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main/raw/meta_categories/meta_All_Beauty.jsonl"


def main() -> int:
    reviews = pd.read_csv(OUT / "09_real_reviews.csv", dtype=str, keep_default_na=False)
    asins = set(reviews["asin"])
    perfumes = pd.read_csv(DATASET1, dtype=str, keep_default_na=False)
    pats = perfume_patterns(perfumes)
    pa = pd.ExcelFile(MASTER).parse("perfume_accord").sort_values(["perfume_id", "accord_rank"])
    acc_of = pa.groupby("perfume_id")["accord_id"].agg(list).to_dict()
    asin_to = {}
    t0 = time.time()
    req = urllib.request.Request(META_URL, headers={"User-Agent": "perfumery-ml research build"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        for n, line in enumerate(io.TextIOWrapper(resp, encoding="utf-8", errors="replace"), 1):
            if n % 50000 == 0:
                print(f"  {n:,} products scanned, {len(asin_to)} matched, {time.time() - t0:.0f}s", flush=True)
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            asin = r.get("parent_asin", "")
            if asin not in asins:
                continue
            title = str(r.get("title", ""))
            for pid, disp, pat in pats:
                if pat.search(title) and acc_of.get(pid):
                    asin_to[asin] = (pid, disp, title[:120])
                    break
    lab = reviews[reviews["asin"].isin(asin_to)].copy()
    lab["perfume_id"] = lab["asin"].map(lambda a: asin_to[a][0])
    lab["perfume"] = lab["asin"].map(lambda a: asin_to[a][1])
    lab["product_title"] = lab["asin"].map(lambda a: asin_to[a][2])
    lab["target_accord_id_primary"] = lab["perfume_id"].map(lambda p: acc_of[p][0])
    lab["target_accord_id_secondary"] = lab["perfume_id"].map(lambda p: acc_of[p][1] if len(acc_of[p]) > 1 else "")
    lab["all_accord_ids"] = lab["perfume_id"].map(lambda p: "|".join(acc_of[p]))
    lab.to_csv(OUT / "09_real_reviews_labelled_by_product.csv", index=False, encoding="utf-8")
    hits = Counter(lab["perfume"])
    lines = ["", f"## Product-title labelling ({time.strftime('%Y-%m-%d')})", "",
             f"- {len(asin_to)} products (ASINs) whose title names a catalogue perfume; {len(lab):,} of their reviews labelled",
             f"- {len(hits)} distinct perfumes; top: " + ", ".join(f"{k} ({v})" for k, v in hits.most_common(15)),
             "- file: 09_real_reviews_labelled_by_product.csv (weak label = the perfume on the product page)"]
    with open(OUT / "09_real_reviews_report.md", "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
