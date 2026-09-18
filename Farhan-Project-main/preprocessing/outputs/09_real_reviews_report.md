# Real reviews build (2026-09-18)

- scanned 701,528 All_Beauty reviews in 349 s (streamed, nothing stored locally but the outputs)
- 65,698 fragrance-related reviews (>= 8 words, fragrance vocabulary present) -> 09_real_reviews.csv
- 701 name a catalogue perfume -> 09_real_reviews_labelled.csv (weak label = that perfume's accords)
- 38 distinct catalogue perfumes matched; top: Coach for Men (295), Narciso Rodriguez For Her (183), Elizabeth Arden Green Tea (123), Tom Ford Oud Wood (14), Creed Aventus (8), Azzaro Pour Homme (7), Carolina Herrera Bad Boy (7), Tom Ford Tobacco Vanille (6), Tom Ford Black Orchid (6), Ralph Lauren Polo Blue (5), Chanel Bleu de Chanel (5), Carolina Herrera Good Girl (4), Chanel Coco Mademoiselle (4), Dior Hypnotic Poison (4), Gucci Bloom (2)

Use: (1) realism check of the Stage 1+2 model on real language (evaluate_on_real_reviews.py); (2) extra training rows
once the preprocessing pipeline is extended to derive descriptors for free text (plan F.5).
## Product-title labelling (2026-09-18)

- 1133 products (ASINs) whose title names a catalogue perfume; 5,078 of their reviews labelled
- 50 distinct perfumes; top: Coach for Men (4083), Elizabeth Arden Green Tea (546), Narciso Rodriguez For Her (164), Azzaro Pour Homme (54), Mugler Angel (36), Juliette Has a Gun Vanilla Vibes (33), Parfums de Marly Delina (14), Tom Ford Tobacco Vanille (13), Creed Silver Mountain Water (13), Tom Ford Black Orchid (12), Tom Ford Oud Wood (11), Carolina Herrera Good Girl (11), Prada Candy (8), Chanel Coco Mademoiselle (6), Bvlgari Rose Goldea (6)
- file: 09_real_reviews_labelled_by_product.csv (weak label = the perfume on the product page)
