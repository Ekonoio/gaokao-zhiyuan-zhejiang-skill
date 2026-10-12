from __future__ import annotations

import argparse
import sys
from pathlib import Path

from common import ROOT, merge_plan_history


def main() -> int:
    parser = argparse.ArgumentParser(description="合并当年招生计划和近三年历史投档数据。")
    parser.add_argument("--processed-dir", type=Path, default=ROOT / "data" / "processed")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs" / "merged_plan_history.csv")
    args = parser.parse_args()

    rows = merge_plan_history(args.processed_dir, args.output)
    print(f"已生成合并表：{args.output}，共 {len(rows)} 行。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
