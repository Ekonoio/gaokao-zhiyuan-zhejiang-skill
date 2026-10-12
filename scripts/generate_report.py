from __future__ import annotations

import argparse
import sys
from pathlib import Path

from common import ROOT, assess_undergraduate_opportunity, generate_all_outputs, read_csv_rows, read_json


def main() -> int:
    parser = argparse.ArgumentParser(description="生成 Markdown、CSV、Excel、排除清单、审计表、来源记录和人工复核清单。")
    parser.add_argument("--profile", type=Path, default=ROOT / "outputs" / "validated_input.json")
    parser.add_argument("--volunteer-table", type=Path, default=ROOT / "outputs" / "volunteer_table.csv")
    parser.add_argument("--excluded", type=Path, default=ROOT / "outputs" / "excluded_list.csv")
    parser.add_argument("--audit", type=Path, default=ROOT / "outputs" / "risk_audit.csv")
    parser.add_argument("--ranked", type=Path, default=ROOT / "outputs" / "rank_gap.csv")
    parser.add_argument(
        "--historical",
        type=Path,
        default=ROOT / "data" / "processed" / "historical_admission.csv",
    )
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs")
    args = parser.parse_args()

    profile = read_json(args.profile)
    volunteers = read_csv_rows(args.volunteer_table)
    excluded = read_csv_rows(args.excluded)
    audit = read_csv_rows(args.audit)
    ranked = read_csv_rows(args.ranked) if args.ranked.exists() else volunteers
    historical = read_csv_rows(args.historical) if args.historical.exists() else []
    opportunity = assess_undergraduate_opportunity(profile, ranked, historical_rows=historical)
    generate_all_outputs(args.output_dir, profile, volunteers, excluded, audit, opportunity)
    print(f"已生成最终报告和表格：{args.output_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
