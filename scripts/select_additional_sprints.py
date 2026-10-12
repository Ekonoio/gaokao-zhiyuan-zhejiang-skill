from __future__ import annotations

import argparse
from pathlib import Path

from common import (
    ROOT,
    classify_row,
    is_undergraduate_level,
    load_tier_rules,
    major_priority,
    read_csv_rows,
    read_json,
    region_priority,
    row_bool,
    to_int,
    write_csv_rows,
)
from optimize_considered_plan import candidate_key, is_region_allowed


REVIEW_COLUMNS = [
    "推荐顺序",
    "学历层次",
    "省份",
    "城市",
    "院校代码",
    "院校名称",
    "专业代码",
    "专业名称",
    "学费",
    "公民办",
    "2026招生计划数",
    "2025最低位次",
    "2025位次差",
    "2024位次差",
    "2023位次差",
    "历史年份数",
    "排序依据",
    "风险提示",
    "人工复核项",
]


def ranked_sprint_candidates(
    considered_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
    profile: dict[str, object],
) -> list[tuple[dict[str, str], str, str, str]]:
    used = {candidate_key(row) for row in considered_rows}
    rules = load_tier_rules()
    ranked: list[tuple[dict[str, str], str, str, str]] = []
    for row in candidate_rows:
        if candidate_key(row) in used or not is_region_allowed(row):
            continue
        layer, reason, risk, review = classify_row(row, rules, profile)
        if layer != "冲" or row_bool(row, "is_sino_foreign"):
            continue
        ranked.append((row, reason, risk, review))

    def key(item: tuple[dict[str, str], str, str, str]) -> tuple[int, ...]:
        row = item[0]
        latest_gap = to_int(row.get("2025_rank_gap"))
        return (
            0 if is_undergraduate_level(row.get("degree_level")) else 1,
            1 if row.get("transfer_bridge") == "是" else 0,
            0 if row.get("is_public") == "是" else 1,
            region_priority(row, profile),
            major_priority(row, profile),
            0 if (to_int(row.get("history_year_count"), 0) or 0) >= 2 else 1,
            -(latest_gap if latest_gap is not None else -10**9),
        )

    ranked.sort(key=key)
    return ranked


def review_rows(
    ranked: list[tuple[dict[str, str], str, str, str]],
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for index, (row, reason, risk, review) in enumerate(ranked, start=1):
        output.append(
            {
                "推荐顺序": index,
                "学历层次": row.get("degree_level", ""),
                "省份": row.get("school_province", ""),
                "城市": row.get("city", ""),
                "院校代码": row.get("school_code", ""),
                "院校名称": row.get("school_name", ""),
                "专业代码": row.get("major_code", ""),
                "专业名称": row.get("major_name", ""),
                "学费": row.get("tuition", ""),
                "公民办": "公办" if row.get("is_public") == "是" else "民办",
                "2026招生计划数": row.get("plan_count", ""),
                "2025最低位次": row.get("2025_min_rank", ""),
                "2025位次差": row.get("2025_rank_gap", ""),
                "2024位次差": row.get("2024_rank_gap", ""),
                "2023位次差": row.get("2023_rank_gap", ""),
                "历史年份数": row.get("history_year_count", ""),
                "排序依据": reason,
                "风险提示": risk,
                "人工复核项": review,
            }
        )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="筛选已考虑清单之外的冲刺候选。")
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
        "--output",
        type=Path,
        default=ROOT / "outputs" / "additional_sprints" / "冲刺候选复核.csv",
    )
    args = parser.parse_args()

    ranked = ranked_sprint_candidates(
        read_csv_rows(args.considered),
        read_csv_rows(args.candidate_pool),
        read_json(args.profile),
    )
    write_csv_rows(args.output, review_rows(ranked), REVIEW_COLUMNS)
    print(f"已生成{len(ranked)}个未出现在已考虑表中的冲刺候选：{args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
