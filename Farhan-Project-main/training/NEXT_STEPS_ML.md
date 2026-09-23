# ML next steps — revised 2026-09-23 after auditing the corpus

## The finding that changes the plan

The 2026-09-18 plan assumed the real-review corpus only needed **balancing**. It needs more than that: the labels are
not supported by the text. Measured, not guessed (`preprocessing/audit_review_corpus.py` → `outputs/11_corpus_audit.md`,
5,078 reviews of 50 catalogue perfumes):

| question | answer |
|---|---|
| reviews that mention fragrance at all | 78.4 % |
| reviews about a different product entirely (mask, cream, shampoo…) | 3.8 % |
| reviews where no scent word can be read at all | 43.8 % |
| text agrees with the labelled **primary** accord | **5.4 %** |
| text agrees with **any** of the perfume's accords | 22.6 % |
| …among reviews that do describe a scent (≥ 2 accord words) | **46.5 %** |
| on-topic + labelled + ≥ 2 scent words | 2,113 rows — but **83 % of them are one perfume** |

Balanced honestly (`preprocessing/build_real_dataset.py`, cap 60/perfume, ≥ 6 words, perfumes held out entirely):
**460 rows, 50 perfumes — 304 train / 122 val_seen / 34 val_unseen.**

Two independent readers score the same on this task (`training/evaluate_lexicon_baseline.py` → `LEXICON_BASELINE.md`):

| reader | accord top-1 (all rows) | val_unseen |
|---|---|---|
| Stage 1+2 checkpoint | ~0.00 | ~0.00 |
| Zone A lexicon (no training at all) | 0.013 | 0.000 |
| **always answer "citrus"** | **0.335** | — |

When two completely different systems both lose to a constant, the label is the problem. It is: the label says what the
**product page sold**, the text says **whatever the customer felt like writing** ("Four Stars. I really like it!"), and
where the text *does* describe the scent it often contradicts the catalogue's own accord order ("long lasting yummy oud"
→ labelled *citrus*, because citrus is first in Creed Royal Oud's `Main_Accords`).

## Therefore

**Do not retrain Stage 1+2 on this corpus.** 304 training rows with 5 % label fidelity cannot teach a 96-class model
anything a constant does not already achieve. Steps 2–4 of the old plan (domain adaptation, adding the rows, retraining)
are suspended — not because the work is hard, but because the result would be meaningless and would *look* like progress.

## What the corpus is actually good for — and this is now done

The 65,698 unlabelled reviews are a genuine asset as **language**, not as labels.
`preprocessing/mine_review_vocabulary.py` harvests the slots where a customer explicitly names a smell
("smells like ___", "notes of ___", "hints of ___", "___ scent"), associates each phrase with the accord terms the
lexicon reads **in the same sentence**, and scores them by lift over base rate. From 9,807 descriptive sentences it
proposed 143 phrases; 57 were accepted into `perfume-ai-system/data/user_lexicon.csv` (578 → 631 phrases), 20 rejected
with a reason, 163 left in `data/lexicon_candidates.csv` for review.

That is how the app got words it genuinely had no way to know: *chemical, plastic, cat pee, old lady, cleaning product,
bubble gum, cucumber, funky, band aid, dryer sheet, moth balls, play doh*. Every one carries its evidence.

## The order now

1. **Review `data/lexicon_candidates.csv`** (163 undecided) — the cheapest accuracy left on the table. `Apply=Yes` +
   `python data/review_input_log.py --promote`.
2. **Collect real wishes, not reviews** (was step 5, now the blocker). A review describes a bottle someone owns; the app
   answers a *wish*. N≈200 prompts of the form "what would you type into this box?", each labelled by a perfumer with
   1–3 accords. That is the only dataset that matches the task, and 200 honest rows beat 5,000 mislabelled ones.
3. **Then** consider a model: fine-tune MiniLM on (1) + (2) with the lexicon as a feature, and evaluate on held-out
   *wishes*. Until step 2 exists there is nothing to train against.
4. Domain-adapting the encoder on the 65k reviews (old step 2) stays available and is cheap (~1 h CPU), but it only
   helps a model that has a real training target, so it waits for step 2.

## Still true from the old plan

- Long CPU jobs go through Task Scheduler (`training/run_detached.py`) — the laptop sleeps; never a Bash background job.
- Never let the templated split be the only validation again: `10_real_splits.csv` has `val_unseen` for that reason.
- perfume-ai-system's Zone A works without any model: questionnaire, buttons and the lexicon are deterministic. The
  model would only ever improve the *match*, never the formula (Zone B is untouched by all of this).
