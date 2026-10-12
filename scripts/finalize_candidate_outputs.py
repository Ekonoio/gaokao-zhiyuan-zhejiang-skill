from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import ROOT, VOLUNTEER_COLUMNS, read_csv_rows, write_csv_rows


def review_reasons(row: dict[str, str]) -> list[str]:
    reasons: list[str] = []
    if row.get("学历层次") in {"本科", "职业本科"}:
        reasons.append("民办本科且历史位次差大，仅作低概率冲刺；确认专业、学费和就读意愿")
    elif row.get("是否民办") == "是":
        reasons.append("民办专科；确认学费、住宿费和真实就读意愿")
    if row.get("是否中外合作") == "是":
        reasons.append("核对中外合作培养模式、收费项目和证书")
    if row.get("人工复核项"):
        reasons.append(row["人工复核项"])
    if row.get("体检风险") not in {"", "无明显体检风险"}:
        reasons.append(f"体检/听力：{row['体检风险']}")
    if row.get("学费是否超预算") == "是" or not row.get("学费"):
        reasons.append("核对学费是否符合每年3万元硬上限")
    return list(dict.fromkeys(reasons))


def final_rows(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for row in rows:
        reasons = review_reasons(row)
        enriched: dict[str, object] = {
            "填报状态": "必须人工确认" if reasons else "可直接填",
            "人工确认原因": "；".join(reasons),
            **row,
        }
        output.append(enriched)
    return output


def markdown_summary(rows: list[dict[str, object]]) -> str:
    undergraduate = [row for row in rows if row["学历层次"] in {"本科", "职业本科"}]
    direct = [row for row in rows if row["填报状态"] == "可直接填"]
    review = [row for row in rows if row["填报状态"] == "必须人工确认"]
    tier_counts = {
        tier: sum(1 for row in rows if row["层级"] == tier)
        for tier in ["冲", "稳", "保"]
    }

    lines = [
        "# 2026浙江普通类二段最终志愿方案",
        "",
        "## 结论",
        "",
        "- 考生：460分，原始位次220000，政史地，男。",
        f"- 最终80个：冲{tier_counts['冲']}、稳{tier_counts['稳']}、保{tier_counts['保']}。",
        f"- 本科：{len(undergraduate)}个，全部为民办本科且只作低概率冲刺。",
        f"- 可直接填：{len(direct)}个；必须人工确认：{len(review)}个。",
        "- 听力情况待确认不作硬排除；本表不能代替逐项核验听力条款，最终以学校2026招生章程为准。",
        "",
        "## 全部可报本科",
        "",
        "|序号|院校|专业|学费/年|2026剩余计划|2025最低位次|位次差|复核重点|",
        "|---:|---|---|---:|---:|---:|---:|---|",
    ]
    for row in undergraduate:
        lines.append(
            f"|{row['志愿序号']}|{row['院校名称']}|{row['专业名称']}|"
            f"{row['学费']}|{row['2026招生计划数']}|{row['2025最低位次']}|"
            f"{row['2025位次差']}|{row['人工确认原因']}|"
        )

    lines.extend(
        [
            "",
            "## 填报状态",
            "",
            "- `可直接填`：今年个性化计划、选科、学费、公民办属性均已通过当前规则；按表中顺序填报。",
            "- `必须人工确认`：确认完成后仍按原序号填，不要删除后整体重排。",
            "- 所有志愿提交前，仍需在浙江官方系统逐项核对院校代码、专业代码和剩余计划是否发生变化。",
            "",
            "## 必须人工确认",
            "",
            "|序号|层级|院校|专业|原因|",
            "|---:|---|---|---|---|",
        ]
    )
    for row in review:
        lines.append(
            f"|{row['志愿序号']}|{row['层级']}|{row['院校名称']}|"
            f"{row['专业名称']}|{row['人工确认原因']}|"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="生成该考生的最终可填报文件。")
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "outputs" / "target_candidate" / "volunteer_table.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "outputs" / "final_2026_460",
    )
    args = parser.parse_args()

    rows = final_rows(read_csv_rows(args.input))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    columns = ["填报状态", "人工确认原因", *VOLUNTEER_COLUMNS]
    write_csv_rows(args.output_dir / "最终80志愿排序表.csv", rows, columns)
    write_csv_rows(
        args.output_dir / "全部可报本科.csv",
        [row for row in rows if row["学历层次"] in {"本科", "职业本科"}],
        columns,
    )
    write_csv_rows(
        args.output_dir / "必须人工确认.csv",
        [row for row in rows if row["填报状态"] == "必须人工确认"],
        columns,
    )
    write_csv_rows(
        args.output_dir / "可直接填报.csv",
        [row for row in rows if row["填报状态"] == "可直接填"],
        columns,
    )
    (args.output_dir / "最终填报说明.md").write_text(
        markdown_summary(rows),
        encoding="utf-8",
    )
    (args.output_dir / "最终志愿数据.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        "最终文件已生成："
        f"80条；本科{sum(row['学历层次'] in {'本科', '职业本科'} for row in rows)}条；"
        f"直接填{sum(row['填报状态'] == '可直接填' for row in rows)}条；"
        f"人工确认{sum(row['填报状态'] == '必须人工确认' for row in rows)}条。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
