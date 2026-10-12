from __future__ import annotations

import argparse
import sys
from pathlib import Path

from common import EXCLUDED_COLUMNS, ROOT, generate_candidate_pool_rows, read_csv_rows, read_json, write_csv_rows


def main() -> int:
    parser = argparse.ArgumentParser(description="根据用户输入和合并数据生成候选志愿池与排除清单。")
    parser.add_argument("--profile", type=Path, default=ROOT / "outputs" / "validated_input.json")
    parser.add_argument("--merged", type=Path, default=ROOT / "outputs" / "merged_plan_history.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs" / "candidate_pool.csv")
    parser.add_argument("--excluded", type=Path, default=ROOT / "outputs" / "excluded_list.csv")
    args = parser.parse_args()

    profile = read_json(args.profile)
    merged = read_csv_rows(args.merged)
    candidates, excluded = generate_candidate_pool_rows(profile, merged)
    fieldnames = list(merged[0].keys()) + ["subject_match", "tuition_over_budget", "medical_risk", "force_review", "candidate_notes"] if merged else []
    write_csv_rows(args.output, candidates, fieldnames)
    write_csv_rows(args.excluded, excluded, EXCLUDED_COLUMNS)
    print(f"候选池：{len(candidates)} 行；排除清单：{len(excluded)} 行。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
