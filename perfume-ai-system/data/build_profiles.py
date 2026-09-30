"""dataset1 rebuilt as a DE-BRANDED PROFILE LIBRARY (called by data/build_datasets.py).

What changed and why (2026-09-24, on the user's instruction "remove the perfume brands"):
  * `Brand` is gone and `Perfume_Name` becomes `Profile_Name` — a neutral descriptive label ("Aromatic Fougère No. 3").
    The system exists to compose perfumes, not to sell branded ones; shipping formulas under a trademark is a liability
    and the brand adds nothing the composition does not already say. Lineage is not lost: the source workbook
    (`../Farhan-Project-main/perfume_system_master_with_recipes.xlsx`) still carries the original rows in order.
  * the source columns were dirty and nobody had noticed, because Zone B routes through `Main_Accords` only:
      - `Gender` contained season values for 10 rows ("Spring, Summer, Day")
      - `Season` mixed seasons with time of day -> split into `Season` + `Time_Of_Day`, normalised to a fixed set
      - `Longevity` / `Sillage` came in 4 casings plus "Eternal" / "Enormous" -> normalised, and the 1-5 scores the
        loader derives are written out as columns so nothing has to re-guess them
      - `Top/Middle/Base_Notes` held 805 "names", only 81 of which exist in dataset2, because a single cell often held
        a comma-separated list ("Aldehydes, Bergamot, Pink Pepper") -> split into atoms and resolved to dataset2 names
  * `Mood_Vibe` and `Occasion` were 100 % empty. They are now derived from the profile's own accords by inverting
    `data/questionnaire.csv` (Q1 occasion, Q3 mood) — the same mapping Zone A uses to read a customer, so a profile is
    described in exactly the vocabulary a customer picks from. `Climate` is added on the same basis.
  * archetype profiles from the books are appended (Curtis' type formulas), so the library contains the classical
    structures a perfumer expects, each cited.

Every generated column carries its basis in `Source`; `Decided_By` is `workbook` for source data, `derived` for the
normalisation, `book` for the appended archetypes.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
SEASONS = ("Spring", "Summer", "Fall", "Winter")
TIMES = ("Day", "Night")
GENDERS = {"men": "Men", "male": "Men", "man": "Men", "women": "Women", "female": "Women", "woman": "Women",
           "unisex": "Unisex", "shared": "Unisex"}
SEASON_WORDS = {"spring": "Spring", "summer": "Summer", "fall": "Fall", "autumn": "Fall", "winter": "Winter",
                "all seasons": "Spring|Summer|Fall|Winter"}
TIME_WORDS = {"day": "Day", "daytime": "Day", "night": "Night", "evening": "Night", "nighttime": "Night"}
# the normalised word must be a key load_data.LONGEVITY_SCORE / SILLAGE_SCORE knows, so the 1-5 scores stay derivable
LONGEVITY = [(r"eternal|very long", ("very long lasting", 5)), (r"long", ("long lasting", 4)),
             (r"moderate|medium", ("moderate", 3)), (r"weak|short|poor", ("weak", 2))]
SILLAGE = [(r"enormous|huge", ("enormous", 5)), (r"very strong", ("very strong", 4)), (r"strong|heavy", ("strong", 3)),
           (r"moderate|medium", ("moderate", 2)), (r"soft|light", ("soft", 1)), (r"intimate|skin", ("intimate", 1))]
CLIMATE = {"Summer": "Hot", "Winter": "Cold", "Spring": "Temperate", "Fall": "Temperate"}


def _text(v) -> str:
    """A cell as clean text — pandas NaN must not become the string 'nan'."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    t = str(v).strip()
    return "" if t.lower() in ("nan", "none", "<na>") else t


def _norm_list(cell: str, sep: str = ";") -> list[str]:
    return [p.strip() for p in str(cell or "").split(sep) if p.strip()]


