from __future__ import annotations

import argparse
import sys
from pathlib import Path

from common import ROOT, load_profile, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="校验浙江普通类考生输入，并输出标准 JSON。")
    parser.add_argument("--input", type=Path, default=ROOT / "examples" / "sample_input.md")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs" / "validated_input.json")
    args = parser.parse_args()

    try:
        profile = load_profile(args.input)
    except Exception as exc:
        print(f"输入校验失败：{exc}", file=sys.stderr)
        return 2
    write_json(args.output, profile)
    print(f"输入校验通过：{args.output}")
    print(f"冲稳保目标数量：{profile['tier_counts']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
