"""Task 6 — the customer-facing description of a recommended perfume (Zone A).

    text = describe(perfume_row, data)                  # template prose from the catalogue fields (button path)
    text = describe(perfume_row, data, client=client)   # LLM prose, checked to contain no numbers / safety talk

What the description may contain: the perfume's name, brand, family, accords, notes by layer and its catalogue
description. What it must never contain: percentages, dosages, IFRA/regulatory statements — those belong to Zone B's
own report. An LLM answer that violates this is replaced by the template.
"""
from __future__ import annotations

import re

import pandas as pd

from .llm_client import LLMClient, complete

SYSTEM_PROMPT = """You write short, warm product descriptions for perfumes. Use only the facts given. Two or three
sentences. Never mention percentages, quantities, dosages, safety, IFRA, allergens or regulations."""
FORBIDDEN = re.compile(r"(\d+(\.\d+)?\s*%|\bpercent\b|\bifra\b|\ballergen|\bregulat|\bbanned\b|\bdosage|\bmg\b|\bppm\b)", re.I)


def _list(cell) -> list[str]:
    return [t.strip() for t in re.split(r"[;,]", str(cell or "")) if t.strip()]


def facts(perfume: pd.Series | dict) -> dict:
    return {
        "name": str(perfume.get("Perfume_Name", "")), "brand": str(perfume.get("Brand", "")),
        "family": str(perfume.get("Fragrance_Family", "")), "accords": _list(perfume.get("Main_Accords", "")),
        "top": _list(perfume.get("Top_Notes", "")), "heart": _list(perfume.get("Middle_Notes", "")),
        "base": _list(perfume.get("Base_Notes", "")), "gender": str(perfume.get("Gender", "")),
        "season": str(perfume.get("Season", "")), "description": str(perfume.get("Description", "")),
    }


def template(perfume: pd.Series | dict) -> str:
    f = facts(perfume)
    parts = [f"{f['name']} by {f['brand']}" + (f" is a {f['family']} fragrance" if f["family"] else "") + "."]
    if f["accords"]:
        parts.append("Main accords: " + ", ".join(f["accords"][:6]) + ".")
    layers = [(k, f[k]) for k in ("top", "heart", "base") if f[k]]
    if layers:
        parts.append(" ".join(f"{k.capitalize()}: {', '.join(v[:5])}." for k, v in layers))
    if f["description"]:
        parts.append(f["description"].strip())
    if f["gender"] or f["season"]:
        parts.append(" ".join(x for x in (f"For {f['gender']}." if f["gender"] else "", f"Best in {f['season']}." if f["season"] else "") if x))
    return " ".join(parts)


def describe(perfume: pd.Series | dict, data=None, client: LLMClient | None = None) -> str:
    base = template(perfume)
    if client is None:
        return base
    f = facts(perfume)
    user = (f"Name: {f['name']}\nBrand: {f['brand']}\nFamily: {f['family']}\nAccords: {', '.join(f['accords'])}\n"
            f"Top notes: {', '.join(f['top'])}\nHeart notes: {', '.join(f['heart'])}\nBase notes: {', '.join(f['base'])}\n"
            f"Catalogue text: {f['description']}")
    answer = complete(client, SYSTEM_PROMPT, user, max_tokens=250).strip()
    if not answer or FORBIDDEN.search(answer) or f["name"] not in answer:
        return base
    return answer


__all__ = ["describe", "template", "facts", "FORBIDDEN"]
