from __future__ import annotations

import argparse
import sys
from pathlib import Path

from common import ROOT, validate_processed_tables


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 processed 标准表字段是否完整。")
    parser.add_argument("--processed-dir", type=Path, default=ROOT / "data" / "processed")
    args = parser.parse_args()

    errors = validate_processed_tables(args.processed_dir)
    if errors:
        print("数据校验失败：", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 2
    print("processed 数据字段校验通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