def _atoms(cell: str) -> list[str]:
    """'Aldehydes, Bergamot; Iris' -> ['Aldehydes', 'Bergamot', 'Iris'] — the source packs lists inside one cell."""
    out: list[str] = []
    for part in re.split(r"[;,]", str(cell or "")):
        p = re.sub(r"\s+", " ", part).strip(" .")
        if p and p.casefold() not in ("and", "etc", "others"):
            out.append(p)
    return out


def _pick(patterns, text: str, default):
    t = str(text or "").casefold()
    for pat, val in patterns:
        if re.search(pat, t):
            return val
    return default


def _questionnaire_map(path: Path) -> tuple[list[tuple[str, set[str]]], list[tuple[str, set[str]]]]:
    """(occasion options, mood options) as (label, accord terms) — the inverse of what Zone A asks the customer."""
    q = pd.read_csv(path, dtype=str, keep_default_na=False)
    def opts(qid: str) -> list[tuple[str, set[str]]]:
        out = []
        for r in q[q["Question_ID"] == qid].itertuples():
            terms = {x.rsplit(":", 1)[0] for x in str(r.Accord_Terms).split(";") if ":" in x}
            if terms:
                out.append((r.Option, terms))
        return out
    return opts("Q1"), opts("Q3")


# accords that imply a mood / occasion but are not themselves questionnaire options
NEIGHBOUR = {"aromatic": "fresh", "herbal": "green", "fresh spicy": "fresh", "soft spicy": "warm spicy", "spicy": "warm spicy",
             "spices": "warm spicy", "cinnamon": "warm spicy", "cardamom": "warm spicy", "anis": "warm spicy",
             "balsamic": "amber", "resinous": "amber", "oriental": "amber", "boozy": "sweet", "rum": "sweet", "whisky": "sweet",
             "bourbon": "sweet", "alcohol": "fresh", "coconut": "sweet", "almond": "sweet", "nutty": "sweet", "honey": "sweet",
             "honeyed": "sweet", "caramel": "sweet", "chocolate": "sweet", "cacao": "sweet", "coffee": "sweet", "milky": "sweet",
             "lactonic": "sweet", "tropical": "fruity", "pear": "fruity", "fig": "fruity", "berry": "fruity",
             "rose": "floral", "rosy": "floral", "jasmine": "white floral", "tuberose": "white floral", "violet": "powdery",
             "lavender": "fresh", "tea": "green", "grassy": "green", "coniferous": "green", "camphor": "green",
             "marine": "aquatic", "ozonic": "aquatic", "salty": "aquatic", "mineral": "aquatic", "sand": "aquatic", "damp": "earthy",
             "patchouli": "earthy", "sandalwood": "woody", "cedar": "woody", "oud": "oud", "tobacco": "smoky", "leathery": "leather",
             "suede": "leather", "musk": "musky", "beeswax": "sweet", "metallic": "clean", "inky": "clean", "aldehydic": "aldehydic",
             "intense": "sensual", "sensual": "sensual", "captivating": "sensual", "vibrant": "fresh", "warm": "warm"}


def _best(options: list[tuple[str, set[str]]], accords: set[str], n: int = 2) -> str:
    """The option(s) whose accord set the profile best covers. Accords that are not options themselves are first
    translated to their nearest option term (NEIGHBOUR), so an 'aromatic; herbal' profile is still described."""
    widened = set(accords) | {NEIGHBOUR[a] for a in accords if a in NEIGHBOUR}
    scored = [(len(widened & terms) / max(1, len(terms)), label) for label, terms in options]
    scored = [(s, l) for s, l in scored if s > 0]
    scored.sort(reverse=True)
    return "; ".join(l for _, l in scored[:n])


