"""Real customer language for the perfumery ML project.

    python preprocessing/build_real_reviews.py            # streams Amazon Reviews 2023 (All_Beauty), ~330 MB, no local copy kept

Source: McAuley-Lab / Amazon-Reviews-2023 (Hugging Face; Hou et al. 2024) — a research dataset, used under its
research terms. NOT scraped from Fragrantica/Basenotes (their ToS forbid it).

Outputs (preprocessing/outputs/):
  09_real_reviews.csv           every review that talks about a fragrance (unlabelled real language)
  09_real_reviews_labelled.csv  the subset that names a catalogue perfume (dataset1), weak-labelled with that perfume's
                                accord ids from the master workbook's perfume_accord sheet (primary = position 1)
  09_real_reviews_report.md     counts + the top matched perfumes

Why weak labels are honest here: the label is not guessed from the text — it is the catalogue's own accord list for a
perfume the customer explicitly named. The text is real; the label is real; only the link (name mention) is heuristic.
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "preprocessing" / "outputs"
MASTER = ROOT / "perfume_system_master_training_dynamic_v5_augmented.xlsx"
DATASET1 = ROOT.parent / "perfume-ai-system" / "data" / "dataset1_perfumes.csv"
URL = "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main/raw/review_categories/All_Beauty.jsonl"

FRAG = re.compile(r"\b(perfume|fragrance|cologne|eau de (?:parfum|toilette|cologne)|edp|edt|scent(?:ed)?|smell(?:s|ed)?|sillage|longevity|projection|top notes?|base notes?|dry ?down)\b", re.I)
CONC = re.compile(r"\b(edp|edt|extrait|eau de parfum|eau de toilette|parfum|cologne|intense|elixir)\b", re.I)
MIN_WORDS = 8


def perfume_patterns(perfumes: pd.DataFrame) -> list[tuple[str, str, re.Pattern]]:
    """(perfume_id, display, regex) — the perfume name without concentration words; needs >= 2 significant words
    or a brand + name so that 'Rose' alone never matches."""
    pats = []
    for r in perfumes.itertuples(index=False):
        name = CONC.sub("", str(r.Perfume_Name)).strip()
        brand = str(r.Brand).strip()
        core = name
        if core.lower().startswith(brand.lower()):
            core = core[len(brand):].strip(" -–:")
        words = [w for w in re.findall(r"[A-Za-z0-9']+", core) if len(w) > 1]
        if len(words) >= 2:
            pat = r"\b" + r"\s+".join(re.escape(w) for w in words) + r"\b"
        elif len(words) == 1 and len(words[0]) >= 5:
            pat = r"\b" + re.escape(brand) + r"\W+" + re.escape(words[0]) + r"\b"      # brand + single name
        else:
            continue
        pats.append((str(r.Perfume_ID), f"{brand} {core}".strip(), re.compile(pat, re.I)))
    return pats


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    perfumes = pd.read_csv(DATASET1, dtype=str, keep_default_na=False)
    pats = perfume_patterns(perfumes)
    m = pd.ExcelFile(MASTER)
    pa = m.parse("perfume_accord")
    pa_cols = [c for c in pa.columns]
    # perfume_id -> ordered accord ids (position column if present)
    order_col = next((c for c in pa_cols if "position" in c.lower() or "rank" in c.lower() or "order" in c.lower()), None)
    if order_col:
        pa = pa.sort_values(["perfume_id", order_col])
    acc_of = pa.groupby("perfume_id")["accord_id"].agg(list).to_dict()
    print(f"{len(pats)} perfume name patterns; {len(acc_of)} perfumes with accord ids in the master workbook")

    kept, labelled = [], []
    hits = Counter()
    t0 = time.time()
    req = urllib.request.Request(URL, headers={"User-Agent": "perfumery-ml research build"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        stream = io.TextIOWrapper(resp, encoding="utf-8", errors="replace")
        for n, line in enumerate(stream, 1):
            if n % 100000 == 0:
                print(f"  {n:,} reviews scanned, {len(kept):,} fragrance, {len(labelled):,} labelled, {time.time() - t0:.0f}s")
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            text = (str(r.get("title", "")) + ". " + str(r.get("text", ""))).strip()
            if len(text.split()) < MIN_WORDS or not FRAG.search(text):
                continue
            row = {"review_id": n, "asin": r.get("parent_asin") or r.get("asin", ""), "rating": r.get("rating", ""), "text": text[:2000]}
            kept.append(row)
            for pid, disp, pat in pats:
                if pat.search(text):
                    accs = acc_of.get(pid, [])
                    if accs:
                        hits[disp] += 1
                        labelled.append({**row, "perfume_id": pid, "perfume": disp, "target_accord_id_primary": accs[0],
                                         "target_accord_id_secondary": accs[1] if len(accs) > 1 else "", "all_accord_ids": "|".join(map(str, accs))})
                    break
    pd.DataFrame(kept).to_csv(OUT / "09_real_reviews.csv", index=False, encoding="utf-8")
    pd.DataFrame(labelled).to_csv(OUT / "09_real_reviews_labelled.csv", index=False, encoding="utf-8")
    report = [f"# Real reviews build ({time.strftime('%Y-%m-%d')})", "",
              f"- scanned {n:,} All_Beauty reviews in {time.time() - t0:.0f} s (streamed, nothing stored locally but the outputs)",
              f"- {len(kept):,} fragrance-related reviews (>= {MIN_WORDS} words, fragrance vocabulary present) -> 09_real_reviews.csv",
              f"- {len(labelled):,} name a catalogue perfume -> 09_real_reviews_labelled.csv (weak label = that perfume's accords)",
              f"- {len(hits)} distinct catalogue perfumes matched; top: " + ", ".join(f"{k} ({v})" for k, v in hits.most_common(15)), "",
              "Use: (1) realism check of the Stage 1+2 model on real language (evaluate_on_real_reviews.py); (2) extra training rows",
              "once the preprocessing pipeline is extended to derive descriptors for free text (plan F.5)."]
    (OUT / "09_real_reviews_report.md").write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
