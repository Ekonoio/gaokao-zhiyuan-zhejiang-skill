from __future__ import annotations

import argparse
import sys
from pathlib import Path

from common import AUDIT_COLUMNS, ROOT, audit_rows, read_csv_rows, read_json, write_csv_rows


def main() -> int:
    parser = argparse.ArgumentParser(description="生成风险审计表。")
    parser.add_argument("--profile", type=Path, default=ROOT / "outputs" / "validated_input.json")
    parser.add_argument("--volunteer-table", type=Path, default=ROOT / "outputs" / "volunteer_table.csv")
    parser.add_argument("--excluded", type=Path, default=ROOT / "outputs" / "excluded_list.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs" / "risk_audit.csv")
    args = parser.parse_args()

    profile = read_json(args.profile)
    volunteers = read_csv_rows(args.volunteer_table)
    excluded = read_csv_rows(args.excluded)
    rows = audit_rows(volunteers, excluded, profile)
    write_csv_rows(args.output, rows, AUDIT_COLUMNS)
    print(f"已生成风险审计表：{args.output}，共 {len(rows)} 行。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
