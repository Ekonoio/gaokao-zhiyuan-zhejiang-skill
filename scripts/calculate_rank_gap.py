from __future__ import annotations

import argparse
import sys
from pathlib import Path

from common import HISTORICAL_YEARS, ROOT, add_rank_gaps, read_csv_rows, read_json, write_csv_rows


def main() -> int:
    parser = argparse.ArgumentParser(description="计算 2025/2024/2023 位次差。")
    parser.add_argument("--profile", type=Path, default=ROOT / "outputs" / "validated_input.json")
    parser.add_argument("--input", type=Path, default=ROOT / "outputs" / "candidate_pool.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs" / "rank_gap.csv")
    args = parser.parse_args()

    profile = read_json(args.profile)
    rows = read_csv_rows(args.input)
    ranked = add_rank_gaps(rows, int(profile["rank"]))
    fields = list(rows[0].keys()) + [f"{year}_rank_gap" for year in HISTORICAL_YEARS] + ["history_year_count", "rank_stability"] if rows else []
    write_csv_rows(args.output, ranked, fields)
    print(f"已计算位次差：{args.output}，共 {len(ranked)} 行。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
