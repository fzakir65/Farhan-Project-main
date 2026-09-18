"""Audit the CAS numbers in dataset2 that fail the CAS checksum and propose corrections.

    python data/verify_cas.py              # prints the table, writes cas_corrections.csv (+ PubChem cache)
    python data/verify_cas.py --offline    # use only the cached PubChem answers

A wrong CAS in a safety system is worse than a missing one, so a correction is written with
Apply=Yes ONLY when two independent sources agree. Evidence sources, in order of authority:

  official   the CAS appears in the official IFRA 51st table for a Standard whose name matches the note
  project    the CAS is used for the same material in safety_caps / regulatory_uk / ifra_limits / reaction_rules
  same_note  another row of the SAME dataset2 note carries this (checksum-valid) CAS
  pubchem    PubChem lists this CAS as a synonym of the note name / chemical name (single molecules;
             weak for natural oils, which PubChem often lacks)
  typo       the bad CAS is one edit away (digit substitution, adjacent transposition) from this valid CAS

Decision rules (deterministic given the same inputs):
  FIX   two or more independent sources, one of them official / project / same_note / pubchem
  FIX   typo + pubchem  (a one-digit slip of a number PubChem confirms for this exact name)
  FLAG  everything else — the row keeps its bad CAS until a human supplies a verified one
Rows whose Decided_By is `human` in cas_corrections.csv are never overwritten.

Network is used only by this audit script; the build (`build_datasets.py`) reads the CSV it writes and
stays offline. Nothing here is an LLM.
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import load_data as ld  # noqa: E402  (checksum + placeholders live there)
sys.path.insert(0, str(HERE))
from reconcile_notes import core as name_core  # noqa: E402  (same botanical/grade equivalence as Step 1)

NOTES_CSV = HERE / "dataset2_notes.csv"
OUT_CSV = HERE / "cas_corrections.csv"
CACHE = HERE / "reference" / "pubchem_cas_cache.json"
OFFICIAL = HERE / "reference" / "ifra_51st_standards_overview.csv"
PROJECT_TABLES = {
    "safety_caps": ("safety_caps.csv", "Material_Name", ["CAS"]),
    "regulatory_uk": ("regulatory_uk.csv", "Material_Name", ["CAS"]),
    "ifra_limits": ("ifra_limits.csv", "Material_Name", ["CAS", "All_CAS"]),
    "reaction_rules_A": ("reaction_rules.csv", "Material_A", ["CAS_A"]),
    "reaction_rules_B": ("reaction_rules.csv", "Material_B", ["CAS_B"]),
}
CAS_RE = re.compile(r"^\d{2,7}-\d{2}-\d$")

# Reviewer shortlist for FLAG rows — recollections and structural hints, explicitly UNVERIFIED, never applied.
HINTS = {
    "Coffee": "coffee (Coffea arabica) extract is usually 84650-00-0 — verify (ECHA/supplier CoA)",
    "Honey": "honey is usually 8028-66-8 — verify",
    "Galbanum Resin": "galbanum gum/resin is usually 9000-24-2 — verify",
    "Fir Needle Oil": "Siberian fir needle oil (Abies sibirica) is usually 8021-29-2 (one digit from the bad value) — verify",
    "Violet Leaf": "violet leaf absolute is usually 8024-08-6 — verify; the row's Chemical_Name 'Ionones' is also wrong for a leaf absolute",
    "Pink Pepper Oil": "safety_caps.csv already uses 68917-52-2 (Schinus molle oil) for this material",
    "Okoumal": "PubChem lists three isomer CAS; suppliers usually cite 131812-67-4",
    "Habanolide": "111879-80-2 is PubChem's (E)-isomer; 34902-57-3 (already on the note) is the unspecified-isomer CAS. 33704-61-9 on this note is CASHMERAN's CAS — remove it",
    "Iris Butter": "iris butter == orris butter; dataset2 'Orris Butter' carries 8002-73-1",
    "Orris Absolute": "orris absolute is usually 90045-89-9 (already on 'Iris (Orris)') — verify",
    "Champaca Absolute": "8006-71-5 is pasted on both Champaca and Gardenia — wrong for at least one; no verified CAS found",
    "Gardenia Absolute": "8006-71-5 is pasted on both Champaca and Gardenia — wrong for at least one; no verified CAS found",
    "Suederal": "1001252-96-7 is pasted on both Suederal and Amber Xtreme — wrong for at least one; PubChem has no entry",
    "Amber Xtreme": "1001252-96-7 is pasted on both Suederal and Amber Xtreme — wrong for at least one; PubChem has no entry",
    "Palo Santo": "both Palo Santo rows share body 959130-05 with different check digits; the only valid check digit gives 959130-05-3 — verify",
    "Palo Santo Oil": "both Palo Santo rows share body 959130-05 with different check digits; the only valid check digit gives 959130-05-3 — verify",
}
PUBCHEM = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{}/synonyms/JSON"
RICH_RE = re.compile(r"\s+(rich|derivatives|esters|compounds|extract)$", re.I)
PRIORITY = {"official": 6, "project": 5, "pubchem": 4, "checkdigit": 3, "sibling": 2, "same_note": 1, "typo": 1}


shared_cas_conflicts = ld.shared_cas_conflicts   # single definition, shared with load_data's WARNING


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------

def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()


def typo_neighbours(cas: str) -> set[str]:
    """Checksum-valid CAS numbers one edit away: one digit substituted, or two adjacent digits swapped.
    (Keeps the segment layout — a wrong hyphen position is a different kind of error.)"""
    digits = cas.replace("-", "")
    seg = [len(p) for p in cas.split("-")]
    out: set[str] = set()

    def rebuild(d: str) -> str:
        return f"{d[:seg[0]]}-{d[seg[0]:seg[0] + seg[1]]}-{d[seg[0] + seg[1]:]}"

    for i in range(len(digits)):
        for c in "0123456789":
            if c != digits[i]:
                cand = rebuild(digits[:i] + c + digits[i + 1:])
                if ld.is_valid_cas(cand):
                    out.add(cand)
    for i in range(len(digits) - 1):
        if digits[i] != digits[i + 1]:
            d = list(digits)
            d[i], d[i + 1] = d[i + 1], d[i]
            cand = rebuild("".join(d))
            if ld.is_valid_cas(cand):
                out.add(cand)
    out.discard(cas)
    return out


class PubChem:
    def __init__(self, offline: bool):
        self.offline = offline
        self.cache: dict[str, dict] = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
        self.dirty = False

    def synonyms(self, name: str) -> dict:
        """{'cid': int|None, 'cas': [..], 'title': str} for a name; cached."""
        key = name.strip().lower()
        if key in self.cache:
            return self.cache[key]
        if self.offline:
            return {"cid": None, "cas": [], "title": "", "note": "not cached"}
        url = PUBCHEM.format(urllib.parse.quote(name))
        req = urllib.request.Request(url, headers={"User-Agent": "perfume-ai-system CAS audit"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                d = json.loads(r.read().decode())
            info = d["InformationList"]["Information"][0]
            syn = info.get("Synonym", [])
            res = {"cid": info.get("CID"), "cas": [s for s in syn if CAS_RE.match(s)], "title": syn[0] if syn else ""}
        except urllib.error.HTTPError as e:
            res = {"cid": None, "cas": [], "title": "", "note": f"HTTP {e.code}"}
        except Exception as e:  # network hiccup: record and move on, never guess
            res = {"cid": None, "cas": [], "title": "", "note": type(e).__name__}
        time.sleep(0.25)   # PubChem asks for <= 5 requests/s
        self.cache[key] = res
        self.dirty = True
        return res

    def save(self):
        if self.dirty:
            CACHE.write_text(json.dumps(self.cache, indent=1, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def _original_cas(notes: pd.DataFrame) -> pd.DataFrame:
    """dataset2 on disk already has the applied corrections; always audit the WORKBOOK values (Source_CAS),
    otherwise a re-run would drop every applied fix from cas_corrections.csv and the build would undo it."""
    if "Source_CAS" in notes.columns:
        notes = notes.copy()
        notes["CAS"] = notes["Source_CAS"]
    return notes


def load_official() -> pd.DataFrame:
    df = pd.read_csv(OFFICIAL, skiprows=2, dtype=str, keep_default_na=False)
    name_col = next(c for c in df.columns if c.strip().lower() == "name of the ifra standard")
    cas_col = next(c for c in df.columns if c.strip().lower() == "cas numbers")
    syn_col = next(c for c in df.columns if c.strip().lower() == "synonyms")
    rows = []
    for _, r in df.iterrows():
        cas = [c.strip() for c in re.split(r"[\n;|,]+", r[cas_col]) if CAS_RE.match(c.strip())]
        names = [r[name_col]] + [s.strip() for s in re.split(r"[\n;]+", r[syn_col]) if s.strip()]
        rows.append({"name": r[name_col], "norms": {norm(x) for x in names if x}, "cas": cas})
    return pd.DataFrame(rows)


def load_project_cas() -> list[tuple[str, str, str]]:
    """(table, material name, CAS) for every CAS the hand-maintained / generated safety tables carry."""
    out = []
    for tag, (fn, name_col, cas_cols) in PROJECT_TABLES.items():
        df = pd.read_csv(HERE / fn, dtype=str, keep_default_na=False)
        for _, r in df.iterrows():
            for c in cas_cols:
                for cas in re.split(r"[|;]", r.get(c, "")):
                    cas = cas.strip()
                    if CAS_RE.match(cas):
                        out.append((tag.split("_")[0], r[name_col], cas))
    return out


# ----------------------------------------------------------------------------
# audit
# ----------------------------------------------------------------------------

def audit(offline: bool = False) -> pd.DataFrame:
    notes = _original_cas(pd.read_csv(NOTES_CSV, dtype=str, keep_default_na=False)).drop_duplicates()
    notes["valid"] = notes["CAS"].map(ld.is_valid_cas)
    bad = notes[(notes["CAS"] != "") & ~notes["CAS"].str.lower().isin(ld.CAS_PLACEHOLDERS) & ~notes["valid"]]
    bad = bad.drop_duplicates(["Note_ID", "CAS"])

    official = load_official()
    project = load_project_cas()
    pc = PubChem(offline)
    suspect = shared_cas_conflicts(notes)            # valid CAS pasted onto unrelated notes -> untrustworthy
    notes["core"] = notes["Note_Name"].map(name_core)
    # check-digit-only errors: the same body appears with DIFFERENT check digits on rows of the SAME material
    # (identical pastes such as 8006-71-5 on Champaca and Gardenia corroborate nothing)
    bad_body = bad.assign(body=bad["CAS"].str.rsplit("-", n=1).str[0], core=bad["Note_Name"].map(name_core))
    corroborated = {(b, c) for (b, c), g in bad_body.groupby(["body", "core"]) if g["CAS"].nunique() >= 2}
    rows = []
    for r in bad.itertuples(index=False):
        evidence: dict[str, set[str]] = {}          # candidate CAS -> set of source tags

        def add(cas: str, tag: str):
            if CAS_RE.match(cas) and ld.is_valid_cas(cas):
                evidence.setdefault(cas, set()).add(tag)

        # same_note: other valid rows of this note (discounted when that CAS is pasted on unrelated notes too)
        same = notes[(notes["Note_ID"] == r.Note_ID) & notes["valid"] & (notes["CAS"] != "")]["CAS"].unique()
        for c in same:
            add(c, "same_note?" if c in suspect else "same_note")
        # sibling: another dataset2 note of the same botanical/grade family (Iris Butter ~ Orris Butter)
        sib = notes[(notes["core"] == name_core(r.Note_Name)) & (notes["Note_ID"] != r.Note_ID) & notes["valid"] & (notes["CAS"] != "")]
        for c in sib["CAS"].unique():
            add(c, "sibling?" if c in suspect else "sibling")
        # check digit: body corroborated by a second bad row -> exactly one valid check digit exists
        b = r.CAS.rsplit("-", 1)[0]
        if (b, name_core(r.Note_Name)) in corroborated:
            for d in "0123456789":
                add(f"{b}-{d}", "checkdigit")
        # official IFRA table by name
        for o in official.itertuples(index=False):
            if norm(r.Note_Name) in o.norms or (norm(r.Chemical_Name) == norm(o.name) and not RICH_RE.search(r.Chemical_Name)):
                for c in o.cas:
                    add(c, "official")
        # project tables by name
        for tag, name, c in project:
            if norm(name) == norm(r.Note_Name) or norm(name) == norm(r.Chemical_Name):
                add(c, f"project:{tag}")
        # PubChem by note name, chemical name (single molecules only), botanical source
        names: set[str] = set()
        defined = r.Natural_Source.strip().lower() == "synthetic" or norm(r.Chemical_Name) == norm(r.Note_Name)
        if defined:
            names.add(r.Note_Name)
            chem = RICH_RE.sub("", r.Chemical_Name).strip()
            if chem and norm(chem) != norm(r.Note_Name) and not re.search(r"\b(rich|blend|derivatives|esters|compounds)\b", r.Chemical_Name, re.I):
                names.add(chem)
        pubchem_hits = {}
        for nm in sorted(names):
            res = pc.synonyms(nm)
            if res["cas"]:
                pubchem_hits[nm] = res["cas"]
                for c in res["cas"]:
                    add(c, "pubchem")
        # typo neighbours — only count as evidence when the neighbour is ALSO known from elsewhere
        for c in typo_neighbours(r.CAS):
            if c in evidence and "checkdigit" not in evidence[c]:   # a check-digit repair is already a 1-edit
                evidence[c].add("typo")

        # decide. Independent origins: ifra_limits is generated from the official table -> one origin;
        # '?'-tagged sources (CAS also pasted on unrelated notes) never count towards a FIX.
        def origins(src: set[str]) -> set[str]:
            out = set()
            for t in src:
                if t.endswith("?"):
                    continue
                out.add("official" if t.startswith("project:ifra") else t.split(":")[0])
            return out

        best, best_src, action, conf = "", set(), "FLAG", 0.0
        ranked = sorted(evidence.items(),
                        key=lambda kv: (-len(origins(kv[1])), -sum(PRIORITY.get(t.rstrip("?").split(":")[0], 0) for t in kv[1]), kv[0]))
        for cas, src in ranked:
            ind = origins(src)
            if len(ind) >= 2 and (ind & {"official", "project", "pubchem", "same_note"}):
                best, best_src, action = cas, src, "FIX"
                conf = 0.95 if ("official" in ind or "project" in ind) else 0.90
                break
        trusted = [(c, src) for c, src in ranked if origins(src)]
        if action == "FLAG" and trusted:
            cas, src = trusted[0]                     # a single source is a recommendation, not a fix
            best, best_src = cas, src
            conf = 0.75 if "checkdigit" in src else 0.6
        elif action == "FLAG" and ranked:
            best, best_src, conf = "", set(), 0.0     # only suspect candidates: say so, recommend nothing
        fixable = [c for c, s in evidence.items() if len(origins(s)) >= 2]
        if action == "FIX" and len(fixable) > 1:
            action, conf = "FLAG", 0.5
        reason = "; ".join(f"{c} <- {','.join(sorted(s))}" for c, s in ranked[:4]) or "no candidate from any source"
        if ranked and not trusted:
            reason = "only suspect candidates (CAS also pasted on unrelated notes): " + reason
        if pubchem_hits:
            reason += " | PubChem: " + "; ".join(f"{k}: {','.join(v[:3])}" for k, v in pubchem_hits.items())
        if action == "FLAG" and len(fixable) > 1:
            reason = "AMBIGUOUS — several candidates each backed by two sources: " + reason
        rows.append({
            "Note_ID": r.Note_ID, "Note_Name": r.Note_Name, "Chemical_Name": r.Chemical_Name,
            "Bad_CAS": r.CAS, "Corrected_CAS": best if action == "FIX" else "",
            "Recommended_CAS": best, "Action": action, "Confidence": f"{conf:.2f}",
            "Evidence": ",".join(sorted(best_src)), "Detail": reason,
            "Apply": "Yes" if action == "FIX" else "No", "Decided_By": "auto",
            "Note": HINTS.get(r.Note_Name, "") if action == "FLAG" else "",
        })
    pc.save()
    out = pd.DataFrame(rows).sort_values(["Action", "Note_Name", "Bad_CAS"]).reset_index(drop=True)
    return out


def merge_with_existing(fresh: pd.DataFrame, path: Path = OUT_CSV) -> pd.DataFrame:
    if not path.exists():
        return fresh
    old = pd.read_csv(path, dtype=str, keep_default_na=False)
    human = old[old["Decided_By"].str.lower().isin(["human", "ai"])]     # decided rows (human or AI) survive re-runs
    keys = set(zip(human["Note_ID"], human["Bad_CAS"]))
    keep = fresh[~fresh.apply(lambda r: (r["Note_ID"], r["Bad_CAS"]) in keys, axis=1)]
    return pd.concat([human[fresh.columns.intersection(human.columns)], keep], ignore_index=True)


def to_markdown(df: pd.DataFrame) -> str:
    lines = []
    for action, title in (("FIX", "FIX — applied (two independent sources agree)"), ("FLAG", "FLAG — not fixed, human must verify")):
        sub = df[df["Action"] == action]
        lines.append(f"\n### {title} ({len(sub)} rows)\n")
        lines.append("| note | bad CAS | corrected / recommended | conf | evidence | detail |")
        lines.append("|---|---|---|---:|---|---|")
        for r in sub.itertuples(index=False):
            lines.append(f"| {r.Note_Name} ({r.Note_ID}) | {r.Bad_CAS} | {r.Recommended_CAS or '—'} | {r.Confidence} | {r.Evidence or '—'} | {r.Detail} |")
    return "\n".join(lines)


def shared_cas_markdown() -> str:
    notes = pd.read_csv(NOTES_CSV, dtype=str, keep_default_na=False).drop_duplicates()   # current (corrected) data
    notes["valid"] = notes["CAS"].map(ld.is_valid_cas)
    conf = shared_cas_conflicts(notes)
    lines = [f"\n### Checksum-VALID CAS shared by UNRELATED notes ({len(conf)} numbers) — a paste error the checksum cannot see; reported, not fixed\n",
             "| CAS | notes using it |", "|---|---|"]
    for cas, names in sorted(conf.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        lines.append(f"| {cas} | {'; '.join(names)} |")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    offline = "--offline" in argv
    fresh = audit(offline=offline)
    merged = merge_with_existing(fresh)
    merged.to_csv(OUT_CSV, index=False, encoding="utf-8")
    print(to_markdown(merged))
    print(shared_cas_markdown())
    print(f"\n{len(merged)} bad CAS rows: {(merged['Action'] == 'FIX').sum()} FIX, {(merged['Action'] == 'FLAG').sum()} FLAG -> {OUT_CSV.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
