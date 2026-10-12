from __future__ import annotations

import argparse
import sys
from pathlib import Path

from common import ROOT, VOLUNTEER_COLUMNS, classify_and_select_volunteers, load_tier_rules, read_csv_rows, read_json, write_csv_rows


def main() -> int:
    parser = argparse.ArgumentParser(description="根据配置阈值生成冲/稳/保志愿排序表。")
    parser.add_argument("--profile", type=Path, default=ROOT / "outputs" / "validated_input.json")
    parser.add_argument("--input", type=Path, default=ROOT / "outputs" / "rank_gap.csv")
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "tier_rules.yaml")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs" / "volunteer_table.csv")
    args = parser.parse_args()

    profile = read_json(args.profile)
    rows = read_csv_rows(args.input)
    volunteers = classify_and_select_volunteers(rows, profile, load_tier_rules(args.config))
    write_csv_rows(args.output, volunteers, VOLUNTEER_COLUMNS)
    print(f"已生成志愿排序表：{args.output}，共 {len(volunteers)} 行。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