def _note_resolver(known: set[str]):
    """name -> dataset2 Note_Name, using the project's own alias tables first and a whole-word fallback after."""
    low = {k.casefold(): k for k in known}
    alias: dict[str, str] = {}
    ap = HERE / "note_name_aliases.csv"
    if ap.exists():
        a = pd.read_csv(ap, dtype=str, keep_default_na=False)
        for r in a[a["Apply"].str.strip().str.lower() == "yes"].itertuples():
            tgt = getattr(r, "Dataset2_Name", "") or getattr(r, "Dataset2_Note_Name", "")
            if tgt in known:
                alias[str(getattr(r, "Dataset3_Name", "") or getattr(r, "Dataset3_Note_Name", "")).casefold()] = tgt
    try:
        import sys
        sys.path.insert(0, str(HERE.parent))
        from zone_a_llm.book_accords import ALIASES       # book material name -> dataset2 name
        for k, v in ALIASES.items():
            if v in known:
                alias.setdefault(k, v)
    except Exception:  # noqa: BLE001 — the alias table is a bonus, never a requirement
        pass
    # everyday names for materials dataset2 already holds ('Cedar' -> Cedarwood, 'Oud' -> Agarwood). This table is
    # read HERE and nowhere else: renaming a note inside an accord would be a chemistry change, so it never reaches
    # note_name_aliases.csv. Rows with Apply=No are recorded gaps and deliberately stay unresolved.
    dp = HERE / "note_display_aliases.csv"
    if dp.exists():
        d = pd.read_csv(dp, dtype=str, keep_default_na=False)
        for r in d[d["Apply"].str.strip().str.lower() == "yes"].itertuples():
            tgt = _text(getattr(r, "Dataset2_Name", ""))
            if tgt in known:
                alias.setdefault(_text(r.Everyday_Name).casefold(), tgt)

    def resolve(name: str) -> str:
        n = re.sub(r"\s+", " ", name).strip()
        if n in known:
            return n
        k = n.casefold()
        if k in low:
            return low[k]
        if k in alias:
            return alias[k]
        k2 = re.sub(r"[^a-z0-9 ]+", " ", k)
        k2 = re.sub(r"\s+", " ", k2).strip()
        if k2 in low:
            return low[k2]
        if k2 in alias:
            return alias[k2]
        for suffix in (" oil", " absolute", " extract", " accord", " notes", " note", " resinoid", " essence"):
            if k2.endswith(suffix) and k2[: -len(suffix)] in low:
                return low[k2[: -len(suffix)]]
        # 'Amalfi Lemon' / 'Sicilian Bergamot' -> the catalogue note that ENDS the phrase (a qualifier in front)
        words = k2.split()
        for take in (3, 2, 1):
            if len(words) > take:
                tail = " ".join(words[-take:])
                if tail in low:
                    return low[tail]
                if tail in alias:
                    return alias[tail]
        return n

    # every phrase the resolver can answer, longest first — used to cut a run of words that carries no delimiter
    resolve.phrases = sorted(set(low) | set(alias), key=len, reverse=True)      # type: ignore[attr-defined]
    return resolve


def _split_run(text: str, resolve) -> list[str]:
    """Some source cells list several notes with NO delimiter at all — 'Rose Sea Salt Seaweed Musk Pink Pepper' is
    one cell. Cut it by matching the longest known note phrase at each position; a word that starts no known phrase
    is emitted on its own so nothing is silently dropped."""
    words = text.split()
    phrases = getattr(resolve, "phrases", None)
    if not phrases or len(words) < 3:
        return [text]
    known = set(phrases)
    out, i, matched, loose = [], 0, 0, 0
    while i < len(words):
        for take in range(min(4, len(words) - i), 0, -1):
            cand = " ".join(words[i:i + take])
            if cand.casefold() in known:
                out.append(cand)
                matched += 1
                i += take
                break
        else:
            out.append(words[i])
            loose += 1
            i += 1
    # Only accept the cut if it really found a list. 'Olive Tree Sandalwood' matching one word is not evidence that
    # the cell is a list — shredding an unknown two-word name into single words would be worse than leaving it.
    return out if matched >= 2 and loose <= matched else [text]


