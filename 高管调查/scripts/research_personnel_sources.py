"""Read original filing pages for the personnel investigation without altering originals.

Example: python -X utf8 personnel_research/scripts/research_personnel_sources.py pages 美的2025 69 71
Extraction cache is disposable; report citations always refer to original PDF pages.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
WORK = Path(tempfile.gettempdir()) / "personnel-background-research-20261017"


def load(name):
    WORK.mkdir(exist_ok=True)
    cache = WORK / "filing_pages.json"
    data = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}
    if name not in data:
        matches = list((ROOT / "origin").rglob(name + ".pdf"))
        if len(matches) != 1:
            raise ValueError(f"Expected one original for {name}, found {len(matches)}")
        run = subprocess.run(["pdftotext", "-layout", str(matches[0]), "-"],
                             check=True, capture_output=True, encoding="utf-8")
        data[name] = run.stdout.split("\f")
        cache.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data[name]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["pages", "find"])
    parser.add_argument("name")
    parser.add_argument("values", nargs="+")
    parser.add_argument("--context", type=int, default=180)
    args = parser.parse_args()
    texts = load(args.name)
    if args.mode == "pages":
        for number in map(int, args.values):
            print(f"\n=== {args.name} PDF {number} ===")
            print("\n".join(line.strip() for line in texts[number - 1].splitlines() if line.strip()))
    else:
        pattern = re.compile("|".join(args.values))
        for number, text in enumerate(texts, 1):
            compact = re.sub(r"\s+", "", text)
            for match in pattern.finditer(compact):
                print(f"{args.name} PDF {number}: " +
                      compact[max(0, match.start()-args.context):match.end()+args.context])


if __name__ == "__main__":
    main()
