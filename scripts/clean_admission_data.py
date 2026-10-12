from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from common import PROCESSED_FIELD_MAP, ROOT, copy_sample_to_processed, ensure_dir, raw_data_status, read_csv_rows, write_csv_rows


def clean_raw_data(root: Path) -> tuple[int, str]:
    raw_dir = root / "data" / "raw"
    processed_dir = root / "data" / "processed"
    ok, message = raw_data_status(raw_dir)
    if not ok:
        return 2, message

    ensure_dir(processed_dir)
    copied = 0
    for target_name, required_fields in PROCESSED_FIELD_MAP.items():
        source = raw_dir / target_name
        if not source.exists():
            continue
        rows = read_csv_rows(source)
        missing = [field for field in required_fields if rows and field not in rows[0]]
        if missing:
            return 2, f"{source.name} 缺少标准字段：{', '.join(missing)}。请先人工映射字段。"
        shutil.copyfile(source, processed_dir / target_name)
        copied += 1

    charter_source = raw_dir / "charter_chunks.jsonl"
    if charter_source.exists():
        shutil.copyfile(charter_source, processed_dir / "charter_chunks.jsonl")
        copied += 1

    if copied == 0:
        return 2, (
            "未找到可直接识别的标准 CSV/JSONL 文件。公开数据请运行 "
            "scripts/fetch_official_data.py；个性化二段 XLSM/XLSX 请运行 "
            "scripts/import_second_stage_plan.py；其他数据需按 data/processed/README.md 映射。"
        )
    return 0, f"已清洗/复制 {copied} 个标准文件到 data/processed/。"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="复制已标准化的浙江普通类招生数据；公开抓取和个性化XLSM导入使用各自专用脚本。"
    )
    parser.add_argument("--use-sample", action="store_true", help="使用 data/sample/ 的 mock 数据生成 processed 表")
    parser.add_argument("--root", type=Path, default=ROOT, help="Skill 根目录")
    args = parser.parse_args()

    if args.use_sample:
        copied = copy_sample_to_processed(args.root)
        print(f"已复制 sample/mock 数据到 data/processed/：{len(copied)} 个文件。")
        return 0

    code, message = clean_raw_data(args.root)
    print(message)
    return code


if __name__ == "__main__":
    sys.exit(main())
