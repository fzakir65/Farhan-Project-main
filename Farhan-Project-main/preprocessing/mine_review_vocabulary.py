"""Mine the 65k real reviews for words the lexicon does NOT know yet -> candidate rows for perfume-ai-system's
data/lexicon_candidates.csv (the human review queue).

    python preprocessing/mine_review_vocabulary.py                 # writes candidates, ranked
    python preprocessing/mine_review_vocabulary.py --min-count 40  # stricter

How it works (and why this is the honest use of the corpus):
  * a review's LABEL is not used — the product page says what was sold, not what the customer described (see
    outputs/11_corpus_audit.md). Nor is document-level co-occurrence used: on this corpus it only rediscovers the
    product category ('hair', 'face', 'lather'), because most reviews are of other beauty products.
  * instead the words are harvested from DESCRIPTIVE PATTERNS — the places where a customer is explicitly naming a
    smell: "smells like X", "notes of X", "reminds me of X", "hints of X", "X scent", "a touch of X". Whatever fills
    the slot is scent vocabulary by construction.
  * each harvested phrase is then associated with the accord terms the lexicon reads in the SAME SENTENCE (a much
    tighter context than the whole review), and kept when it clears MIN_COUNT occurrences.
  * the result is a SUGGESTION with the evidence attached (count, the terms it co-occurs with, an example sentence).
    A human sets Apply=Yes in lexicon_candidates.csv and `python data/review_input_log.py --promote` writes it into
    user_lexicon.csv. Nothing is added automatically: this is a datasheet, every row must be attributable.
"""
from __future__ import annotations

import collections
import csv
import math
import re
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
ENGINE = HERE.parent.parent / "perfume-ai-system"
CAND = ENGINE / "data" / "lexicon_candidates.csv"
COLS = ["Phrase", "Suggested_Terms", "Accord_Terms", "Seen", "Example", "Origin", "Apply", "Decided_By"]

FRAG_WORDS = re.compile(r"\b(perfume|fragrance|cologne|scent|smell|smells|eau de|edt|edp|parfum|notes?)\b", re.I)
OFF_TOPIC = re.compile(r"\b(mask|masks|moisturi[sz]|serum|shampoo|conditioner|razor|blade|toothpaste|wipes|acne|wrinkle|"
                       r"hyaluronic|makeup remover|foundation|concealer|mascara|lipstick|nail)\b", re.I)
# the slots where a customer explicitly names a smell
PATTERNS = [
    re.compile(r"smells? (?:just )?like (?:an? |the |some )?([a-z][a-z' \-]{2,30})", re.I),
    re.compile(r"smell of (?:an? |the )?([a-z][a-z' \-]{2,30})", re.I),
    re.compile(r"notes? of (?:an? |the )?([a-z][a-z' \-]{2,30})", re.I),
    re.compile(r"hints? of (?:an? |the )?([a-z][a-z' \-]{2,30})", re.I),
    re.compile(r"touch of (?:an? |the )?([a-z][a-z' \-]{2,30})", re.I),
    re.compile(r"reminds me of (?:an? |the |my )?([a-z][a-z' \-]{2,30})", re.I),
    re.compile(r"reminiscent of (?:an? |the )?([a-z][a-z' \-]{2,30})", re.I),
    re.compile(r"\b(?:very|really|quite|so|too)? ?([a-z][a-z'\-]{3,20})[ -]scented\b", re.I),
    re.compile(r"\b([a-z][a-z'\-]{3,20}) (?:scent|smell|fragrance|note)\b", re.I),
]
SENT_SPLIT = re.compile(r"[.!?;\n]+")
WORD = re.compile(r"[a-z][a-z'\-]{2,}")
MIN_SCENT = 1            # known accord words the SENTENCE must contain for the association (0 = none required)
MIN_COUNT_DEFAULT = 12
MIN_LIFT = 2.0            # a context term must be 2x more likely here than in descriptive sentences generally
TOP_TERMS_PER_WORD = 3
# words that fill the slot but are not smells
JUNK = re.compile(r"^(amazon|seller|shipping|delivery|package|packaging|bottle|bottles|refund|return|returned|order|ordered|"
                  r"price|prices|pricey|cheap|expensive|money|worth|product|item|review|reviews|star|stars|purchase|purchased|"
                  r"husband|wife|daughter|mother|father|friend|gift|gifts|birthday|christmas|compliment|compliments|"
                  r"recommend|recommended|definitely|absolutely|probably|actually|literally|honestly|basically|"
                  r"description|picture|photo|advertised|expected|other|others|another|same|different|original|real|fake|"
                  r"first|second|last|next|only|every|each|any|all|some|most|more|less|much|many|lot|lots|bit|little|"
                  r"one|two|three|time|times|day|days|week|weeks|month|months|year|years|hour|hours|minute|minutes|"
                  r"thing|things|stuff|kind|type|sort|way|ways|part|place|use|uses|usage|wear|wearing|skin|body|hair|face|"
                  r"man|men|woman|women|guy|guys|girl|girls|people|person|everyone|someone|anyone|nobody|"
                  r"before|after|during|while|when|where|which|what|who|how|why|because|though|although|however|"
                  r"good|great|nice|bad|awful|terrible|amazing|wonderful|perfect|excellent|favorite|favourite|best|better|worse|"
                  r"strong|light|heavy|long|short|big|small|new|old|young|high|low|full|empty|clean|dirty|"
                  # function words that slip through 'X scent'
                  r"this|that|these|those|they|them|their|there|here|it's|its|he|she|his|her|him|you|your|our|we|"
                  r"does|doesn't|don't|didn't|isn't|wasn't|won't|can't|couldn't|shouldn't|wouldn't|hasn't|haven't|"
                  r"could|would|should|will|shall|might|must|may|can|been|being|have|has|had|was|were|are|is|am|"
                  r"just|still|even|also|very|really|quite|rather|pretty|somewhat|slightly|super|extremely|totally|"
                  r"like|likes|liked|love|loves|loved|hate|hates|hated|want|wants|wanted|need|needs|needed|"
                  r"get|gets|got|give|gives|gave|make|makes|made|take|takes|took|put|puts|say|says|said|"
                  r"think|thinks|thought|know|knows|knew|find|finds|found|feel|feels|felt|seem|seems|seemed|"
                  r"lasting|staying|projection|sillage|longevity|scent|smell|smells|fragrance|perfume|cologne|parfum|note|notes|"
                  # judgements of quality, not names of smells
                  r"pleasant|unpleasant|lovely|beautiful|gorgeous|horrible|awesome|weird|strange|odd|funny|"
                  r"disgusting|nasty|cheap-smelling|delightful|divine|heavenly|incredible|fantastic|fabulous|"
                  r"overpowering|overwhelming|subtle|mild|faint|slight|intense|powerful|masculine|feminine|unisex)$")

