# Real-review evaluation of stage12_best.pt (2026-09-18)

- rows: 5078 real Amazon reviews of 50 catalogue perfumes (09_real_reviews_labelled_by_product.csv; weak label = the perfume's accords)
- caveat: the set is skewed (4083 rows are one perfume) — the majority baseline below shows how much
- primary top-1: **0.000**   top-3: **0.002**   (majority-class baseline 0.918)
- prediction anywhere in the perfume's accord set: top-1 0.057, top-3 0.180
- templated split for comparison: val top-1 0.066 / test 0.073; val top-3 0.187 / test 0.203

Reading: the templated numbers are an upper bound (labels leak into the text); this is what the model does on
sentences real people wrote. Retraining with 09_real_reviews_labelled.csv in the train split is the next step
(plan F.5) — keep a held-out slice of these reviews so the gain is measured on real text too.