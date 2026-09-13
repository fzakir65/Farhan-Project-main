"""Task 7 — Streamlit app (NOT YET IMPLEMENTED). For now: prints the data report."""
from __future__ import annotations

import sys

from load_data import load_all, report

if __name__ == "__main__":
    data = load_all()
    print(report(data))
    sys.exit(2 if data.errors() else 0)
