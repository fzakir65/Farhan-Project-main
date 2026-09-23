# Zone A logs

- `input_log.csv` — one row per free-text interpretation: the sentence, what the keyword pass found, what the lexicon
  added, what the LLM added (if a key is configured), the final terms, avoid list, strength and the words nothing matched.
- `questionnaire_log.csv` — one row per completed questionnaire: the picks and the preferences they produced.

Both are **gitignored** (they contain what users typed) and both are inputs, not outputs: `python data/review_input_log.py`
turns them into `data/lexicon_candidates.csv` for review, `--promote` moves the approved rows into `data/user_lexicon.csv`,
and once there are enough rows they are the training set for the model that will replace the LLM fallback.
