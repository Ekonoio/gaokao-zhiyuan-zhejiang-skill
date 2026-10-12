from __future__ import annotations

import argparse
import sys
from pathlib import Path

from common import ROOT
from second_stage_plan import OFFICIAL_PLAN_PORTAL, import_second_stage_plan


def main() -> int:
    parser = argparse.ArgumentParser(description="导入浙江考试院登录后下载的2026个性化二段计划 XLSM/XLSX。")
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=ROOT / "data" / "raw" / "current_second_stage_plan.xlsm",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "processed" / "admissions_plan.csv",
    )
    args = parser.parse_args()
    try:
        rows, summary = import_second_stage_plan(args.input, args.output)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(str(exc))
        print(f"人工下载入口：{OFFICIAL_PLAN_PORTAL}")
        return 2
    print(
        f"已导入{len(rows)}个二段专业：本科/职业本科"
        f"{summary['undergraduate_program_count']}个，专科{summary['associate_program_count']}个。"
    )
    print(f"标准计划表：{args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
