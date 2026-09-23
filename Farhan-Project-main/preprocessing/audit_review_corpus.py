"""Audit the real-review corpus before anyone trains on it -> preprocessing/outputs/11_corpus_audit.md

    python preprocessing/audit_review_corpus.py

The 5,078 'labelled' reviews were labelled by the PRODUCT PAGE, not by what the review says. This measures how often
that label is actually supported by the text, using Zone A's lexicon as a scent-language detector:

  scent_words   how many accord terms the lexicon reads in the review
  off_topic     the review is about a different product category (mask, cream, shampoo, razor...) — the ASIN matched a
                bundle or the brand's skincare line, not the fragrance
  no_label      the perfume's accord does not map to a catalogue term at all (the bridge does not cover it)
  agrees        the lexicon's reading overlaps the perfume's own accord list

A review is TRAINABLE only if it is on-topic, carries at least MIN_SCENT accord terms and has a label. The output says
how many of those exist, and that number decides whether a retrain is possible at all.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
ENGINE = HERE.parent.parent / "perfume-ai-system"
MIN_SCENT = 2
OFF_TOPIC = re.compile(r"\b(mask|masks|face ?mask|moisturi[sz]|serum|cream|lotion|shampoo|conditioner|razor|blade|shave gel|"
                       r"toothpaste|deodorant stick|wipes|acne|wrinkle|hyaluronic|spf|sunscreen|makeup remover|foundation|"
                       r"concealer|mascara|lipstick|nail|shower gel|body wash|soap bar|candle|diffuser|pillow)\b", re.I)
FRAG_WORDS = re.compile(r"\b(perfume|fragrance|cologne|scent|smell|eau de|edt|edp|parfum|toilette|sillage|projection|notes?)\b", re.I)


def main() -> int:
    src = OUT / "09_real_reviews_labelled_by_product.csv"
    if not src.exists():
        print("run preprocessing/label_reviews_by_product.py first")
        return 2
    sys.path.insert(0, str(ENGINE))
    from load_data import load_all                  # noqa: E402
    from zone_a_llm.lexicon import Lexicon          # noqa: E402

    df = pd.read_csv(src, dtype=str, keep_default_na=False)
    data = load_all()
    lx = Lexicon.load()
    acc = pd.read_csv(ENGINE / "data" / "dataset3_accords.csv", dtype=str, keep_default_na=False)
    id2name = dict(zip(acc["Accord_ID"], acc["Accord_Name"]))
    al = pd.read_csv(ENGINE / "data" / "accord_name_aliases.csv", dtype=str, keep_default_na=False)
    al = al[al["Apply"] == "Yes"]
    a2t: dict[str, str] = {}
    for r in al.itertuples():
        a2t.setdefault(r.Dataset3_Accord, r.Dataset1_Term)

    rows = []
    for r in df.itertuples():
        hit = lx.apply(r.text)
        read = set(hit.weights)
        prim = a2t.get(id2name.get(r.target_accord_id_primary, ""), "")
        allt = {a2t.get(id2name.get(a, ""), "") for a in r.all_accord_ids.split("|")} - {""}
        rows.append({"review_id": r.review_id, "perfume": r.perfume, "n_words": len(r.text.split()),
                     "scent_words": len(read), "off_topic": bool(OFF_TOPIC.search(r.text)) and not bool(FRAG_WORDS.search(r.text)),
                     "mentions_fragrance": bool(FRAG_WORDS.search(r.text)), "no_label": not bool(prim),
                     "agrees_primary": bool(prim) and prim in read, "agrees_any": bool(read & allt),
                     "read": "|".join(sorted(read)), "label_primary": prim, "label_all": "|".join(sorted(allt))})
    a = pd.DataFrame(rows)
    a["trainable"] = (~a["off_topic"]) & (~a["no_label"]) & (a["scent_words"] >= MIN_SCENT)
    a.to_csv(OUT / "11_corpus_audit.csv", index=False, encoding="utf-8")

    n = len(a)
    tr = a[a["trainable"]]
    lines = [f"# Real-review corpus audit ({pd.Timestamp.today().date()})", "",
             f"Source: `09_real_reviews_labelled_by_product.csv` — {n:,} reviews of {a['perfume'].nunique()} catalogue perfumes, "
             f"weak-labelled by the product page.", "",
             "## Is the label supported by the text?", "",
             f"- reviews that mention fragrance at all: **{a['mentions_fragrance'].mean():.1%}**",
             f"- reviews about a different product category (mask, cream, shampoo…): **{a['off_topic'].mean():.1%}**",
             f"- reviews whose perfume has no catalogue accord term (bridge gap): **{a['no_label'].mean():.1%}**",
             f"- reviews where the lexicon reads no scent word at all: **{(a['scent_words'] == 0).mean():.1%}**; "
             f"1 word: {(a['scent_words'] == 1).mean():.1%}; {MIN_SCENT}+: {(a['scent_words'] >= MIN_SCENT).mean():.1%}",
             f"- text agrees with the labelled PRIMARY accord: **{a['agrees_primary'].mean():.1%}**; "
             f"with ANY of the perfume's accords: **{a['agrees_any'].mean():.1%}**", "",
             "Among the reviews that do describe a scent (>= 2 accord words):", "",
             f"- agreement with the primary accord: **{a.loc[a['scent_words'] >= MIN_SCENT, 'agrees_primary'].mean():.1%}**, "
             f"with any accord: **{a.loc[a['scent_words'] >= MIN_SCENT, 'agrees_any'].mean():.1%}**", "",
             "## Trainable rows", "",
             f"- on-topic + labelled + >= {MIN_SCENT} scent words: **{len(tr):,} of {n:,} ({len(tr) / n:.1%})**, "
             f"covering {tr['perfume'].nunique()} perfumes",
             f"- largest perfume's share of those: {100 * tr['perfume'].value_counts().iloc[0] / max(1, len(tr)):.0f} %", "",
             "## What this means", "",
             "The label says what the product page sells; the text says what the customer felt like writing. Those are different",
             "things, and the numbers above are the size of the gap. A model trained on this pairing learns the gap, not the",
             "language — which is exactly what the ~0 % real-world score of the Stage 1+2 checkpoint showed.", "",
             "Per-perfume trainable counts:", "", "| perfume | trainable | total |", "|---|---|---|"]
    tot = a["perfume"].value_counts()
    for p, c in tr["perfume"].value_counts().head(20).items():
        lines.append(f"| {p} | {c} | {tot[p]} |")
    (OUT / "11_corpus_audit.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:30]))
    print(f"\n-> {(OUT / '11_corpus_audit.md').name} and 11_corpus_audit.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
