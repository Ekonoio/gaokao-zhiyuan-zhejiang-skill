from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from common import ROOT, search_charter_chunks, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="对 charter_chunks.jsonl 做基础关键词检索。")
    parser.add_argument("--charter", type=Path, default=ROOT / "data" / "processed" / "charter_chunks.jsonl")
    parser.add_argument("--school-code", default="")
    parser.add_argument("--school-name", default="")
    parser.add_argument("--risk-type", default="")
    parser.add_argument("--keyword", default="")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    rows = search_charter_chunks(args.charter, args.school_code, args.school_name, args.risk_type, args.keyword)
    if args.output:
        write_json(args.output, rows)
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
