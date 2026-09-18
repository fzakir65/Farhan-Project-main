"""Verify dataset2's chemistry columns against PubChem (Molecular_Weight, LogP) for every defined molecule.

    python data/enrich_pubchem.py             # fetch what is not cached yet -> reference/pubchem_properties.csv
    python data/enrich_pubchem.py --offline   # only report from the cache

Scope: notes whose CAS is checksum-valid AND that are single substances (Natural_Source 'Synthetic' or the
Chemical_Name is the note name). Natural complex substances (oils, absolutes) have no PubChem compound record and
are skipped. PubChem's computed XLogP is compared with dataset2 LogP; exact MolecularWeight with Molecular_Weight.
`load_data` turns disagreements into WARNINGs (data.pubchem_mismatches). Network only here; the build stays offline.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
NOTES_CSV = HERE / "dataset2_notes.csv"
OUT = HERE / "reference" / "pubchem_properties.csv"
URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{}/property/MolecularWeight,XLogP,IUPACName,MolecularFormula/JSON"


def fetch(cas: str) -> dict:
    req = urllib.request.Request(URL.format(urllib.parse.quote(cas)), headers={"User-Agent": "perfume-ai-system chemistry audit"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            p = json.loads(r.read().decode())["PropertyTable"]["Properties"][0]
        return {"CAS": cas, "CID": p.get("CID"), "PubChem_MW": p.get("MolecularWeight"), "PubChem_XLogP": p.get("XLogP", ""),
                "IUPAC_Name": p.get("IUPACName", ""), "Formula": p.get("MolecularFormula", ""), "Status": "ok"}
    except urllib.error.HTTPError as e:
        return {"CAS": cas, "CID": "", "PubChem_MW": "", "PubChem_XLogP": "", "IUPAC_Name": "", "Formula": "", "Status": f"HTTP {e.code}"}
    except Exception as e:
        return {"CAS": cas, "CID": "", "PubChem_MW": "", "PubChem_XLogP": "", "IUPAC_Name": "", "Formula": "", "Status": type(e).__name__}


def defined_molecules(notes: pd.DataFrame) -> pd.DataFrame:
    sys.path.insert(0, str(HERE.parent))
    from load_data import is_valid_cas, normalize_name
    n = notes[(notes["CAS"] != "") & notes["CAS"].map(is_valid_cas)].copy()
    single = (n["Natural_Source"].str.strip().str.lower() == "synthetic") | \
             (n["Chemical_Name"].map(normalize_name) == n["Note_Name"].map(normalize_name))
    return n[single].drop_duplicates("CAS")


def main(argv: list[str]) -> int:
    offline = "--offline" in argv
    notes = pd.read_csv(NOTES_CSV, dtype=str, keep_default_na=False)
    targets = defined_molecules(notes)
    cache = pd.read_csv(OUT, dtype=str, keep_default_na=False) if OUT.exists() else pd.DataFrame(columns=["CAS", "CID", "PubChem_MW", "PubChem_XLogP", "IUPAC_Name", "Formula", "Status", "Fetched"])
    have = set(cache["CAS"])
    todo = [c for c in targets["CAS"] if c not in have]
    print(f"{len(targets)} defined molecules with a valid CAS; {len(have)} cached; {len(todo)} to fetch{' (offline: skipped)' if offline else ''}")
    rows = []
    if not offline:
        for i, cas in enumerate(todo, 1):
            r = fetch(cas)
            r["Fetched"] = time.strftime("%Y-%m-%d")
            rows.append(r)
            time.sleep(0.22)
            if i % 50 == 0:
                print(f"  {i}/{len(todo)}")
    cache = pd.concat([cache, pd.DataFrame(rows)], ignore_index=True)
    cache.to_csv(OUT, index=False, encoding="utf-8")
    ok = cache[cache["Status"] == "ok"]
    print(f"cache: {len(cache)} rows, {len(ok)} resolved -> {OUT.relative_to(HERE)}")
    # compare
    m = targets.merge(ok, on="CAS", how="inner")
    m["ds_mw"] = pd.to_numeric(m["Molecular_Weight"], errors="coerce")
    m["pc_mw"] = pd.to_numeric(m["PubChem_MW"], errors="coerce")
    m["ds_logp"] = pd.to_numeric(m["LogP"], errors="coerce")
    m["pc_logp"] = pd.to_numeric(m["PubChem_XLogP"], errors="coerce")
    mw_bad = m[(m["ds_mw"].notna()) & ((m["ds_mw"] - m["pc_mw"]).abs() / m["pc_mw"] > 0.05)]
    lp_bad = m[(m["ds_logp"].notna()) & (m["pc_logp"].notna()) & ((m["ds_logp"] - m["pc_logp"]).abs() > 1.0)]
    print(f"compared {len(m)}: MW off by >5 %: {len(mw_bad)}; logP off by >1.0: {len(lp_bad)}")
    for r in mw_bad.head(15).itertuples(index=False):
        print(f"  MW   {r.Note_Name:<28} {r.CAS:<12} dataset2 {r.ds_mw:g} vs PubChem {r.pc_mw:g} ({r.IUPAC_Name[:40]})")
    for r in lp_bad.head(15).itertuples(index=False):
        print(f"  logP {r.Note_Name:<28} {r.CAS:<12} dataset2 {r.ds_logp:g} vs PubChem {r.pc_logp:g}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
