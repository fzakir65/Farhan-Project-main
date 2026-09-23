"""Zone A — the guided path: a questionnaire whose picks accumulate into Preferences (no text, no LLM, no model).

    qs = load_questionnaire()                                   # data/questionnaire.csv -> [Question]
    prefs = answer({"Q1": ["b"], "Q3": ["d"], "Q4": ["i", "r", "y"], "Q5": ["a"], "Q6": ["c"], "Q7": ["a"]})
    prefs.accords -> ordered by accumulated weight; prefs.avoid, .strength, .gender, .season, .family; prefs.trace explains

Each option carries 'term:weight' pairs; picks add up (a smell chosen twice through two questions counts more), avoided
terms are removed, strength / gender / season come from the single-choice questions. The result is exactly what the
free-text path produces, so matcher.match() and invention.invent() need nothing new. Every completed questionnaire is
also a clean labelled record (data/logs/questionnaire_log.csv) for the future model.
"""
from __future__ import annotations

import csv
import datetime as _dt
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from .input_handler import Preferences


@dataclass
class Option:
    id: str
    text: str
    pairs: list[tuple[str, float]]
    family: str | None
    gender: str | None
    season: str | None
    strength: int | None
    avoid: list[str]


@dataclass
class Question:
    id: str
    text: str
    type: str                      # single | multi
    max_picks: int
    options: list[Option] = field(default_factory=list)

    def option(self, oid: str) -> Option | None:
        return next((o for o in self.options if o.id == oid), None)


def load_questionnaire(path: str | Path | None = None) -> list[Question]:
    if path is None:
        from load_data import DATA_DIR
        path = Path(DATA_DIR) / "questionnaire.csv"
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    out: dict[str, Question] = {}
    for r in df.itertuples(index=False):
        q = out.setdefault(r.Question_ID, Question(r.Question_ID, r.Question, r.Type, int(r.Max_Picks or 1)))
        pairs = []
        for item in str(r.Accord_Terms).split(";"):
            if ":" in item:
                t, w = item.rsplit(":", 1)
                pairs.append((t.strip(), float(w)))
        q.options.append(Option(r.Option_ID, r.Option, pairs, r.Family or None, r.Gender or None, r.Season or None,
                                int(r.Strength) if str(r.Strength).strip() else None, [a for a in str(r.Avoid).split(";") if a]))
    return list(out.values())


def answer(picks: dict[str, list[str] | str], questions: list[Question] | None = None, log: bool = True) -> Preferences:
    """picks: {question id: [option ids]} (a single id string is accepted). Unknown ids are reported in prefs.notes, never fatal."""
    qs = {q.id: q for q in (questions or load_questionnaire())}
    weights: dict[str, float] = {}
    avoid: set[str] = set()
    p = Preferences(source="questionnaire")
    strengths: list[int] = []          # implicit (an occasion implies a strength)
    explicit: list[int] = []           # the strength question itself — it wins
    for qid, chosen in picks.items():
        q = qs.get(qid)
        if q is None:
            p.notes.append(f"unknown question {qid!r}")
            continue
        ids = [chosen] if isinstance(chosen, str) else list(chosen)
        if q.type == "single":
            ids = ids[:1]
        ids = ids[:q.max_picks]
        for oid in ids:
            o = q.option(oid)
            if o is None:
                p.notes.append(f"unknown option {qid}{oid!r}")
                continue
            for t, w in o.pairs:
                weights[t] = weights.get(t, 0.0) + w
            avoid.update(o.avoid)
            if o.family:
                p.family = p.family or o.family
            if o.gender:
                p.gender = o.gender
            if o.season:
                p.season = o.season
            if o.strength is not None:
                (explicit if not o.pairs else strengths).append(o.strength)
            p.trace.append(f"{qid}{oid} '{o.text}' -> " + (";".join(f"{t}:{w:g}" for t, w in o.pairs) or "-") + (f" avoid {', '.join(o.avoid)}" if o.avoid else "")
                           + (f" strength {o.strength}" if o.strength is not None else "") + (f" {o.gender}" if o.gender else "") + (f" {o.season}" if o.season else ""))
    for a in avoid:
        weights.pop(a, None)
    mx = max(weights.values()) if weights else 1.0
    p.weights = {t: round(w / mx, 3) for t, w in sorted(weights.items(), key=lambda kv: (-kv[1], kv[0]))}
    p.accords = list(p.weights)
    p.avoid = sorted(avoid)
    use = explicit or strengths        # "How strong should it be?" overrides what an occasion implies
    p.strength = round(sum(use) / len(use)) if use else None
    if p.is_empty():
        p.notes.append("no preferences picked")
    if log:
        try:
            _log(picks, p)
        except Exception:  # noqa: BLE001
            pass
    return p


def _log(picks: dict, p: Preferences) -> None:
    from load_data import DATA_DIR
    path = Path(DATA_DIR) / "logs" / "questionnaire_log.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["Timestamp", "Picks", "Accords", "Avoid", "Strength", "Gender", "Season"])
        if new:
            w.writeheader()
        w.writerow({"Timestamp": _dt.datetime.now().isoformat(timespec="seconds"),
                    "Picks": ";".join(f"{q}={','.join([v] if isinstance(v, str) else v)}" for q, v in picks.items()),
                    "Accords": "|".join(p.accords), "Avoid": "|".join(p.avoid), "Strength": p.strength if p.strength is not None else "",
                    "Gender": p.gender or "", "Season": p.season or ""})


def parse_answers(spec: str) -> dict[str, list[str]]:
    """'Q1=b;Q4=i,r,y;Q6=c' -> {'Q1': ['b'], 'Q4': ['i','r','y'], 'Q6': ['c']} (the CLI form)."""
    picks: dict[str, list[str]] = {}
    for part in spec.split(";"):
        if "=" in part:
            q, v = part.split("=", 1)
            picks[q.strip().upper()] = [x.strip().lower() for x in v.split(",") if x.strip()]
    return picks


__all__ = ["Question", "Option", "load_questionnaire", "answer", "parse_answers"]
