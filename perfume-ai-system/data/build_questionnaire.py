"""Write data/questionnaire.csv — the guided path: questions, options and what each option means in catalogue terms.

    python data/build_questionnaire.py

Each option carries accord weights ('term:weight;…'), optionally a family, gender, season, strength and avoid terms. Picks
accumulate (zone_a_llm/questionnaire.py) into the same Preferences the free-text path produces, so the matcher and the
inventor need nothing new. Every term is validated against the catalogue vocabulary at build time. The scene -> accord
mapping is a design decision (Decided_By = ai) informed by Ohloff's family lists (2e Ch 9.3) and Curtis' odour vocabulary
(Ch 3); a perfumer can re-weight any option by editing the CSV.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
OUT = HERE / "questionnaire.csv"
COLS = ["Question_ID", "Question", "Type", "Max_Picks", "Option_ID", "Option", "Accord_Terms", "Family", "Gender", "Season", "Strength", "Avoid", "Basis", "Decided_By"]
BASIS = "scene -> accord mapping, AI-authored 2026-09-22 after Ohloff 2e Ch 9.3 families (p.609-616) and Curtis 1994 Ch 3 odour vocabulary (p.66-91)"

Q = [
    ("Q1", "When will you wear it most?", "single", 1, [
        ("a", "Every day, work or study", "clean:1;fresh:0.9;woody:0.6;musky:0.5", "", "", "", "3", ""),
        ("b", "Evenings out", "amber:1;sweet:0.8;warm spicy:0.7;oud:0.5", "", "", "", "4", ""),
        ("c", "A special occasion", "white floral:0.9;iris:0.8;amber:0.7;oud:0.6", "", "", "", "4", ""),
        ("d", "Sport and the outdoors", "fresh:1;aquatic:0.9;citrus:0.9;green:0.6", "", "", "", "3", ""),
        ("e", "Relaxing at home", "vanilla:0.9;musky:0.8;powdery:0.7;warm:0.6", "", "", "", "2", ""),
    ]),
    ("Q2", "Which season should it feel like?", "single", 1, [
        ("a", "Spring", "green:1;floral:0.9;fresh:0.7", "", "", "Spring", "", ""),
        ("b", "Summer", "citrus:1;aquatic:0.9;fresh:0.8;coconut:0.4", "", "", "Summer", "", ""),
        ("c", "Autumn", "woody:1;warm spicy:0.8;earthy:0.6;tobacco:0.4", "", "", "Fall", "", ""),
        ("d", "Winter", "amber:1;warm spicy:0.9;vanilla:0.7;incense:0.5", "", "", "Winter", "", ""),
        ("e", "All year", "", "", "", "", "", ""),
    ]),
    ("Q3", "What feeling should it give?", "single", 1, [
        ("a", "Fresh and clean", "fresh:1;clean:1;citrus:0.7;soapy:0.5", "", "", "", "", ""),
        ("b", "Warm and cosy", "warm:1;amber:0.9;vanilla:0.8;musky:0.5", "", "", "", "", ""),
        ("c", "Sweet and playful", "sweet:1;fruity:0.9;gourmand:0.7;caramel:0.4", "", "", "", "", ""),
        ("d", "Dark and mysterious", "smoky:1;oud:0.9;leather:0.8;incense:0.7", "", "", "", "", ""),
        ("e", "Elegant and classic", "iris:1;aldehydic:0.8;floral:0.8;chypre:0.6", "", "", "", "", ""),
        ("f", "Natural and earthy", "earthy:1;green:0.9;vetiver:0.7;mossy:0.6", "", "", "", "", ""),
        ("g", "Seductive", "sensual:1;musky:0.9;amber:0.8;animalic:0.4", "", "", "", "", ""),
    ]),
    ("Q4", "Pick up to three smells you love", "multi", 3, [
        ("a", "Freshly cut grass", "grassy:1;green:0.9", "", "", "", "", ""),
        ("b", "Sea breeze", "marine:1;aquatic:0.9;salty:0.7", "", "", "", "", ""),
        ("c", "Lemon peel", "citrus:1;fresh:0.6", "", "", "", "", ""),
        ("d", "A rose garden", "rose:1;floral:0.8", "", "", "", "", ""),
        ("e", "Jasmine at night", "jasmine:1;white floral:0.9", "", "", "", "", ""),
        ("f", "Vanilla cake", "vanilla:1;sweet:0.8;gourmand:0.7", "", "", "", "", ""),
        ("g", "Fresh coffee", "coffee:1;gourmand:0.5", "", "", "", "", ""),
        ("h", "Dark chocolate", "chocolate:1;cacao:0.9;sweet:0.5", "", "", "", "", ""),
        ("i", "An old library", "woody:0.9;powdery:0.6;inky:0.6;leather:0.5", "", "", "", "", ""),
        ("j", "Pencil shavings", "woody:1", "", "", "", "", ""),
        ("k", "A pine forest", "coniferous:1;green:0.7;woody:0.6", "", "", "", "", ""),
        ("l", "Incense in a church", "incense:1;resinous:0.8;smoky:0.5", "", "", "", "", ""),
        ("m", "Clean laundry", "clean:1;soapy:0.8;musky:0.6", "", "", "", "", ""),
        ("n", "A spice market", "warm spicy:1;spicy:0.9;cinnamon:0.5", "", "", "", "", ""),
        ("o", "Ripe peaches", "fruity:1;lactonic:0.5;sweet:0.5", "", "", "", "", ""),
        ("p", "Honey", "honey:1;sweet:0.7", "", "", "", "", ""),
        ("q", "Rain on dry soil", "earthy:1;damp:0.8;mineral:0.5", "", "", "", "", ""),
        ("r", "Tobacco and whisky", "tobacco:1;boozy:0.9;whisky:0.7", "", "", "", "", ""),
        ("s", "Fresh mint tea", "minty:1;tea:0.8;fresh:0.6", "", "", "", "", ""),
        ("t", "Lavender fields", "lavender:1;aromatic:0.7", "", "", "", "", ""),
        ("u", "Baby powder", "powdery:1;musky:0.5;iris:0.4", "", "", "", "", ""),
        ("v", "A campfire", "smoky:1;woody:0.7", "", "", "", "", ""),
        ("w", "Coconut and sun cream", "coconut:1;tropical:0.8", "", "", "", "", ""),
        ("x", "Marzipan", "almond:1;sweet:0.6", "", "", "", "", ""),
        ("y", "Leather", "leather:1;suede:0.5", "", "", "", "", ""),
        ("z", "Sandalwood", "sandalwood:1;woody:0.8;milky:0.4", "", "", "", "", ""),
    ]),
    ("Q5", "Anything you cannot stand? (pick any)", "multi", 5, [
        ("a", "Sweet, sugary things", "", "", "", "", "", "sweet;gourmand;caramel"),
        ("b", "Heavy florals", "", "", "", "", "", "white floral;floral;tuberose"),
        ("c", "Powdery, old-fashioned", "", "", "", "", "", "powdery;aldehydic;iris"),
        ("d", "Smoke and leather", "", "", "", "", "", "smoky;leather;tobacco"),
        ("e", "Sharp citrus", "", "", "", "", "", "citrus"),
        ("f", "Patchouli and earthy", "", "", "", "", "", "patchouli;earthy"),
        ("g", "Animal / musky", "", "", "", "", "", "animalic;musky"),
        ("h", "Nothing, I am open", "", "", "", "", "", ""),
    ]),
    ("Q6", "How strong should it be?", "single", 1, [
        ("a", "Barely there, just for me", "", "", "", "", "1", ""),
        ("b", "Close to the skin", "", "", "", "", "2", ""),
        ("c", "Noticeable", "", "", "", "", "3", ""),
        ("d", "Fills the room", "", "", "", "", "5", ""),
    ]),
    ("Q7", "Who is it for?", "single", 1, [
        ("a", "Him", "", "", "Men", "", "", ""),
        ("b", "Her", "", "", "Women", "", "", ""),
        ("c", "Anyone", "", "", "Unisex", "", "", ""),
    ]),
    ("Q8", "If this scent were a place…", "single", 1, [
        ("a", "A beach at noon", "aquatic:1;salty:0.8;coconut:0.6;citrus:0.5", "", "", "", "", ""),
        ("b", "A forest after rain", "green:1;earthy:0.8;coniferous:0.7;damp:0.6", "", "", "", "", ""),
        ("c", "A city at night", "oud:0.9;amber:0.9;leather:0.6;smoky:0.5", "", "", "", "", ""),
        ("d", "A country garden", "floral:1;rose:0.7;green:0.7;honey:0.4", "", "", "", "", ""),
        ("e", "A bakery", "gourmand:1;vanilla:0.9;sweet:0.8;caramel:0.5", "", "", "", "", ""),
        ("f", "A desert at dusk", "amber:1;incense:0.8;resinous:0.6;mineral:0.5", "", "", "", "", ""),
        ("g", "A mountain cabin", "woody:1;smoky:0.7;coniferous:0.7;warm:0.5", "", "", "", "", ""),
        ("h", "A spa", "clean:1;fresh:0.8;tea:0.6;herbal:0.5", "", "", "", "", ""),
    ]),
]


def main() -> int:
    from load_data import load_all
    from zone_a_llm.input_handler import vocabulary
    data = load_all()
    vocab = vocabulary(data)
    terms = set(vocab["accords"])
    rows = []
    for qid, q, typ, mx, opts in Q:
        for oid, text, acc, fam, gender, season, strength, avoid in opts:
            for item in [x for x in acc.split(";") if x]:
                t = item.rsplit(":", 1)[0]
                if t not in terms:
                    raise SystemExit(f"questionnaire {qid}{oid}: unknown term {t!r}")
            for t in [x for x in avoid.split(";") if x]:
                if t not in terms:
                    raise SystemExit(f"questionnaire {qid}{oid}: unknown avoid term {t!r}")
            if fam and fam not in vocab["families"]:
                raise SystemExit(f"questionnaire {qid}{oid}: unknown family {fam!r}")
            rows.append({"Question_ID": qid, "Question": q, "Type": typ, "Max_Picks": mx, "Option_ID": oid, "Option": text, "Accord_Terms": acc, "Family": fam,
                         "Gender": gender, "Season": season, "Strength": strength, "Avoid": avoid, "Basis": BASIS, "Decided_By": "ai"})
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS); w.writeheader(); w.writerows(rows)
    print(f"{len(Q)} questions, {len(rows)} options -> {OUT.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