def _phrase_ok(ph: str) -> bool:
    ph = ph.strip()
    if not (2 < len(ph) < 28) or ph.endswith(("'", "-")):
        return False
    words = ph.split()
    return 1 <= len(words) <= 3 and not any(JUNK.match(w) for w in words)


def main(argv: list[str]) -> int:
    src = OUT / "09_real_reviews.csv"
    if not src.exists():
        print("missing 09_real_reviews.csv — run preprocessing/build_real_reviews.py first")
        return 2
    min_count = int(argv[argv.index("--min-count") + 1]) if "--min-count" in argv else MIN_COUNT_DEFAULT
    sys.path.insert(0, str(ENGINE))
    from zone_a_llm.lexicon import Lexicon, STOPWORDS      # noqa: E402

    lx = Lexicon.load()
    known_phrases = set(lx.rows)
    df = pd.read_csv(src, dtype=str, keep_default_na=False)
    print(f"{len(df):,} reviews; harvesting descriptive patterns with {len(known_phrases)} known lexicon phrases…")

    seen: collections.Counter = collections.Counter()
    ctx: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    term_base: collections.Counter = collections.Counter()      # how often each term appears in ANY descriptive sentence
    example: dict[str, str] = {}
    n_sent = 0
    for t in df["text"]:
        text = str(t)
        if not FRAG_WORDS.search(text) or OFF_TOPIC.search(text):
            continue
        for sent in SENT_SPLIT.split(text):
            if len(sent) < 12 or not FRAG_WORDS.search(sent):
                continue
            found = []
            for pat in PATTERNS:
                for m in pat.finditer(sent):
                    ph = re.sub(r"\s+", " ", m.group(1).casefold()).strip(" '-")
                    ph = re.sub(r"^(a|an|the|some|any|this|that|my|your|his|her|its|their)\s+", "", ph)
                    if _phrase_ok(ph) and ph not in known_phrases:
                        found.append(ph)
            if not found:
                continue
            n_sent += 1
            terms = set(lx.apply(sent).weights)
            for term in terms:
                term_base[term] += 1
            for ph in set(found):
                seen[ph] += 1
                example.setdefault(ph, sent.strip()[:140])
                for term in terms:
                    if term not in ph:
                        ctx[ph][term] += 1

    print(f"{n_sent:,} descriptive sentences; {len(seen):,} distinct phrases before the count filter")
    rows = []
    for ph, n in seen.most_common():
        if n < min_count:
            continue
        # lift = how much more often this term accompanies the phrase than it accompanies descriptive sentences generally
        lifted = []
        for term, c in ctx[ph].items():
            base = term_base[term] / max(1, n_sent)
            if base <= 0 or c < 3:
                continue
            lift = (c / n) / base
            if lift >= MIN_LIFT:
                lifted.append((round(lift, 2), c, term))
        lifted.sort(reverse=True)
        top = lifted[:TOP_TERMS_PER_WORD]
        weights = [1.0, 0.8, 0.6][:len(top)]
        rows.append({"Phrase": ph, "Suggested_Terms": ";".join(f"{t}:{w:g}" for (_, _, t), w in zip(top, weights)),
                     "Accord_Terms": "", "Seen": n, "Example": example[ph].replace("\n", " "),
                     "Origin": "review corpus pattern (" + (", ".join(f"{t} lift {l:g} on {c}" for l, c, t in top) or "no distinctive context term") + ")",
                     "Apply": "", "Decided_By": ""})

    old = pd.read_csv(CAND, dtype=str, keep_default_na=False) if CAND.exists() else pd.DataFrame(columns=COLS)
    keep = old[~old["Phrase"].isin({r["Phrase"] for r in rows})]
    decided = {r.Phrase: r for r in old.itertuples() if str(r.Apply).strip().lower() in ("yes", "no")}
    for r in rows:
        if r["Phrase"] in decided:
            d = decided[r["Phrase"]]
            r["Accord_Terms"], r["Apply"], r["Decided_By"] = d.Accord_Terms, d.Apply, d.Decided_By
    out = pd.concat([keep, pd.DataFrame(rows)], ignore_index=True) if len(keep) else pd.DataFrame(rows)
    out.to_csv(CAND, index=False, encoding="utf-8")
    (OUT / "12_review_vocabulary.csv").write_text(pd.DataFrame(rows).to_csv(index=False), encoding="utf-8")
    print(f"{len(rows)} candidate phrases (>= {min_count} sentences) -> {CAND.relative_to(ENGINE.parent)}")
    for r in rows[:30]:
        print(f"   {r['Seen']:5d}  {r['Phrase']:<18} {r['Suggested_Terms']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
