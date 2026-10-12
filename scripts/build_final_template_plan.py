from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from common import (
    ROOT,
    VOLUNTEER_COLUMNS,
    classify_row,
    load_tier_rules,
    read_csv_rows,
    read_json,
    to_int,
    volunteer_row_from_candidate,
    write_csv_rows,
)
from finalize_candidate_outputs import final_rows
from optimize_considered_plan import candidate_key, is_region_allowed


ADDITIONAL_SPRINT_KEYS = [
    ("温州科技职业学院", "大数据与会计"),
    ("义乌工商职业技术学院", "大数据与会计"),
    ("嘉兴职业技术学院", "现代物流管理"),
    ("浙江安防职业技术学院", "大数据与会计"),
    ("台州职业技术学院", "金融服务与管理"),
]
TARGET_COUNTS = {"冲": 19, "稳": 31, "保": 30}


def build_additional_sprints(
    considered: list[dict[str, str]],
    candidates: list[dict[str, str]],
    profile: dict[str, object],
) -> list[dict[str, object]]:
    candidate_map = {candidate_key(row): row for row in candidates}
    considered_keys = {candidate_key(row) for row in considered}
    considered_schools = {row.get("院校名称", "") for row in considered}
    rules = load_tier_rules()
    additional: list[dict[str, object]] = []

    for sequence, key in enumerate(ADDITIONAL_SPRINT_KEYS, start=1):
        if key in considered_keys:
            raise ValueError(f"新增冲刺与已考虑项重复：{key}")
        if key[0] in considered_schools:
            raise ValueError(f"新增冲刺院校已出现在已考虑表：{key[0]}")
        row = candidate_map.get(key)
        if row is None:
            raise ValueError(f"候选池缺少新增冲刺：{key}")
        if not is_region_allowed(row):
            raise ValueError(f"新增冲刺违反地域约束：{key}")
        tuition = to_int(row.get("tuition"))
        if tuition is None or tuition >= 15000:
            raise ValueError(f"新增冲刺学费未低于1.5万元：{key} -> {tuition}")
        layer, reason, risk, review = classify_row(row, rules, profile)
        if layer != "冲":
            raise ValueError(f"新增项不是冲刺层：{key} -> {layer}")
        additional.append(
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
    return final_rows(additional)


def choose_final_rows(
    considered: list[dict[str, str]],
    base_rows: list[dict[str, str]],
    additional: list[dict[str, object]],
) -> list[dict[str, object]]:
    if len(considered) != 20:
        raise ValueError(f"已考虑表应有20项，实际为{len(considered)}项")
    if len(base_rows) != 80:
        raise ValueError(f"基础志愿表应有80项，实际为{len(base_rows)}项")

    considered_by_tier = {
        tier: [dict(row) for row in considered if row.get("层级") == tier]
        for tier in ["冲", "稳", "保"]
    }
    if len(considered_by_tier["冲"]) + len(additional) != TARGET_COUNTS["冲"]:
        raise ValueError(
            "已考虑冲刺数加新增冲刺数与19个冲刺目标不一致："
            f"{len(considered_by_tier['冲'])}+{len(additional)}"
        )

    selected: list[dict[str, object]] = []
    used: set[tuple[str, str]] = set()

    def add(row: dict[str, object]) -> None:
        key = candidate_key(row)
        if key in used:
            return
        used.add(key)
        selected.append(dict(row))

    for row in considered_by_tier["冲"]:
        add(row)
    for row in additional:
        add(row)
    for row in considered_by_tier["稳"]:
        add(row)

    steady_needed = TARGET_COUNTS["稳"] - len(considered_by_tier["稳"])
    for row in base_rows:
        if row.get("层级") != "稳" or candidate_key(row) in used:
            continue
        add(row)
        steady_needed -= 1
        if steady_needed == 0:
            break
    if steady_needed:
        raise ValueError(f"稳志愿不足，还缺{steady_needed}项")

    for row in considered_by_tier["保"]:
        add(row)
    safe_needed = TARGET_COUNTS["保"] - len(considered_by_tier["保"])
    for row in base_rows:
        if row.get("层级") != "保" or candidate_key(row) in used:
            continue
        add(row)
        safe_needed -= 1
        if safe_needed == 0:
            break
    if safe_needed:
        raise ValueError(f"保志愿不足，还缺{safe_needed}项")

    if len(selected) != 80:
        raise ValueError(f"最终志愿应为80项，实际为{len(selected)}项")
    for sequence, row in enumerate(selected, start=1):
        row["志愿序号"] = sequence
    actual = Counter(str(row.get("层级", "")) for row in selected)
    if actual != Counter(TARGET_COUNTS):
        raise ValueError(f"冲稳保数量错误：{dict(actual)}")
    return selected


def validate_final_regions(
    rows: list[dict[str, object]],
    candidates: list[dict[str, str]],
) -> dict[str, int]:
    candidate_map = {candidate_key(row): row for row in candidates}
    missing = [candidate_key(row) for row in rows if candidate_key(row) not in candidate_map]
    if missing:
        raise ValueError(f"最终表有{len(missing)}项无法回查候选池：{missing[:3]}")
    northeast = 0
    jiangxi_non_nanchang = 0
    for row in rows:
        source = candidate_map[candidate_key(row)]
        if not is_region_allowed(source):
            if source.get("school_province") in {"辽宁", "吉林", "黑龙江"}:
                northeast += 1
            if source.get("school_province") == "江西" and source.get("city") != "南昌":
                jiangxi_non_nanchang += 1
    return {
        "northeast_count": northeast,
        "jiangxi_non_nanchang_count": jiangxi_non_nanchang,
    }


def summary_markdown(
    rows: list[dict[str, object]],
    considered: list[dict[str, str]],
    additional: list[dict[str, object]],
    region_checks: dict[str, int],
) -> str:
    counts = Counter(str(row.get("层级", "")) for row in rows)
    manual = sum(row.get("填报状态") == "必须人工确认" for row in rows)
    private = sum(row.get("是否民办") == "是" for row in rows)
    max_tuition = max(to_int(row.get("学费"), 0) or 0 for row in rows)
    lines = [
        "# 最终80志愿汇总",
        "",
        "## 组成",
        "",
        f"- 已考虑表：{len(considered)}项，全部保留。",
        f"- 新增低学费冲刺：{len(additional)}项。",
        "- 其余55项来自用户提供的最终80志愿排序表，去重后按原顺序补足稳保。",
        f"- 最终结构：冲{counts['冲']}、稳{counts['稳']}、保{counts['保']}。",
        f"- 必须人工确认：{manual}项；民办：{private}项。",
        f"- 全表最高学费：{max_tuition}元/年。新增5个冲刺均低于15000元/年。",
        f"- 东北：{region_checks['northeast_count']}项；江西非南昌：{region_checks['jiangxi_non_nanchang_count']}项。",
        "",
        "## 新增5个冲刺",
        "",
        "|顺序|院校|专业|城市|学费/年|2026计划|2025位次差|",
        "|---:|---|---|---|---:|---:|---:|",
    ]
    for row in additional:
        lines.append(
            f"|{row['志愿序号']}|{row['院校名称']}|{row['专业名称']}|"
            f"{row['城市']}|{row['学费']}|{row['2026招生计划数']}|{row['2025位次差']}|"
        )
    lines.extend(
        [
            "",
            "## 注意",
            "",
            "- 模板录入表只保留院校代码、院校名称、专业代码、专业名称四列。",
            "- 最终提交前必须在浙江官方系统核对代码、剩余计划和招生章程。",
            "- “可直接填”仍表示通过当前自动规则，不替代提交前的官方系统核对。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="合并用户选择并生成最终80模板数据。")
    parser.add_argument(
        "--considered",
        type=Path,
        default=ROOT / "data" / "raw" / "considered.csv",
    )
    parser.add_argument(
        "--base",
        type=Path,
        default=ROOT
        / "outputs"
        / "optimized_2026_460"
        / "最终80志愿排序表.csv",
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
        default=ROOT / "outputs" / "final_template_2026_460",
    )
    args = parser.parse_args()

    considered = read_csv_rows(args.considered)
    base_rows = read_csv_rows(args.base)
    candidates = read_csv_rows(args.candidate_pool)
    additional = build_additional_sprints(
        considered,
        candidates,
        read_json(args.profile),
    )
    final = choose_final_rows(considered, base_rows, additional)
    region_checks = validate_final_regions(final, candidates)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    write_csv_rows(
        args.output_dir / "最终80志愿排序表.csv",
        final,
        ["填报状态", "人工确认原因", *VOLUNTEER_COLUMNS],
    )
    write_csv_rows(
        args.output_dir / "新增5个冲刺.csv",
        additional,
        ["填报状态", "人工确认原因", *VOLUNTEER_COLUMNS],
    )
    (args.output_dir / "最终志愿数据.json").write_text(
        json.dumps(final, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    template_rows = [
        [
            str(row.get("院校代码", "")).zfill(4),
            str(row.get("院校名称", "")),
            str(row.get("专业代码", "")).zfill(3),
            str(row.get("专业名称", "")),
        ]
        for row in final
    ]
    (args.output_dir / "模板录入数据.json").write_text(
        json.dumps(template_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (args.output_dir / "最终选择说明.md").write_text(
        summary_markdown(final, considered, additional, region_checks),
        encoding="utf-8",
    )
    checks = {
        "total": len(final),
        "tier_counts": dict(Counter(str(row.get("层级", "")) for row in final)),
        "considered_retained": sum(
            candidate_key(row) in {candidate_key(item) for item in final}
            for row in considered
        ),
        "additional_sprints": len(additional),
        "additional_max_tuition": max(
            to_int(row.get("学费"), 0) or 0 for row in additional
        ),
        "duplicate_count": len(final)
        - len({candidate_key(row) for row in final}),
        **region_checks,
    }
    (args.output_dir / "最终约束检查.json").write_text(
        json.dumps(checks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(checks, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
