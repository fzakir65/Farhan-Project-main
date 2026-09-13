"""Build the v5 augmented master workbook from v4.

Adds synthetic training_examples rows for rare ACTIVE accords (present as a
primary target but with < MIN_COUNT examples), bringing each up to MIN_COUNT.
Dead accords (never a target) are left dead per the plan ("keep in catalog,
de-emphasise"). Every synthetic row is flagged `is_augmented = 1` and given a
REQ-AUG-… request_id; v4 is never modified. Downstream, preprocessing must
route is_augmented rows to the train split only — never val/test.

Generation mirrors how v4 itself was templated (EDA section 4): donor rows
from the same accord supply descriptor/occasion/secondary structure; text is
rebuilt from the observed template families; demographics are resampled from
the global distributions so no fake demographic->accord correlation is
injected; avoid tokens never contradict the descriptor set (EDA section 13).

Run: python preprocessing/build_v5_augmented.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
V4_FILE = PROJECT_ROOT / "perfume_system_master_training_dynamic_v4_10000.xlsx"
V5_FILE = PROJECT_ROOT / "perfume_system_master_training_dynamic_v5_augmented.xlsx"

SEED = 42
MIN_COUNT = 30

rng = np.random.default_rng(SEED)


def bucket_of(age: int) -> str:
    if age <= 17:
        return "13-17"
    if age <= 24:
        return "18-24"
    if age <= 34:
        return "25-34"
    if age <= 44:
        return "35-44"
    return "45+"


LEAKY_TEMPLATES_2 = [
    "{age}yo and I'm after {d1}/{d2} vibes—nothing basic.",
    "I want something that feels {d1} and {d2}.",
    "Age {age}. Give me a scent that screams {d1} but stays {d2}.",
    "Turning {age} soon. I want something that feels {d1} and {d2}.",
    "I'm {age} and Can you do {d1} with a twist of {d2}?",
]
LEAKY_TEMPLATES_1 = [
    "{age}yo and I'm after {d1} vibes—nothing basic.",
    "I want something that feels {d1}.",
    "Age {age}. I want something that feels {d1}.",
]
OCCASION_TEMPLATES = [
    "I'm {age} and Looking for something that fits {occ}.",
    "{age} here. Looking for something that fits {occ}.",
    "Age {age}. Looking for something that fits {occ}.",
    "Turning {age} soon. Looking for something that fits {occ}.",
]


def make_text(age: int, descs: list[str], occ: str, avoids: list[str]) -> str:
    parts = []
    if descs and rng.random() < 0.5:
        if len(descs) >= 2:
            d1, d2 = rng.choice(descs, size=2, replace=False)
            parts.append(str(rng.choice(LEAKY_TEMPLATES_2)).format(
                age=age, d1=d1, d2=d2))
        else:
            parts.append(str(rng.choice(LEAKY_TEMPLATES_1)).format(
                age=age, d1=descs[0]))
    else:
        parts.append(str(rng.choice(OCCASION_TEMPLATES)).format(age=age, occ=occ))
    if avoids and rng.random() < 0.5:
        a = rng.choice(avoids)
        parts.append(str(rng.choice([
            "no {a}.", "Avoid {a} completely.", "If it's {a}, I'm out.",
        ])).format(a=a))
    if descs and rng.random() < 0.25:
        parts.append(f"Prefer {rng.choice(descs)} in the drydown.")
    if rng.random() < 0.15:
        parts.append("Background: any.")
    return " ".join(parts)


def main() -> None:
    print(f"reading {V4_FILE.name} ...")
    xl = pd.ExcelFile(V4_FILE)
    sheets = {name: xl.parse(name) for name in xl.sheet_names}
    tr = sheets["training_examples"].copy()
    tr["is_augmented"] = 0

    counts = tr["target_accord_id_primary"].value_counts()
    rare = counts[counts < MIN_COUNT]
    print(f"active accords: {len(counts)} | below {MIN_COUNT}: {len(rare)} "
          f"| rows to generate: {int((MIN_COUNT - rare).sum())}")

    global_ages = tr["age"].to_numpy()
    global_rows = tr  # demographic pools
    avoid_pool = sorted({t.strip() for s in tr["avoid_notes_csv"].dropna()
                         for t in str(s).split(",") if t.strip()})

    new_rows, seq = [], 1
    for accord, n_have in rare.items():
        donors = tr[tr["target_accord_id_primary"] == accord]
        desc_pool = sorted({t.strip() for s in donors["descriptor_tags_csv"].dropna()
                            for t in str(s).split(",") if t.strip()})
        occ_pool = donors["occasion_tag"].dropna().astype(str).tolist()
        for _ in range(MIN_COUNT - n_have):
            donor = donors.iloc[int(rng.integers(len(donors)))]
            descs = [t.strip() for t in str(donor["descriptor_tags_csv"] or "")
                     .split(",") if t.strip() and str(donor["descriptor_tags_csv"]) != "nan"]
            if len(descs) >= 2 and rng.random() < 0.3:
                descs.remove(str(rng.choice(descs)))
            extra = [d for d in desc_pool if d not in descs]
            if extra and rng.random() < 0.3:
                descs.append(str(rng.choice(extra)))
            occ = str(rng.choice(occ_pool)) if occ_pool else str(donor["occasion_tag"])
            age = int(rng.choice(global_ages))
            demo = global_rows.iloc[int(rng.integers(len(global_rows)))]
            avoid_ok = [a for a in avoid_pool if a not in descs]
            n_avoid = int(rng.integers(0, 3)) if rng.random() < 0.75 else 0
            avoids = (list(rng.choice(avoid_ok, size=min(n_avoid, len(avoid_ok)),
                                      replace=False)) if n_avoid else [])
            new_rows.append({
                "request_id": f"REQ-AUG-{seq:04d}",
                "created_at": pd.Timestamp("2026-07-14"),
                "user_text": make_text(age, descs, occ, avoids),
                "age": age,
                "age_bucket": bucket_of(age),
                "gender": demo["gender"],
                "region": demo["region"],
                "background_tag": demo["background_tag"],
                "occasion_tag": occ,
                "descriptor_tags_csv": ",".join(descs) if descs else np.nan,
                "avoid_notes_csv": ",".join(avoids) if avoids else np.nan,
                "target_accord_id_primary": accord,
                "target_accord_id_secondary": donor["target_accord_id_secondary"],
                "target_perfume_id_reference": np.nan,
                "user_rating_1_5": np.nan,
                "accepted_flag": np.nan,
                "notes": np.nan,
                "is_augmented": 1,
            })
            seq += 1

    aug = pd.DataFrame(new_rows)
    out = pd.concat([tr, aug], ignore_index=True)
    sheets["training_examples"] = out

    dup = out["request_id"].duplicated().sum()
    new_counts = out["target_accord_id_primary"].value_counts()
    assert dup == 0, "duplicate request ids"
    assert new_counts.min() >= MIN_COUNT, "some accord still below MIN_COUNT"
    assert len(out) == len(tr) + len(aug)

    print(f"writing {V5_FILE.name}: {len(tr)} original + {len(aug)} augmented rows; "
          f"min per-accord count now {new_counts.min()}")
    with pd.ExcelWriter(V5_FILE, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name, index=False)
    print("done.")


if __name__ == "__main__":
    main()
