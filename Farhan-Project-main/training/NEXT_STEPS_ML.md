# ML next steps (written 2026-09-18, after the real-review evaluation)

## What we now know
- `training/REAL_REVIEWS_EVAL.md`: the Stage 1+2 checkpoint scores ~0 % top-1 on real customer sentences
  (5,078 Amazon reviews of 50 catalogue perfumes) vs 7 % on the templated split. The templated number was an artefact.
- `preprocessing/outputs/09_real_reviews.csv` (65,698 real fragrance reviews, unlabelled) is the real-language asset;
  `09_real_reviews_labelled_by_product.csv` (5,078 rows, 50 perfumes, 80 % one perfume) is weakly labelled.

## Do, in order
1. **Balance** the labelled set: cap each perfume at ~60 reviews (-> ~600 rows, 50 perfumes), hold out 30 % as the
   REAL validation set. Never let the templated split be the only validation again.
2. **Domain-adapt the encoder** on the 65k unlabelled reviews (masked-LM continued pre-training of MiniLM, 1 epoch,
   ~1 h CPU) so the backbone has seen how people actually describe scent.
3. **Extend preprocessing** (plan F.5) so free-text rows get descriptor columns from the synonym table, then add the
   balanced real rows to the train split with a `source=real` flag and 3x sample weight.
4. Retrain Stage 1+2 via Task Scheduler (`training/run_detached.py`; the laptop sleeps — never Bash background).
   Report BOTH validations. Then Stage 3/4.
5. Ask real people for the N=200 prompt set (plan L.7) — the reviews are about existing products; prompts describe wishes.

Also worth knowing: perfume-ai-system's Zone A already uses the catalogue vocabulary deterministically, so the app works
without this model; the model is the offline free-text matcher and only improves the *match*, never the formula.
