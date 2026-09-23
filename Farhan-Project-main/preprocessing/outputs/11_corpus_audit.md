# Real-review corpus audit (2026-09-23)

Source: `09_real_reviews_labelled_by_product.csv` — 5,078 reviews of 50 catalogue perfumes, weak-labelled by the product page.

## Is the label supported by the text?

- reviews that mention fragrance at all: **78.4%**
- reviews about a different product category (mask, cream, shampoo…): **3.8%**
- reviews whose perfume has no catalogue accord term (bridge gap): **4.5%**
- reviews where the lexicon reads no scent word at all: **43.8%**; 1 word: 10.2%; 2+: 46.1%
- text agrees with the labelled PRIMARY accord: **5.4%**; with ANY of the perfume's accords: **22.6%**

Among the reviews that do describe a scent (>= 2 accord words):

- agreement with the primary accord: **10.8%**, with any accord: **46.5%**

## Trainable rows

- on-topic + labelled + >= 2 scent words: **2,113 of 5,078 (41.6%)**, covering 21 perfumes
- largest perfume's share of those: 83 %

## What this means

The label says what the product page sells; the text says what the customer felt like writing. Those are different
things, and the numbers above are the size of the gap. A model trained on this pairing learns the gap, not the
language — which is exactly what the ~0 % real-world score of the Stage 1+2 checkpoint showed.

Per-perfume trainable counts:

| perfume | trainable | total |
|---|---|---|
| Coach for Men | 1752 | 4083 |
| Elizabeth Arden Green Tea | 303 | 546 |
| Juliette Has a Gun Vanilla Vibes | 19 | 33 |
| Azzaro Pour Homme | 8 | 54 |
| Parfums de Marly Delina | 6 | 14 |
| Prada Candy | 5 | 8 |
| Tom Ford Tobacco Vanille | 2 | 13 |
| John Varvatos Artisan Pure | 2 | 3 |
| Tom Ford Oud Wood | 2 | 11 |
| Jean Paul Gaultier La Belle | 2 | 6 |
| Calvin Klein CK One | 2 | 5 |
| Viktor & Rolf Bonbon | 1 | 2 |
| Jean Paul Gaultier Ultra Male | 1 | 3 |
| Mugler Alien | 1 | 6 |
| Hermès Un Jardin sur le Nil | 1 | 1 |
| Chanel Coco Mademoiselle | 1 | 6 |
| Ajmal Amber Wood | 1 | 2 |
| Lattafa Raghba Wood | 1 | 1 |
| Hugo Boss Bottled Oud | 1 | 1 |
| Creed Royal Oud | 1 | 1 |