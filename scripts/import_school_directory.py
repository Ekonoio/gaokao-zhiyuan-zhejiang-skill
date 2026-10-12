from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import pandas as pd

from common import PROCESSED_FIELD_MAP, ROOT, write_csv_rows


DEFAULT_SOURCE_URL = "https://www.dxsbb.com/news/34310.html"
OFFICIAL_SOURCE_URL = (
    "https://www.moe.gov.cn/jyb_xxgk/s5743/s5744/A03/202606/"
    "t20260618_1441074.html"
)


def parse_school_directory(path: Path, source_url: str) -> list[dict[str, object]]:
    table = pd.read_html(path)[0]
    table.columns = [str(value).strip() for value in table.iloc[0].tolist()]
    table = table.iloc[1:].copy()

    rows: list[dict[str, object]] = []
    for _, item in table.iterrows():
        school_name = str(item.get("学校名称", "")).strip()
        if not school_name or school_name == "nan":
            continue
        note = str(item.get("备注", "")).strip()
        is_private = "民办" in note
        is_public = "公办" in note
        rows.append(
            {
                "school_code": "",
                "school_name": school_name,
                "province": str(item.get("省份", "")).strip(),
                "city": str(item.get("城市", "")).strip(),
                "school_type": str(item.get("层次", "")).strip(),
                "is_public": "是" if is_public else "否",
                "is_private": "是" if is_private else "否",
                "is_985": "",
                "is_211": "",
                "is_double_first_class": "",
                "under_department": "",
                "official_site": "",
                "admission_site": "",
                "source": source_url,
                "updated_at": "2026-06-18",
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="导入2026教育部全国普通高校名单。")
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "data" / "raw" / "2026-national-schools-source.html",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "processed" / "school_info.csv",
    )
    parser.add_argument("--source-url", default=DEFAULT_SOURCE_URL)
    args = parser.parse_args()

    rows = parse_school_directory(args.input, args.source_url)
    write_csv_rows(args.output, rows, PROCESSED_FIELD_MAP["school_info.csv"])
    digest = hashlib.sha256(args.input.read_bytes()).hexdigest()
    print(
        f"已导入{len(rows)}所高校；源文件SHA256={digest}；"
        f"教育部原始发布页={OFFICIAL_SOURCE_URL}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