def build(src: pd.DataFrame, notes: pd.DataFrame | None = None) -> pd.DataFrame:
    """src: the workbook sheet (perfume_id, perfume_name, brand, fragrance_family, …). Returns the profile library."""
    occ_opts, mood_opts = _questionnaire_map(HERE / "questionnaire.csv")
    known = set(notes["Note_Name"]) if notes is not None else set()
    map_note = _note_resolver(known) if known else (lambda x: x)

    rows = []
    family_counter: dict[str, int] = {}
    for r in src.itertuples(index=False):
        fam = str(getattr(r, "fragrance_family", "")).strip() or "Unclassified"
        family_counter[fam] = family_counter.get(fam, 0) + 1
        # the source packs terms with BOTH separators ('oud, spicy, resinous; woody'); no catalogue term contains a comma
        accords = [a.strip().casefold() for a in re.split(r"[;,\n]", str(getattr(r, "main_accords_raw", ""))) if a.strip()]
        acc_set = set(accords)

        gender_raw = str(getattr(r, "gender", "")).strip()
        gender = GENDERS.get(gender_raw.casefold(), "")
        season_src = f"{getattr(r, 'season_raw', '')} {gender_raw if not gender else ''}"      # the 10 rows where seasons landed in Gender
        seasons, times = [], []
        low = season_src.casefold()
        for word, val in SEASON_WORDS.items():
            if re.search(rf"\b{word}\b", low):
                seasons.extend(val.split("|"))
        for word, val in TIME_WORDS.items():
            if re.search(rf"\b{word}\b", low):
                times.append(val)
        seasons = [s for s in SEASONS if s in set(seasons)] or list(SEASONS)
        times = [t for t in TIMES if t in set(times)] or list(TIMES)
        if not gender:
            gender = "Unisex"

        lon_txt, _ = _pick(LONGEVITY, getattr(r, "longevity", ""), ("Moderate", 3))
        sil_txt, _ = _pick(SILLAGE, getattr(r, "sillage", ""), ("Moderate", 3))
        note_cols = {}
        for col, key in (("Top_Notes", "top_notes_raw"), ("Middle_Notes", "middle_notes_raw"), ("Base_Notes", "base_notes_raw")):
            atoms = []
            for a in _atoms(getattr(r, key, "")):
                if a == map_note(a) and len(a.split()) >= 3:     # unresolved AND long -> probably several notes
                    atoms.extend(_split_run(a, map_note))
                else:
                    atoms.append(a)
            # a stray em dash or bullet left in a workbook cell is punctuation, not a note
            atoms = [a for a in atoms if re.search(r"[A-Za-z]", a)]
            note_cols[col] = "; ".join(dict.fromkeys(map_note(a) for a in atoms))
            note_cols["Source_" + col] = "; ".join(atoms)

        rows.append({
            "Perfume_ID": getattr(r, "perfume_id"),
            "Profile_Name": f"{fam} No. {family_counter[fam]}",
            "Fragrance_Family": fam,
            "Main_Accords": "; ".join(accords),
            **note_cols,
            "Gender": gender,
            "Season": "; ".join(seasons),
            "Time_Of_Day": "; ".join(times),
            "Climate": "; ".join(dict.fromkeys(CLIMATE[s] for s in seasons)),
            "Longevity": lon_txt,          # the 1-5 scores stay derived in load_data (one source of truth)
            "Sillage": sil_txt,
            "Mood_Vibe": _best(mood_opts, acc_set),
            "Occasion": _best(occ_opts, acc_set),
            "Description": _text(getattr(r, "description", "")),
            "Source": "workbook composition, de-branded; season/gender/longevity/sillage normalised; mood & occasion "
                      "derived from the profile's accords via questionnaire.csv (Q3 / Q1)",
            "Decided_By": "workbook + derived",
        })
    return pd.DataFrame(rows)


def _layer_map(notes: pd.DataFrame | None) -> dict[str, str]:
    """note name -> layer. dataset2 has several rows for some names and they do not always agree, so take the
    note's MOST COMMON class — the same tie-break formula_builder.build_formula() uses, so a profile and the
    formula built from it never disagree about where a material sits."""
    if notes is None:
        return {}
    counts: dict[str, dict[str, int]] = {}
    for r in notes.itertuples():
        name = _text(r.Note_Name)
        layer = _text(r.Volatility_Class).split("/")[0].strip()
        if name and layer:
            counts.setdefault(name, {})
            counts[name][layer] = counts[name].get(layer, 0) + 1
    # ties break on the fixed order below, so the answer never depends on row order in the CSV
    order = {"Top": 0, "Heart": 1, "Base": 2}
    return {n: max(c, key=lambda l: (c[l], -order.get(l, 9))) for n, c in counts.items()}


