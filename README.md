# Farhan Project — AI Perfume Formulation

Describe a scent in plain words. Get back a balanced, IFRA-compliant, UK-legal formula
you could actually mix.

```
"something warm for winter evenings, not too sweet"
        ↓
   matched profile  →  accords  →  materials  →  safety  →  formula
```

## Two folders

| | |
|---|---|
| **`perfume-ai-system/`** | The live system. Start here — read its `CLAUDE.md` first. |
| **`Farhan-Project-main/`** | An earlier ML experiment on perfume reviews. Kept for its data work; the model is not used. |

## The one rule that matters

The system is split in two, and the split never blurs:

- **Zone A** interprets language — what you meant, which profile fits. An LLM may help here.
  A wrong answer is disappointing.
- **Zone B** does chemistry, IFRA limits and cosmetics law. Pure deterministic Python and CSV
  lookups by CAS number. **No LLM, ever.** A wrong answer is unsafe or illegal.

Same input always gives the same formula, and every adjustment cites the table row that caused it.

## Quick start

```bash
cd perfume-ai-system
pip install -r requirements.txt

python load_data.py                             # data health report
python app.py "fresh woody for summer"          # match → formula → safety → bottle
python app.py --invent "citrus, mossy, rose" --family Chypre
python app.py --quiz                            # the questionnaire, no API key needed
streamlit run app.py                            # the UI
python -m pytest -q                             # 246 tests, ~4 min
```

No API key is required. The buttons, the questionnaire and the phrase lexicon all work offline;
the LLM is only called when those find nothing, and never for a quantity or a safety decision.

## The four datasheets

| | Rows | What it holds |
|---|---|---|
| **1 — profiles** | 455 | Scent profiles in human words: family, accords, gender, season, mood, occasion |
| **2 — accords** | 1,518 | The bridge. "Smoky" is not a substance — it's a recipe of substances |
| **3 — materials** | 803 | The substances: CAS number, pyramid layer, strength, physical properties |
| **4 — requests** | **0** | Real requests answered by a perfumer. Does not exist yet — the main blocker |

Plain-English write-ups live in [`perfume-ai-system/docs/`](perfume-ai-system/docs/):
why the sheets need rebuilding, what new ones must contain, and how much data training needs.

## Status

The chemistry engine is finished and tested. All 455 profiles pass the full safety pass.

Two things still need a human, not more code:

1. **Supplier certificates** for the natural oils. Every safety verdict is marked *provisional*
   until the real percentage of restricted constituents in each oil is known.
2. **~200 real requests labelled by a perfumer.** Two attempts to substitute for this failed:
   5,078 reviews labelled by their product page were supported by the text only 5.4% of the
   time, and a file of 505 ready-made "training examples" turned out to be generated rather
   than collected. A label nobody checked is not a label.

## Sources

The chemistry follows published literature, and every derived table cites its page:

Jean Carles, *A Method of Creation in Perfumery* · IFRA 51st Amendment ·
Pybus & Sell, *The Chemistry of Fragrances* (RSC) · Tisserand & Young, *Essential Oil Safety* 2e ·
Curtis & Williams, *An Introduction to Perfumery* · Ohloff, Pickenhagen & Kraft, *Scent and Chemistry* 2e ·
Poucher's *Perfumes, Cosmetics and Soaps*.

The tables under `data/reference/` are page-cited extracts made for this project's own use, not a
substitute for the books. The books themselves are not included.

## Not medical or legal advice

This is a research project. Nothing here has been reviewed by a qualified perfumer or a cosmetic
safety assessor. Do not put its output on skin or sell it without a proper Cosmetic Product Safety
Report. Every safety verdict currently carries a `PROVISIONAL` flag for exactly this reason.
