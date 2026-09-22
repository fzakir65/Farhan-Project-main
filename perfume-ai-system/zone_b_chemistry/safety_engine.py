"""Task 3 — safety engine (Zone B: deterministic CSV lookups by CAS, no LLM, no I/O).

    result = check_formula(formula, data)                 # formula: build_formula().formula ; data: load_data.load_all()
    result.verdict      -> "PASS" | "ADJUSTED" | "REJECT"
    result.formula      -> the formula with every ceiling applied (may sum to < 100 — Task 4 rebalances)
    result.rejections   -> materials that make the formula unacceptable, each citing its source row
    result.adjustments  -> every cut: From_Pct -> To_Pct, the ceiling, the table + row + legal/IFRA basis that binds
    result.flags        -> specifications (CoA), grade notes, provisional caps, unverifiable notes, step-0 status
    result.pinned       -> CAS numbers sitting at a ceiling (Task 4 must never raise them)
    result.log          -> the ordered, human-readable trace (Rule 7: every decision cites its source row)

Order of checks (CLAUDE.md "SAFETY RULES"):
  0. constituents.csv               natural -> restricted constituent -> fraction. effective % of a constituent =
                                    direct % + sum(natural % x fraction); judged against the constituent's own ceiling.
                                    Naturals keep their share first, the pure molecule takes what is left; if the naturals
                                    alone exceed the ceiling they are scaled down proportionally. Runs after the
                                    per-material ceilings (steps 1, 2, 4) so nothing is cut twice; the optimizer loop
                                    re-runs everything until stable. result.provisional stays True while any fraction
                                    used is Provisional=Yes (literature range rather than a supplier CoA).
  1. regulatory_uk.csv              BANNED (GB or EU) -> REJECT;  RESTRICTED -> ceiling candidate
  2. ifra_limits.csv                Prohibition (all / as_such) -> REJECT;  grade-scoped prohibition -> REJECT unless the
                                    given grade is an allowed one;  Restriction -> ceiling Cat4 / CONCENTRATE_FRACTION;
                                    Specification -> FLAG (supplier CoA)
  3. group_rules.csv                ifra_sum: scale members so the sum meets the limit; ifra_sum_of_fractions (the 8
                                    furocoumarin oils): scale so sum(used/limit) <= 1; ifra_spec_coa: FLAG
  4. safety_caps.csv                ceiling candidate Max_Safe_Percent (+ Grade_Note / Provisional flags)
  5. reaction_rules.csv             olfactory rules with a numeric Sum_Limit are applied (A + k x B <= limit); the rest FLAG
  Per material the LOWEST ceiling from steps 1, 2 and 4 binds; the trace lists the ones that did not bind too.
  A material with no CAS cannot be checked -> WARNING (unverifiable), never silently passed.

Same input -> same output. Nothing here mutates its inputs.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

# IFRA MACs apply to the finished product. We treat the formula as the finished product
# (neat, Category 4). Zone C may later set the true concentrate fraction (0 < f <= 1);
# effective caps become limit / CONCENTRATE_FRACTION. Never set above 1.0, never LLM-supplied.
CONCENTRATE_FRACTION = 1.0

IFRA_CATEGORY = "Category_4_Limit"     # fine fragrance; body spray -> Category 2, hair mist -> min(4, 7B)
ROUND = 4
TOL = 1e-9


@dataclass(frozen=True)
class SafetyFlag:
    code: str            # STEP0_NOT_IMPLEMENTED, NO_CAS, SPECIFICATION, GRADE_NOTE, PROVISIONAL_CAP, PHOTOTOXIC,
                         # REACTION, GROUP_MEMBER_NO_LIMIT, CATEGORY_PROHIBITION, JURISDICTION
    severity: str        # ERROR | WARNING | INFO
    message: str
    note: str = ""
    cas: str = ""
    source: str = ""

    def __str__(self) -> str:
        where = f"{self.note} ({self.cas})" if self.cas else self.note
        return f"{self.severity:<7} {self.code:<24} {where}: {self.message}" + (f"  [{self.source}]" if self.source else "")


@dataclass
class SafetyResult:
    verdict: str
    formula: pd.DataFrame
    rejections: pd.DataFrame
    adjustments: pd.DataFrame
    flags: list[SafetyFlag]
    pinned: set[str]
    log: list[str]
    ceilings: pd.DataFrame
    provisional: bool = True
    concentrate_fraction: float = CONCENTRATE_FRACTION
    total_pct: float = 0.0

    @property
    def safe(self) -> bool:
        """Acceptable to hand to Task 4 / the user (PASS or ADJUSTED). Provisional until step 0 exists."""
        return self.verdict != "REJECT"

    def summary(self) -> str:
        head = f"verdict: {self.verdict}{'  (PROVISIONAL — constituent fractions are literature ranges, not CoA values)' if self.provisional else ''}" \
               f"  total {self.total_pct:.3f} %  concentrate fraction {self.concentrate_fraction:g}"
        lines = [head]
        for r in self.rejections.itertuples(index=False):
            lines.append(f"  REJECT  {r.Note_Name} ({r.CAS}) {r.Pct:.3f} % — {r.Reason}  [{r.Source}]")
        for r in self.adjustments.itertuples(index=False):
            lines.append(f"  CAP     {r.Note_Name} ({r.CAS}) {r.From_Pct:.4f} -> {r.To_Pct:.4f} %  [{r.Source}]")
        for f in self.flags:
            lines.append(f"  {f}")
        return "\n".join(lines)


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------

def _num(x) -> float:
    try:
        v = float(x)
        return v if v == v else float("nan")
    except (TypeError, ValueError):
        return float("nan")


def _isnum(x) -> bool:
    v = _num(x)
    return v == v


def _grade_matches(grade: str, pattern: str) -> bool:
    """`pattern` is a |-separated list of grade words from ifra_limits (crude|gum); match as whole words."""
    if not grade or not pattern:
        return False
    words = [w for w in pattern.split("|") if w]
    return any(re.search(rf"\b{re.escape(w)}\b", grade, re.I) for w in words)


def _effective(limit: float, fraction: float) -> float:
    return min(100.0, limit / fraction)


# ----------------------------------------------------------------------------
# the engine
# ----------------------------------------------------------------------------

def check_formula(formula: pd.DataFrame, data, *, concentrate_fraction: float = CONCENTRATE_FRACTION,
                  grades: dict[str, str] | None = None) -> SafetyResult:
    """Run the safety pass over a formula (columns: Note_Name, CAS, Pct; other columns are carried through).

    data                  load_data.Data (ifra_limits, regulatory, group_rules, safety_caps, reaction_rules)
    concentrate_fraction  concentrate-in-finished-product fraction, 0 < f <= 1 (1.0 = the formula IS the product)
    grades                {CAS: grade text} for materials whose IFRA Standard bans one grade and restricts another
                          ("rectified", "crude", "absolute", "oil", "Tagetes minuta"...). Unknown grade -> REJECT.
    """
    if not (0.0 < concentrate_fraction <= 1.0):
        raise ValueError(f"concentrate_fraction must be in (0, 1], got {concentrate_fraction}")
    grades = {str(k).strip(): str(v) for k, v in (grades or {}).items()}
    flags: list[SafetyFlag] = []
    log: list[str] = []
    rejections: list[dict] = []
    adjustments: list[dict] = []
    ceiling_rows: list[dict] = []
    pinned: set[str] = set()

    f = formula.copy()
    for col in ("Note_Name", "CAS", "Pct"):
        if col not in f.columns:
            raise ValueError(f"formula needs a {col} column")
    f["CAS"] = f["CAS"].fillna("").astype(str).str.strip()
    f["Pct"] = f["Pct"].map(_num)
    f = f.sort_values(["Note_Name", "CAS"], kind="mergesort").reset_index(drop=True)
    f["Safe_Pct"] = f["Pct"]

    # ---- step 0 (data presence; the roll-up itself runs after the per-material ceilings below)
    constituents = getattr(data, "constituents", None)
    provisional = True
    if constituents is None or len(constituents) == 0:
        flags.append(SafetyFlag("STEP0_NOT_IMPLEMENTED", "WARNING",
                                "constituent roll-up (natural -> restricted constituent, IFRA Guidance s1.4) has no data: "
                                "constituents.csv is missing or empty. Provisional=Yes caps in safety_caps.csv stand in.",
                                source="CLAUDE.md step 0"))
        log.append("step 0 constituent roll-up: NO DATA (constituents.csv missing) — result provisional")

    # ---- lookups by CAS (any CAS an IFRA Standard lists)
    ifra = data.ifra_limits
    ifra_by_cas: dict[str, int] = {}
    for i, r in enumerate(ifra.itertuples(index=False)):
        for c in [r.CAS] + list(getattr(r, "All_CAS_List", []) or []):
            c = str(c).strip()
            if c and c not in ifra_by_cas:
                ifra_by_cas[c] = i
    reg = data.regulatory
    reg_by_cas: dict[str, list[int]] = {}
    for i, r in enumerate(reg.itertuples(index=False)):
        reg_by_cas.setdefault(str(r.CAS).strip(), []).append(i)
    caps = data.safety_caps
    caps_by_cas: dict[str, list[int]] = {}
    for i, r in enumerate(caps.itertuples(index=False)):
        c = str(r.CAS).strip()
        if c:
            caps_by_cas.setdefault(c, []).append(i)

    # ---- steps 1, 2, 4 per material: collect ceilings / rejections
    for idx, row in f.iterrows():
        name, cas, pct = row["Note_Name"], row["CAS"], row["Pct"]
        if not cas:
            flags.append(SafetyFlag("NO_CAS", "WARNING", "no CAS — regulatory, IFRA and cap lookups are impossible; treat as UNVERIFIED",
                                    name, "", "dataset2"))
            log.append(f"{name}: no CAS -> UNVERIFIED (no lookup possible)")
            continue
        candidates: list[tuple[float, str]] = []      # (ceiling %, source)

        # 1. regulatory REJECT layer
        for i in reg_by_cas.get(cas, []):
            r = reg.iloc[i]
            src = f"regulatory_uk.csv {r['Material_Name']} [{r['Jurisdiction']}] — {r['Legal_Basis']}"
            if r["Status"] == "BANNED":
                rejections.append({"Note_Name": name, "CAS": cas, "Pct": pct, "Step": 1,
                                   "Reason": f"BANNED in {r['Jurisdiction']} (UK target market: GB or EU ban both reject)", "Source": src})
                log.append(f"{name} ({cas}) REJECTED: {src}")
            elif r["Status"] == "RESTRICTED" and _isnum(r["Fine_Fragrance_Limit_Pct"]):
                lim = _effective(_num(r["Fine_Fragrance_Limit_Pct"]), concentrate_fraction)
                candidates.append((lim, src))
                if r["Jurisdiction"] != "GB+EU":
                    flags.append(SafetyFlag("JURISDICTION", "INFO", f"restriction applies in {r['Jurisdiction']} only; applied anyway (NI follows EU)",
                                            name, cas, src))

        # 2. IFRA
        if cas in ifra_by_cas:
            r = ifra.iloc[ifra_by_cas[cas]]
            src = f"ifra_limits.csv {r['Material_Name']} ({r['IFRA_Key']}, Amendment {r['Amendment']})"
            parts = list(r["Type_Parts"])
            scope = str(r["Prohibition_Scope"])
            if "Prohibition" in parts:
                if scope == "all":
                    rejections.append({"Note_Name": name, "CAS": cas, "Pct": pct, "Step": 2, "Reason": "IFRA PROHIBITION", "Source": src})
                    log.append(f"{name} ({cas}) REJECTED: IFRA prohibition — {src}")
                elif scope == "as_such":
                    rejections.append({"Note_Name": name, "CAS": cas, "Pct": pct, "Step": 2,
                                       "Reason": "IFRA prohibits this substance added AS SUCH (only natural-content contribution is tolerated, via step 0)",
                                       "Source": src})
                    log.append(f"{name} ({cas}) REJECTED: prohibited as such — {src}")
                elif scope == "grade":
                    grade = grades.get(cas, "")
                    if not grade:
                        rejections.append({"Note_Name": name, "CAS": cas, "Pct": pct, "Step": 2,
                                           "Reason": f"grade unknown — IFRA bans grade(s) '{r['Prohibited_Grades']}' and restricts '{r['Allowed_Grades']}' "
                                                     "(CLAUDE.md: unknown grade -> REJECT)", "Source": src})
                        log.append(f"{name} ({cas}) REJECTED: grade unknown — {src}")
                    elif _grade_matches(grade, r["Prohibited_Grades"]):
                        rejections.append({"Note_Name": name, "CAS": cas, "Pct": pct, "Step": 2,
                                           "Reason": f"grade '{grade}' is IFRA-prohibited ('{r['Prohibited_Grades']}')", "Source": src})
                        log.append(f"{name} ({cas}) REJECTED: prohibited grade {grade!r} — {src}")
                    elif not _grade_matches(grade, r["Allowed_Grades"]):
                        rejections.append({"Note_Name": name, "CAS": cas, "Pct": pct, "Step": 2,
                                           "Reason": f"grade '{grade}' is not a recognised allowed grade ('{r['Allowed_Grades']}')", "Source": src})
                        log.append(f"{name} ({cas}) REJECTED: unrecognised grade {grade!r} — {src}")
                    else:
                        log.append(f"{name} ({cas}) grade {grade!r} accepted — {src}")
                elif scope == "category":
                    flags.append(SafetyFlag("CATEGORY_PROHIBITION", "INFO", "IFRA prohibits this only in other product categories; Cat 4 cap applies",
                                            name, cas, src))
            if "Restriction" in parts and _isnum(r[IFRA_CATEGORY]):
                lim = _effective(_num(r[IFRA_CATEGORY]), concentrate_fraction)
                candidates.append((lim, f"{src} {IFRA_CATEGORY} {_num(r[IFRA_CATEGORY]):g} %"
                                        + (f" / concentrate fraction {concentrate_fraction:g}" if concentrate_fraction < 1 else "")))
            if "Specification" in parts:
                flags.append(SafetyFlag("SPECIFICATION", "WARNING", f"IFRA specification: supplier CoA must show compliance — {r['Notes'] or 'see Standard'}",
                                        name, cas, src))
            if str(r["Phototoxic"]) == "Yes":
                flags.append(SafetyFlag("PHOTOTOXIC", "INFO", "phototoxic material — limit already reflects it", name, cas, src))

        # 4. olfactory caps
        for i in caps_by_cas.get(cas, []):
            r = caps.iloc[i]
            src = f"safety_caps.csv {r['Material_Name']} Max_Safe_Percent {_num(r['Max_Safe_Percent']):g} % — {r['Reason']}"
            if _isnum(r["Max_Safe_Percent"]):
                candidates.append((_num(r["Max_Safe_Percent"]), src))
            if str(r["Grade_Note"]).strip():
                flags.append(SafetyFlag("GRADE_NOTE", "WARNING", str(r["Grade_Note"]), name, cas, "safety_caps.csv"))
            if str(r["Provisional"]).strip().lower() == "yes":
                flags.append(SafetyFlag("PROVISIONAL_CAP", "WARNING", "cap derived from typical constituent levels — recompute from the supplier CoA",
                                        name, cas, "safety_caps.csv"))

        if candidates:
            candidates.sort(key=lambda t: (t[0], t[1]))
            ceiling, src = candidates[0]
            others = "; ".join(f"{lim:g} % ({s.split(' — ')[0]})" for lim, s in candidates[1:])
            ceiling_rows.append({"Note_Name": name, "CAS": cas, "Ceiling_Pct": ceiling, "Source": src,
                                 "Not_Binding": others})
            if pct > ceiling + TOL:
                f.loc[idx, "Safe_Pct"] = ceiling
                adjustments.append({"Note_Name": name, "CAS": cas, "Step": 1 if "regulatory" in src else (2 if "ifra" in src else 4),
                                    "From_Pct": pct, "To_Pct": ceiling, "Ceiling_Pct": ceiling, "Source": src})
                log.append(f"{name} ({cas}) {pct:g} % -> {ceiling:g} %: {src}" + (f"  (not binding: {others})" if others else ""))
                pinned.add(cas)
            else:
                log.append(f"{name} ({cas}) {pct:g} % within ceiling {ceiling:g} % ({src.split(' — ')[0]})")
                if abs(pct - ceiling) <= TOL:
                    pinned.add(cas)

    # ---- step 0: constituent roll-up (IFRA Guidance s1.4) on the values after the per-material ceilings
    if constituents is not None and len(constituents):
        used_provisional = False
        by_nat: dict[str, pd.DataFrame] = {c: g for c, g in constituents.groupby("Natural_CAS")}
        contrib: dict[str, list[tuple[int, str, float, float, str]]] = {}     # constituent CAS -> [(idx, natural, fraction, pct_contrib, cname)]
        for idx, row in f.iterrows():
            cas = row["CAS"]
            if cas not in by_nat:
                continue
            g = by_nat[cas]
            words = [w for w in g["Grade_Word"].unique() if w]
            hit = [w for w in words if re.search(rf"\b{re.escape(w)}\b", str(row["Note_Name"]), re.I)]
            if hit:
                sel = g[g["Grade_Word"].isin(hit + [""])]
                how = f"grade '{hit[0]}' read from the note name"
            elif words:
                # grade unknown -> the highest fraction of each constituent across all grades (conservative)
                sel = g.sort_values("Fraction_Used", ascending=False).drop_duplicates("Constituent_CAS")
                how = f"grade not stated (options: {', '.join(words)}) -> worst case of every grade assumed"
                flags.append(SafetyFlag("CONSTITUENT_GRADE_ASSUMED", "WARNING",
                                        f"constituent profile depends on grade ({', '.join(words)}); none in the note name, worst case used",
                                        row["Note_Name"], cas, "constituents.csv"))
            else:
                sel = g
                how = "single profile"
            for c in sel.itertuples(index=False):
                frac = float(c.Fraction_Used)
                amount = float(f.loc[idx, "Safe_Pct"]) * frac
                contrib.setdefault(str(c.Constituent_CAS), []).append((idx, str(row["Note_Name"]), frac, amount, str(c.Constituent_Name)))
                if str(c.Provisional).strip().lower() == "yes":
                    used_provisional = True
            log.append(f"step 0: {row['Note_Name']} ({cas}) contributes " + ", ".join(
                f"{c.Constituent_Name} x{float(c.Fraction_Used):g}" for c in sel.itertuples(index=False)) + f" — {how}")
        for ccas in sorted(contrib):
            entries = contrib[ccas]
            cname = entries[0][4]
            direct_idx = [i for i in f.index if f.loc[i, "CAS"] == ccas]
            direct = float(f.loc[direct_idx, "Safe_Pct"].sum()) if direct_idx else 0.0
            # the constituent's own ceiling: UK/EU restriction, IFRA Cat 4 (or notebox natural-contribution value), olfactory cap
            cands: list[tuple[float, str]] = []
            for i in reg_by_cas.get(ccas, []):
                r = reg.iloc[i]
                if r["Status"] == "RESTRICTED" and _isnum(r["Fine_Fragrance_Limit_Pct"]):
                    cands.append((_effective(_num(r["Fine_Fragrance_Limit_Pct"]), concentrate_fraction), f"regulatory_uk.csv {r['Material_Name']}"))
            if ccas in ifra_by_cas:
                r = ifra.iloc[ifra_by_cas[ccas]]
                if _isnum(r[IFRA_CATEGORY]):
                    cands.append((_effective(_num(r[IFRA_CATEGORY]), concentrate_fraction), f"ifra_limits.csv {r['Material_Name']} ({r['IFRA_Key']})"))
            for i in caps_by_cas.get(ccas, []):
                r = caps.iloc[i]
                if _isnum(r["Max_Safe_Percent"]):
                    cands.append((_num(r["Max_Safe_Percent"]), f"safety_caps.csv {r['Material_Name']}"))
            total_nat = sum(a for _, _, _, a, _ in entries)
            effective = direct + total_nat
            detail = " + ".join(f"{n} {a:.4f}" for _, n, _, a, _ in entries) + (f" + direct {direct:.4f}" if direct else "")
            if not cands:
                banned = [reg.iloc[i]["Material_Name"] for i in reg_by_cas.get(ccas, []) if reg.iloc[i]["Status"] == "BANNED"]
                if banned:
                    # Annex II bans the substance as an *ingredient*; its natural content (benzyl cyanide in tuberose /
                    # orange flower, atranol in mosses) has no numeric ceiling in any table -> visible warning, not silent INFO
                    flags.append(SafetyFlag("CONSTITUENT_BANNED_AS_SUCH", "WARNING",
                                            f"{cname} is BANNED as an ingredient (regulatory_uk.csv: {banned[0]}); {effective:.4f} % arrives as natural content ({detail}) — "
                                            "no numeric ceiling exists for that contribution: confirm with the supplier CoA", cname, ccas, "constituents.csv"))
                    log.append(f"step 0: {cname} ({ccas}) effective {effective:.4f} % — banned as such, natural content has no numeric ceiling")
                    continue
                flags.append(SafetyFlag("CONSTITUENT_NO_CEILING", "INFO", f"effective {effective:.4f} % ({detail}) — no limit in any table", cname, ccas, "constituents.csv"))
                log.append(f"step 0: {cname} ({ccas}) effective {effective:.4f} % — no ceiling to judge against")
                continue
            cands.sort(key=lambda t: (t[0], t[1]))
            ceiling, src = cands[0]
            ceiling_rows.append({"Note_Name": f"[constituent] {cname}", "CAS": ccas, "Ceiling_Pct": ceiling, "Source": src,
                                 "Not_Binding": f"effective {effective:.4f} % = {detail}"})
            if effective <= ceiling + TOL:
                log.append(f"step 0: {cname} ({ccas}) effective {effective:.4f} % <= {ceiling:g} % OK ({detail})")
                continue
            # naturals first: keep them whole if they fit, the pure molecule takes the remainder
            if total_nat <= ceiling + TOL:
                new_direct_total = ceiling - total_nat
                scale = new_direct_total / direct if direct > 0 else 0.0
                for i in direct_idx:
                    before = float(f.loc[i, "Safe_Pct"])
                    f.loc[i, "Safe_Pct"] = before * scale
                    adjustments.append({"Note_Name": f.loc[i, "Note_Name"], "CAS": ccas, "Step": 0, "From_Pct": before, "To_Pct": before * scale,
                                        "Ceiling_Pct": ceiling, "Source": f"{src} — effective {cname} {effective:.4f} % > {ceiling:g} % (naturals contribute {total_nat:.4f} %; constituents.csv)"})
                    pinned.add(ccas)
                log.append(f"step 0: {cname} ({ccas}) effective {effective:.4f} % > {ceiling:g} % -> direct {cname} cut to {new_direct_total:.4f} % ({src})")
            else:
                scale = ceiling / total_nat
                for i in direct_idx:
                    before = float(f.loc[i, "Safe_Pct"])
                    if before > 0:
                        f.loc[i, "Safe_Pct"] = 0.0
                        adjustments.append({"Note_Name": f.loc[i, "Note_Name"], "CAS": ccas, "Step": 0, "From_Pct": before, "To_Pct": 0.0,
                                            "Ceiling_Pct": ceiling, "Source": f"{src} — naturals alone supply {total_nat:.4f} % {cname} > {ceiling:g} % (constituents.csv)"})
                        pinned.add(ccas)
                for i, n, frac, a, _ in entries:
                    before = float(f.loc[i, "Safe_Pct"])
                    f.loc[i, "Safe_Pct"] = before * scale
                    adjustments.append({"Note_Name": n, "CAS": f.loc[i, "CAS"], "Step": 0, "From_Pct": before, "To_Pct": before * scale,
                                        "Ceiling_Pct": ceiling / frac, "Source": f"{src} — {cname} content x{frac:g}: effective {effective:.4f} % > {ceiling:g} %, x{scale:.4f} (constituents.csv)"})
                    pinned.add(f.loc[i, "CAS"])
                log.append(f"step 0: {cname} ({ccas}) naturals supply {total_nat:.4f} % > {ceiling:g} % -> contributors scaled x{scale:.4f}, direct removed ({src})")
        if used_provisional:
            flags.append(SafetyFlag("CONSTITUENT_PROVISIONAL", "WARNING",
                                    "constituent fractions are literature upper bounds (constituents.csv Provisional=Yes) — replace with supplier CoA values",
                                    source="constituents.csv"))
        else:
            provisional = False

    # ---- advisory: Tisserand & Young's own dermal maximum for a natural (second source; reported, never applied)
    ty = getattr(data, "tisserand_maxima", None)
    if ty is not None and len(ty):
        by_cas = {c: g for c, g in ty.groupby("CAS")}
        for idx, row in f.iterrows():
            g = by_cas.get(str(row["CAS"]))
            if g is None:
                continue
            name = str(row["Note_Name"]).casefold()
            note_form = "Absolute" if "absolute" in name else ("Resinoid" if re.search(r"resin|balsam", name) else "Essential oil")
            g = g[(g["Form"] == note_form) | (g["Form"] == "")]            # an absolute's figure never judges an oil, and vice versa
            if "Grade_Word" in g.columns and len(g):
                # a CAS shared by grades (cinnamon bark / leaf, lime expressed / distilled): only the grade the note names may judge it
                hit = g["Grade_Word"].map(lambda w: bool(w) and re.search(rf"\b{re.escape(str(w))}\b", name, re.I) is not None)
                g = g[hit | (g["Grade_Word"] == "")]
            if not len(g):
                continue
            best = g.sort_values("TY_Max_Pct").iloc[0]
            on_skin = float(f.loc[idx, "Safe_Pct"]) * concentrate_fraction
            if on_skin > float(best["TY_Max_Pct"]) + TOL:
                flags.append(SafetyFlag("TY_ADVISORY", "WARNING",
                                        f"{on_skin:.3f} % on skin vs Tisserand & Young's recommended maximum {float(best['TY_Max_Pct']):g} % for "
                                        f"'{best['Profile']}'{' (' + best['Form'].lower() + ')' if best['Form'] else ''}"
                                        f"{' — basis: ' + best['Basis_Constituent'] + ' content' if best['Basis_Constituent'] else ''}"
                                        f"{' — ' + best['Qualifier'] if best['Qualifier'] else ''}; IFRA / UK law remain the ceilings applied here",
                                        row["Note_Name"], str(row["CAS"]), best["Source"]))
                log.append(f"advisory: {row['Note_Name']} {on_skin:.3f} % > T&Y maximum {float(best['TY_Max_Pct']):g} % ({best['Source']}) — not applied")

    # ---- step 3: group rules on the capped values
    for g in data.group_rules.sort_values("Group_Name").itertuples(index=False):
        members = [str(c).strip() for c in (getattr(g, "Members_CAS_List", None) or str(g.Members_CAS).split("|")) if str(c).strip()]
        present = f[f["CAS"].isin(members)]
        if len(present) == 0:
            continue
        src = f"group_rules.csv {g.Group_Name} — {g.Limit_Basis}"
        names = ", ".join(f"{r.Note_Name} {r.Safe_Pct:g} %" for r in present.itertuples(index=False))
        if g.Rule_Type == "ifra_sum":
            total = float(present["Safe_Pct"].sum())
            limit = _effective(_num(g.Limit), concentrate_fraction)
            if total > limit + TOL:
                scale = limit / total
                for i in present.index:
                    before = f.loc[i, "Safe_Pct"]
                    f.loc[i, "Safe_Pct"] = before * scale
                    adjustments.append({"Note_Name": f.loc[i, "Note_Name"], "CAS": f.loc[i, "CAS"], "Step": 3, "From_Pct": before,
                                        "To_Pct": before * scale, "Ceiling_Pct": limit, "Source": f"{src} (sum {total:g} % > {limit:g} %, x{scale:.4f})"})
                    pinned.add(f.loc[i, "CAS"])
                log.append(f"group {g.Group_Name}: {names} sum {total:g} % > {limit:g} % -> members scaled x{scale:.4f}: {src}")
            else:
                log.append(f"group {g.Group_Name}: {names} sum {total:g} % <= {limit:g} % OK")
        elif g.Rule_Type == "ifra_sum_of_fractions":
            fractions, missing = [], []
            for i in present.index:
                cas = f.loc[i, "CAS"]
                lim = _num(ifra.iloc[ifra_by_cas[cas]][IFRA_CATEGORY]) if cas in ifra_by_cas else float("nan")
                if lim == lim and lim > 0:
                    fractions.append((i, f.loc[i, "Safe_Pct"] / _effective(lim, concentrate_fraction)))
                else:
                    missing.append(f.loc[i, "Note_Name"])
            for m in missing:
                flags.append(SafetyFlag("GROUP_MEMBER_NO_LIMIT", "ERROR", f"member of {g.Group_Name} has no individual Cat 4 limit — sum cannot be evaluated", m, "", src))
            total = sum(v for _, v in fractions)
            limit = _num(g.Limit)
            if total > limit + TOL:
                scale = limit / total
                for i, _ in fractions:
                    before = f.loc[i, "Safe_Pct"]
                    f.loc[i, "Safe_Pct"] = before * scale
                    adjustments.append({"Note_Name": f.loc[i, "Note_Name"], "CAS": f.loc[i, "CAS"], "Step": 3, "From_Pct": before,
                                        "To_Pct": before * scale, "Ceiling_Pct": float("nan"),
                                        "Source": f"{src} (sum of used/limit = {total:.3f} > {limit:g}, x{scale:.4f})"})
                    pinned.add(f.loc[i, "CAS"])
                log.append(f"group {g.Group_Name}: {names} sum of fractions {total:.3f} > {limit:g} -> members scaled x{scale:.4f}: {src}")
            else:
                log.append(f"group {g.Group_Name}: {names} sum of fractions {total:.3f} <= {limit:g} OK")
        elif g.Rule_Type == "ifra_spec_coa":
            for r in present.itertuples(index=False):
                flags.append(SafetyFlag("SPECIFICATION", "WARNING", f"{g.Group_Name}: {g.Rule}", r.Note_Name, r.CAS, src))
            log.append(f"group {g.Group_Name}: {names} -> CoA specification flagged: {src}")

    # ---- step 5: reaction rules
    by_cas = {c: i for i, c in zip(f.index, f["CAS"]) if c}
    for r in data.reaction_rules.itertuples(index=False):
        a, b = str(r.CAS_A).strip(), str(r.CAS_B).strip()
        if a in by_cas and b in by_cas:
            ia, ib = by_cas[a], by_cas[b]
            src = f"reaction_rules.csv {r.Material_A} + {r.Material_B} ({r.Rule_Type}) — {r.Limit_Basis}"
            k, lim = _num(getattr(r, "Equivalence_B", float("nan"))), _num(getattr(r, "Sum_Limit_Pct", float("nan")))
            if r.Rule_Type == "olfactory" and k == k and lim == lim:
                pa, pb = f.loc[ia, "Safe_Pct"], f.loc[ib, "Safe_Pct"]
                total = pa + k * pb
                if total > lim + TOL:
                    scale = lim / total
                    for i, before in ((ia, pa), (ib, pb)):
                        f.loc[i, "Safe_Pct"] = before * scale
                        adjustments.append({"Note_Name": f.loc[i, "Note_Name"], "CAS": f.loc[i, "CAS"], "Step": 5, "From_Pct": before,
                                            "To_Pct": before * scale, "Ceiling_Pct": lim,
                                            "Source": f"{src} ({r.Material_A} + {k:g} x {r.Material_B} = {total:g} % > {lim:g} %, x{scale:.4f})"})
                        pinned.add(f.loc[i, "CAS"])
                    log.append(f"reaction {r.Material_A}+{r.Material_B}: {pa:g} + {k:g} x {pb:g} = {total:g} % > {lim:g} % -> both scaled x{scale:.4f}: {src}")
                else:
                    log.append(f"reaction {r.Material_A}+{r.Material_B}: {pa:g} + {k:g} x {pb:g} = {total:g} % <= {lim:g} % OK")
            else:
                sev = "WARNING" if r.Rule_Type == "olfactory" else "INFO"
                flags.append(SafetyFlag("REACTION", sev, f"{r.Issue} — {r.Action}", f"{r.Material_A} + {r.Material_B}", f"{a}+{b}", src))
                log.append(f"reaction {r.Material_A}+{r.Material_B}: flagged ({r.Rule_Type}) — {r.Action}")

    # ---- assemble
    f["Safe_Pct"] = f["Safe_Pct"].round(ROUND)
    rej = pd.DataFrame(rejections, columns=["Note_Name", "CAS", "Pct", "Step", "Reason", "Source"])
    adj = pd.DataFrame(adjustments, columns=["Note_Name", "CAS", "Step", "From_Pct", "To_Pct", "Ceiling_Pct", "Source"])
    ceil = pd.DataFrame(ceiling_rows, columns=["Note_Name", "CAS", "Ceiling_Pct", "Source", "Not_Binding"])
    verdict = "REJECT" if len(rej) else ("ADJUSTED" if len(adj) else "PASS")
    if verdict == "REJECT":
        log.append("VERDICT: REJECT — a banned / prohibited material is present; remove it and rebuild (Zone B never drops a note by itself)")
    else:
        log.append(f"VERDICT: {verdict}" + (" (provisional — constituent data is literature-based or missing)" if provisional else ""))
    order = {"ERROR": 0, "WARNING": 1, "INFO": 2}
    flags = sorted(flags, key=lambda x: (order[x.severity], x.code, x.note, x.cas))
    out = f.drop(columns=["Pct"]).rename(columns={"Safe_Pct": "Pct"})
    out.insert(list(out.columns).index("Pct"), "Input_Pct", f["Pct"])
    return SafetyResult(verdict=verdict, formula=out, rejections=rej, adjustments=adj, flags=flags, pinned=pinned, log=log,
                        ceilings=ceil, provisional=provisional, concentrate_fraction=concentrate_fraction,
                        total_pct=round(float(out["Pct"].sum()), 3))


__all__ = ["check_formula", "SafetyResult", "SafetyFlag", "CONCENTRATE_FRACTION", "IFRA_CATEGORY"]