def book_profiles(formulas: Path, notes: pd.DataFrame | None = None) -> pd.DataFrame:
    """Curtis' type formulas as archetype profiles — the classical structures, each cited to its page.

    `notes` is dataset2: it resolves the book's own spellings ('Musk ketone', 'Vetivert Oil Reunion') to catalogue
    names and, more importantly, says which LAYER each material belongs to. Placing them by Curtis' part sizes put
    the biggest materials in the top note, which is the opposite of how these formulas actually smell."""
    if not formulas.exists():
        return pd.DataFrame()
    f = pd.read_csv(formulas, dtype=str, keep_default_na=False)
    known = set(notes["Note_Name"]) if notes is not None else set()
    map_note = _note_resolver(known) if known else (lambda x: x)
    layer_of = _layer_map(notes)
    fam_name = {"chypre": "Chypre", "fougere": "Aromatic Fougère", "eau de cologne": "Citrus Aromatic",
                "lavender water": "Aromatic", "floral-aldehydic": "Floral Aldehyde"}      # 'oriental' lists accord
                                                                                          # placeholders, not materials
    acc_of = {"chypre": "chypre; mossy; woody; citrus; floral; animalic",
              "fougere": "aromatic; lavender; mossy; woody; sweet",
              "eau de cologne": "citrus; aromatic; fresh; herbal; floral",
              "lavender water": "lavender; aromatic; citrus; musky",
              "floral-aldehydic": "aldehydic; floral; woody; powdery; musky",
              "oriental": "oriental; amber; woody; warm spicy; floral"}
    rows, seen = [], set()
    for name, g in f.groupby("Formula", sort=True):
        fam_key = str(g["Family"].iloc[0]).casefold()
        if fam_key not in fam_name or fam_key in seen:
            continue
        seen.add(fam_key)
        raw = g.sort_values("Parts", key=lambda s: pd.to_numeric(s, errors="coerce"), ascending=False)["Material"].tolist()
        mats = list(dict.fromkeys(map_note(m) for m in raw))
        # place by dataset2's Volatility_Class; a material dataset2 does not know keeps Curtis' own order and goes
        # to the heart, the layer that makes the weakest claim about it
        placed: dict[str, list[str]] = {"Top": [], "Heart": [], "Base": []}
        for m in mats:
            placed.get(layer_of.get(m, "Heart") or "Heart", placed["Heart"]).append(m)
        rows.append({
            "Perfume_ID": f"A{len(rows) + 1:05d}",
            "Profile_Name": f"{fam_name[fam_key]} archetype (Curtis 1994)",
            "Fragrance_Family": fam_name[fam_key],
            "Main_Accords": acc_of[fam_key],
            "Top_Notes": "; ".join(placed["Top"][:5]), "Middle_Notes": "; ".join(placed["Heart"][:5]),
            "Base_Notes": "; ".join(placed["Base"][:5]),
            # the book's own material names, kept exactly as Curtis prints them
            "Source_Top_Notes": "; ".join(raw), "Source_Middle_Notes": "", "Source_Base_Notes": "",
            "Gender": "Unisex", "Season": "Spring; Summer; Fall; Winter", "Time_Of_Day": "Day; Night",
            "Climate": "Temperate; Hot; Cold", "Longevity": "Long lasting", "Longevity_Score": 4,
            "Sillage": "Moderate", "Sillage_Score": 3,
            "Mood_Vibe": "Elegant and classic", "Occasion": "A special occasion",
            "Description": f"The classical {fam_name[fam_key].lower()} structure as taught in the literature, "
                           f"kept as a reference profile for the composer.",
            "Source": str(g["Source"].iloc[0]),
            "Decided_By": "book",
        })
    return pd.DataFrame(rows)


__all__ = ["build", "book_profiles", "_layer_map"]
