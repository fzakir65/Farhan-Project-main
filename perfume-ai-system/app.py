"""Task 7 — the app. Zone A (buttons or free text -> matched perfume -> description) hands a perfume to Zone B
(structure -> safety -> rebalance) and shows the formula with every flag and trace.

    streamlit run app.py                    # the UI
    python app.py "fresh woody for summer"  # the same flow in the terminal (no Streamlit needed)
    python app.py --report                  # the data report (Task 1)

The LLM is optional: with no ANTHROPIC_API_KEY the button path and keyword interpretation still work (Rule 9).
"""
from __future__ import annotations

import sys

import pandas as pd

from load_data import load_all, report
from zone_a_llm.describer import describe
from zone_a_llm.input_handler import Preferences, interpret, vocabulary
from zone_a_llm.llm_client import get_client
from zone_a_llm.matcher import match
from zone_b_chemistry.pipeline import perfume_to_accords, run_zone_b_for_perfume


def formula_table(out) -> pd.DataFrame:
    cols = [c for c in ("Layer", "Note_Name", "CAS", "Pct", "Pinned", "Accords") if c in out.formula.columns]
    f = out.formula[cols].copy()
    f["Pct"] = f["Pct"].round(3)
    return f


# ----------------------------------------------------------------------------
# terminal flow
# ----------------------------------------------------------------------------

def run_cli(text: str) -> int:
    data = load_all()
    client = get_client()
    print(f"LLM: {'available' if client else 'not configured — keyword + deterministic path'}")
    prefs = interpret(text, data, client=client)
    print(f"\npreferences: {prefs}")
    matches = match(prefs, data, top_k=5, client=client)
    if not matches:
        print("no match"); return 1
    for i, m in enumerate(matches, 1):
        print(f"{i}. {m.name} by {m.brand}  score {m.score:.1f}  [{m.rank_source}]")
        for r in m.reasons[:4]:
            print(f"     {r}")
    row = data.perfumes[data.perfumes["Perfume_ID"] == matches[0].perfume_id].iloc[0]
    print("\n" + describe(row, data, client=client))
    names, weights, unmapped = perfume_to_accords(row, data)
    print(f"\naccords -> dataset3: {names}   unmapped terms: {unmapped or 'none'}")
    out, _ = run_zone_b_for_perfume(row, data, require_complete=False)
    if out is None:
        print("no accord of this perfume maps to a rule recipe yet — resolve accord_name_aliases.csv"); return 1
    print(f"\nZONE B verdict: {out.verdict}")
    print(formula_table(out).to_string(index=False))
    if out.safety is not None:
        print("\nsafety:"); print(out.safety.summary())
    if out.optimized is not None:
        print("\nrebalance trace:"); print("\n".join(f"  {t}" for t in out.optimized.trace))
    return 0 if out.verdict == "PASS" else 1


# ----------------------------------------------------------------------------
# Streamlit flow
# ----------------------------------------------------------------------------

