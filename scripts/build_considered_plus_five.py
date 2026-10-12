from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import (
    ROOT,
    VOLUNTEER_COLUMNS,
    classify_row,
    load_tier_rules,
    read_csv_rows,
    read_json,
    volunteer_row_from_candidate,
    write_csv_rows,
)
from finalize_candidate_outputs import final_rows
from optimize_considered_plan import candidate_key, is_region_allowed


ADDITIONAL_KEYS = [
    ("武汉工程科技学院", "会计学"),
    ("昆明城市学院", "金融学"),
    ("嘉兴职业技术学院", "现代物流管理"),
    ("浙江安防职业技术学院", "大数据与会计"),
    ("台州职业技术学院", "金融服务与管理"),
]


def build_additional_rows(
    considered: list[dict[str, str]],
    candidates: list[dict[str, str]],
    profile: dict[str, object],
) -> list[dict[str, object]]:
    if len(considered) != 20:
        raise ValueError(f"已考虑表应为20项，实际为{len(considered)}项")
    considered_keys = {candidate_key(row) for row in considered}
    considered_schools = {row.get("院校名称", "") for row in considered}
    candidate_map = {candidate_key(row): row for row in candidates}
    rules = load_tier_rules()
    output: list[dict[str, object]] = []

    for sequence, key in enumerate(ADDITIONAL_KEYS, start=1):
        if key in considered_keys:
            raise ValueError(f"新增项已存在于已考虑表：{key}")
        if key[0] in considered_schools:
            raise ValueError(f"新增项院校已出现在已考虑表：{key[0]}")
        row = candidate_map.get(key)
        if row is None:
            raise ValueError(f"候选池缺少新增项：{key}")
        if not is_region_allowed(row):
            raise ValueError(f"新增项违反地域约束：{key}")
        layer, reason, risk, review = classify_row(row, rules, profile)
        if layer != "冲":
            raise ValueError(f"新增项并非冲刺层：{key} -> {layer}")
        output.append(
            volunteer_row_from_candidate(
                row,
                sequence,
                profile,
                layer,
                reason,
                risk,
                review,
            )
        )
    return final_rows(output)


def combined_rows(
    considered: list[dict[str, str]],
    additional: list[dict[str, object]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for sequence, row in enumerate(considered, start=1):
        rows.append(
            {
                "清单序号": sequence,
                "来源": "已考虑",
                "原志愿序号": row.get("志愿序号", ""),
                **{key: value for key, value in row.items() if key != "志愿序号"},
            }
        )
    for offset, row in enumerate(additional, start=1):
        rows.append(
            {
                "清单序号": len(considered) + offset,
                "来源": "新增冲刺",
                "原志愿序号": "",
                **{key: value for key, value in row.items() if key != "志愿序号"},
            }
        )
    return rows


def markdown(additional: list[dict[str, object]]) -> str:
    lines = [
        "# 在已考虑20项基础上新增5个冲刺",
        "",
        "- 原20项全部保留，不删除、不改层级。",
        "- 新增5项均未在原表出现，且新增院校也未在原表出现。",
        "- 东北三省为0；江西非南昌为0；中外合作为0；学费均不超过3万元/年。",
        "",
        "|新增顺序|院校|专业|层次|城市|公民办|学费/年|2026计划|2025位次差|定位|",
        "|---:|---|---|---|---|---|---:|---:|---:|---|",
    ]
    for row in additional:
        nature = "民办" if row["是否民办"] == "是" else "公办"
        position = (
            "本科极低概率冲刺"
            if row["学历层次"] in {"本科", "职业本科"}
            else "专科冲稳边界"
        )
        lines.append(
            f"|{row['志愿序号']}|{row['院校名称']}|{row['专业名称']}|"
            f"{row['学历层次']}|{row['城市']}|{nature}|{row['学费']}|"
            f"{row['2026招生计划数']}|{row['2025位次差']}|{position}|"
        )
    lines.extend(
        [
            "",
            "## 使用方式",
            "",
            "- 这5项是原20项之外的增补项，不替换原20项。",
            "- 两个本科必须确认民办、学费及真实就读意愿。",
            "- 三个公办专科的历史位次接近考生，属于冲刺或冲稳边界，不能作为最终保底。",
            "- 最终提交前仍需在浙江官方系统核对代码、剩余计划和招生章程。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="保留已考虑20项并新增5个冲刺项。")
    parser.add_argument(
        "--considered",
        type=Path,
        default=ROOT / "data" / "raw" / "considered.csv",
    )
    parser.add_argument(
        "--candidate-pool",
        type=Path,
        default=ROOT / "outputs" / "target_candidate" / "rank_gap.csv",
    )
    parser.add_argument(
        "--profile",
        type=Path,
        default=ROOT / "outputs" / "target_candidate" / "validated_input.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "outputs" / "considered_plus_five",
    )
    args = parser.parse_args()

    considered = read_csv_rows(args.considered)
    additional = build_additional_rows(
        considered,
        read_csv_rows(args.candidate_pool),
        read_json(args.profile),
    )
    combined = combined_rows(considered, additional)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv_rows(
        args.output_dir / "新增5个冲刺.csv",
        additional,
        ["填报状态", "人工确认原因", *VOLUNTEER_COLUMNS],
    )
    combined_columns = [
        "清单序号",
        "来源",
        "原志愿序号",
        "填报状态",
        "人工确认原因",
        *[column for column in VOLUNTEER_COLUMNS if column != "志愿序号"],
    ]
    write_csv_rows(
        args.output_dir / "已考虑20加新增5冲.csv",
        combined,
        combined_columns,
    )
    (args.output_dir / "新增5个冲刺说明.md").write_text(
        markdown(additional),
        encoding="utf-8",
    )
    (args.output_dir / "新增5个冲刺.json").write_text(
        json.dumps(additional, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"已保留{len(considered)}项并新增{len(additional)}个冲刺项。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
