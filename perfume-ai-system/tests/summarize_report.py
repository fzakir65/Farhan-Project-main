"""Dev helper: run the loader and print issue categories instead of every line."""
import collections
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from load_data import load_all, report  # noqa: E402


def kind(issue) -> str:
    msg = re.sub(r"'[^']*'", "'…'", issue.message)
    msg = re.sub(r"\d+(\.\d+)?", "#", msg)
    return f"{issue.table} :: {msg[:80]}"


d = load_all()
text = report(d)
print(text.split("--- ERROR")[0])
for sev in ("ERROR", "WARNING"):
    c = collections.Counter(kind(i) for i in d.issues if i.severity == sev)
    print(f"{sev} kinds:")
    for k, n in c.most_common(15):
        print(f"  {n:>4}  {k}")
    print()
print(text[text.index("UK/EU entries"):])
