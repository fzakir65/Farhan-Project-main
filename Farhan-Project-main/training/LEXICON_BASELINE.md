# Deterministic lexicon baseline on real reviews (2026-09-23)

Zone A's `user_lexicon.csv` + matcher, no model and no LLM, on `10_real_balanced.csv` (460 reviews, 50 perfumes, largest 13 %).

- **train** (304 reviews, 26 perfumes): accord top-1 **0.020**, top-3 0.046; any of the perfume's accords top-1 0.062, top-3 0.155; perfume top-1 0.003, top-5 0.043; read something in 0.609 of reviews

- **val_seen** (122 reviews, 40 perfumes): accord top-1 **0.000**, top-3 0.033; any of the perfume's accords top-1 0.033, top-3 0.189; perfume top-1 0.008, top-5 0.041; read something in 0.705 of reviews

- **val_unseen** (34 reviews, 10 perfumes): accord top-1 **0.000**, top-3 0.000; any of the perfume's accords top-1 0.000, top-3 0.000; perfume top-1 0.000, top-5 0.029; read something in 0.118 of reviews

- **all rows** (460 reviews, 50 perfumes): accord top-1 **0.013**, top-3 0.039; any of the perfume's accords top-1 0.050, top-3 0.152; perfume top-1 0.004, top-5 0.041; read something in 0.598 of reviews


- majority-class accord baseline on the same rows: 0.335 (most common: 'citrus')
- Stage 1+2 model, for comparison: ~0.00 top-1 on real reviews (training/REAL_REVIEWS_EVAL.md); 0.066 on its own templated split

Reading: the lexicon reads a sentence with no training at all. A retrain is only worth it if the model can beat
these numbers on `val_unseen` — reviews of perfumes it never saw. Note both systems are judged on text that
describes an owned product, not a wish, so neither figure is the app's real accuracy; it is a like-for-like race.