def run_streamlit() -> None:
    import streamlit as st

    st.set_page_config(page_title="Perfume Formulation", layout="wide")
    st.title("AI Perfume Formulation — Zone A → Zone B")

    @st.cache_resource
    def _data():
        return load_all()

    data = _data()
    client = get_client()
    vocab = vocabulary(data)

    with st.sidebar:
        st.caption(f"LLM: {'connected' if client else 'not configured (button path only)'}")
        mode = st.radio("Input", ["Buttons", "Free text"])
        product = st.selectbox("Product type (dilution)", ["Neat (formula = product)"] + list(data.product_types["Product_Type"]))
        if product == "Neat (formula = product)":
            fraction = 1.0
        else:
            r = data.product_types.set_index("Product_Type").loc[product]
            fraction = st.slider("Concentrate fraction", float(r["Concentrate_Fraction_Min"]), float(r["Concentrate_Fraction_Max"]),
                                 float(r["Concentrate_Fraction_Max"]), 0.01)
        st.caption("Source: RSC Table A2 (product_types.csv). Caps become limit / fraction; bans never relax.")

    if mode == "Buttons":
        c1, c2 = st.columns(2)
        accords = c1.multiselect("Accords you like", vocab["accords"])
        avoid = c2.multiselect("Accords to avoid", vocab["accords"])
        family = c1.selectbox("Family", ["(any)"] + vocab["families"])
        gender = c2.selectbox("For", ["(any)"] + vocab["genders"])
        season = c1.selectbox("Season", ["(any)"] + vocab["seasons"])
        strength = c2.slider("Strength / longevity", 1, 5, 3)
        prefs = Preferences(accords=accords, avoid=avoid, family=None if family == "(any)" else family,
                            gender=None if gender == "(any)" else gender, season=None if season == "(any)" else season, strength=strength)
    else:
        text = st.text_area("Describe what you want", "something fresh and woody for summer evenings, not too sweet")
        prefs = interpret(text, data, client=client)
        st.json({k: v for k, v in prefs.__dict__.items() if v})

    if prefs.is_empty():
        st.info("Pick at least one preference."); return
    matches = match(prefs, data, top_k=5, client=client)
    st.subheader("Matches")
    labels = [f"{m.name} — {m.brand} (score {m.score:.1f}, {m.rank_source})" for m in matches]
    pick = st.radio("Choose a perfume", labels, index=0)
    m = matches[labels.index(pick)]
    with st.expander("Why these matches"):
        for mm in matches:
            st.write(f"**{mm.name}** — " + "; ".join(mm.reasons))
    row = data.perfumes[data.perfumes["Perfume_ID"] == m.perfume_id].iloc[0]
    st.write(describe(row, data, client=client))
    names, weights, unmapped = perfume_to_accords(row, data)
    st.caption(f"Accords → rule recipes: {', '.join(names) or 'none'}" + (f" · unmapped: {', '.join(unmapped)}" if unmapped else ""))

    if st.button("Approve → build the formula (Zone B)"):
        out, _ = run_zone_b_for_perfume(row, data, concentrate_fraction=fraction, require_complete=False)
        if out is None:
            st.error("No accord of this perfume maps to a rule recipe yet (see accord_name_aliases.csv)."); return
        colour = {"PASS": st.success, "REJECT": st.error, "INCOMPLETE": st.warning}[out.verdict]
        colour(f"Zone B verdict: {out.verdict}" + ("  (provisional — constituent roll-up not implemented)" if out.safety else ""))
        if out.optimized is not None:
            st.dataframe(out.optimized.layers, hide_index=True)
        st.dataframe(formula_table(out), hide_index=True, use_container_width=True)
        st.download_button("Download formula CSV", formula_table(out).to_csv(index=False), f"{row['Perfume_Name']}_formula.csv")
        if out.safety is not None:
            with st.expander("Safety: rejections, caps and flags (every line cites its source row)"):
                st.text(out.safety.summary())
        with st.expander("Structure trace (Task 2)"):
            st.text(out.build.summary())
            st.dataframe(out.build.trace, hide_index=True)
        if out.optimized is not None:
            with st.expander("Rebalance trace (Task 4)"):
                st.text("\n".join(out.optimized.trace))
        if len(out.build.unplaced):
            st.warning("Unplaced notes (need a dataset2 row or an alias):")
            st.dataframe(out.build.unplaced, hide_index=True)


def _under_streamlit() -> bool:
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx() is not None
    except Exception:
        return False


if __name__ == "__main__":
    if _under_streamlit():
        run_streamlit()
    elif len(sys.argv) > 1 and sys.argv[1] == "--report":
        data = load_all()
        print(report(data))
        sys.exit(2 if data.errors() else 0)
    else:
        sys.exit(run_cli(" ".join(sys.argv[1:]) or "fresh woody citrus for summer"))
elif _under_streamlit():
    run_streamlit()
