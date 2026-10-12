from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from common import (
    ROOT,
    VOLUNTEER_COLUMNS,
    candidate_sort_key,
    classify_row,
    is_undergraduate_level,
    load_tier_rules,
    major_priority,
    read_csv_rows,
    read_json,
    region_priority,
    row_bool,
    stringify,
    to_int,
    volunteer_row_from_candidate,
    write_csv_rows,
)


NORTHEAST_PROVINCES = {"辽宁", "吉林", "黑龙江"}
TARGET_COUNTS = {"冲": 5, "稳": 45, "保": 30}


def candidate_key(row: dict[str, object]) -> tuple[str, str]:
    return (
        stringify(row.get("school_name", row.get("院校名称", ""))).strip(),
        stringify(row.get("major_name", row.get("专业名称", ""))).strip(),
    )


def is_region_allowed(row: dict[str, object]) -> bool:
    province = stringify(row.get("school_province", "")).strip()
    city = stringify(row.get("city", row.get("城市", ""))).strip()
    if province in NORTHEAST_PROVINCES:
        return False
    if province == "江西" and city != "南昌":
        return False
    return True


def considered_sequence(row: dict[str, object]) -> int:
    return to_int(row.get("志愿序号"), 10**9) or 10**9


def sprint_choice_key(
    item: tuple[dict[str, object], str, str, str],
    original_sequence: dict[tuple[str, str], int],
) -> tuple[int, int, int, int]:
    row = item[0]
    history_missing = 1 if (to_int(row.get("history_year_count"), 0) or 0) < 2 else 0
    latest_gap = to_int(row.get("2025_rank_gap"), -10**9) or -10**9
    return (
        history_missing,
        -latest_gap,
        region_priority(row, {}),
        original_sequence.get(candidate_key(row), 10**9),
    )


def fill_sort_key(
    item: tuple[dict[str, object], str, str, str],
    profile: dict[str, object],
) -> tuple[int, int, int, int, int, int, int]:
    row = item[0]
    latest_gap = to_int(row.get("2025_rank_gap"), 10**9) or 10**9
    return (
        0 if stringify(row.get("is_public")) == "是" else 1,
        0 if not row_bool(row, "is_sino_foreign") else 1,
        region_priority(row, profile),
        major_priority(row, profile),
        0 if (to_int(row.get("history_year_count"), 0) or 0) >= 3 else 1,
        latest_gap,
        candidate_sort_key(row, profile)[-1],
    )


def add_with_school_cap(
    destination: list[tuple[dict[str, object], str, str, str, str]],
    candidates: list[tuple[dict[str, object], str, str, str]],
    layer: str,
    quota: int,
    used: set[tuple[str, str]],
    school_counts: Counter[str],
    school_cap: int | None,
    public_only: bool,
    exclude_sino_foreign: bool,
) -> None:
    for row, reason, risk, review in candidates:
        if len([item for item in destination if item[1] == layer]) >= quota:
            return
        key = candidate_key(row)
        if key in used:
            continue
        if public_only and stringify(row.get("is_public")) != "是":
            continue
        if exclude_sino_foreign and row_bool(row, "is_sino_foreign"):
            continue
        school_name = stringify(row.get("school_name"))
        if school_cap is not None and school_counts[school_name] >= school_cap:
            continue
        used.add(key)
        school_counts[school_name] += 1
        destination.append((row, layer, reason, risk, review))


def optimize(
    considered_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
    profile: dict[str, object],
) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    rules = load_tier_rules()
    allowed_rows = [row for row in candidate_rows if is_region_allowed(row)]
    allowed_map = {candidate_key(row): row for row in allowed_rows}
    original_sequence = {
        candidate_key(row): considered_sequence(row) for row in considered_rows
    }

    missing = [candidate_key(row) for row in considered_rows if candidate_key(row) not in allowed_map]
    if missing:
        raise ValueError(f"已考虑表中有{len(missing)}项无法在当前候选池匹配：{missing[:3]}")

    classified: list[tuple[dict[str, object], str, str, str, str]] = []
    by_key: dict[tuple[str, str], tuple[dict[str, object], str, str, str, str]] = {}
    for row in allowed_rows:
        layer, reason, risk, review = classify_row(row, rules, profile)
        item = (row, layer, reason, risk, review)
        classified.append(item)
        by_key[candidate_key(row)] = item

    considered_items = [by_key[candidate_key(row)] for row in considered_rows]
    considered_undergraduates = [
        item for item in considered_items if is_undergraduate_level(item[0].get("degree_level"))
    ]
    considered_undergraduates.sort(
        key=lambda item: original_sequence[candidate_key(item[0])]
    )
    if len(considered_undergraduates) > TARGET_COUNTS["冲"]:
        considered_undergraduates = considered_undergraduates[: TARGET_COUNTS["冲"]]

    remaining_sprint_slots = TARGET_COUNTS["冲"] - len(considered_undergraduates)
    considered_sprint_associates = [
        (item[0], item[2], item[3], item[4])
        for item in considered_items
        if item[1] == "冲" and not is_undergraduate_level(item[0].get("degree_level"))
    ]
    considered_sprint_associates.sort(
        key=lambda item: sprint_choice_key(item, original_sequence)
    )
    chosen_sprint_associates = considered_sprint_associates[:remaining_sprint_slots]

    selected: list[tuple[dict[str, object], str, str, str, str]] = []
    for row, _layer, reason, risk, review in considered_undergraduates:
        selected.append((row, "冲", reason, risk, review))
    for row, reason, risk, review in chosen_sprint_associates:
        selected.append((row, "冲", reason, risk, review))
    selected.sort(key=lambda item: original_sequence[candidate_key(item[0])])

    used = {candidate_key(item[0]) for item in selected}
    school_counts: Counter[str] = Counter(
        stringify(item[0].get("school_name")) for item in selected
    )

    for layer in ["稳", "保"]:
        locked = [item for item in considered_items if item[1] == layer]
        locked.sort(key=lambda item: original_sequence[candidate_key(item[0])])
        for row, actual_layer, reason, risk, review in locked:
            key = candidate_key(row)
            if key in used or len([item for item in selected if item[1] == layer]) >= TARGET_COUNTS[layer]:
                continue
            used.add(key)
            school_counts[stringify(row.get("school_name"))] += 1
            selected.append((row, actual_layer, reason, risk, review))

        pool = [
            (row, reason, risk, review)
            for row, actual_layer, reason, risk, review in classified
            if actual_layer == layer
            and not is_undergraduate_level(row.get("degree_level"))
        ]
        pool.sort(key=lambda item: fill_sort_key(item, profile))
        for public_only, exclude_sino, school_cap in [
            (True, True, 3),
            (True, True, None),
            (False, True, 4),
            (False, True, None),
            (False, False, None),
        ]:
            add_with_school_cap(
                selected,
                pool,
                layer,
                TARGET_COUNTS[layer],
                used,
                school_counts,
                school_cap,
                public_only,
                exclude_sino,
            )

    actual_counts = Counter(item[1] for item in selected)
    if any(actual_counts[layer] != count for layer, count in TARGET_COUNTS.items()):
        raise ValueError(
            f"候选池不足，目标{TARGET_COUNTS}，实际{dict(actual_counts)}"
        )

    ordered: list[tuple[dict[str, object], str, str, str, str]] = []
    for layer in ["冲", "稳", "保"]:
        ordered.extend(item for item in selected if item[1] == layer)
    volunteers = [
        volunteer_row_from_candidate(row, index + 1, profile, layer, reason, risk, review)
        for index, (row, layer, reason, risk, review) in enumerate(ordered)
    ]

    new_sequence = {candidate_key(row): row["志愿序号"] for row in volunteers}
    selected_keys = set(new_sequence)
    decisions: list[dict[str, object]] = []
    for row in sorted(considered_rows, key=considered_sequence):
        key = candidate_key(row)
        if key in selected_keys:
            decision = "纳入推荐80"
            reason = "保留已选项，并按新的冲稳保结构重新排序"
        else:
            decision = "候补冲刺"
            reason = "该项仍属于冲刺；为把冲刺控制在5个，暂不纳入推荐80"
        decisions.append(
            {
                "原序号": row.get("志愿序号", ""),
                "原层级": row.get("层级", ""),
                "院校名称": row.get("院校名称", ""),
                "专业名称": row.get("专业名称", ""),
                "处理结果": decision,
                "新序号": new_sequence.get(key, ""),
                "处理原因": reason,
            }
        )

    checks = {
        "target_counts": TARGET_COUNTS,
        "actual_counts": dict(actual_counts),
        "total": len(volunteers),
        "considered_total": len(considered_rows),
        "considered_retained": sum(1 for row in decisions if row["处理结果"] == "纳入推荐80"),
        "considered_backup_sprint": sum(1 for row in decisions if row["处理结果"] == "候补冲刺"),
        "northeast_count": sum(
            1 for row in ordered if stringify(row[0].get("school_province")) in NORTHEAST_PROVINCES
        ),
        "jiangxi_non_nanchang_count": sum(
            1
            for row in ordered
            if stringify(row[0].get("school_province")) == "江西"
            and stringify(row[0].get("city")) != "南昌"
        ),
        "private_associate_count": sum(
            1
            for row in ordered
            if not is_undergraduate_level(row[0].get("degree_level"))
            and row_bool(row[0], "is_private")
        ),
        "sino_foreign_count": sum(
            1 for row in ordered if row_bool(row[0], "is_sino_foreign")
        ),
        "jiangxi_nanchang_count": sum(
            1
            for row in ordered
            if stringify(row[0].get("school_province")) == "江西"
            and stringify(row[0].get("city")) == "南昌"
        ),
    }
    return volunteers, decisions, checks


def optimization_markdown(
    volunteers: list[dict[str, object]],
    decisions: list[dict[str, object]],
    checks: dict[str, object],
) -> str:
    sprint = [row for row in volunteers if row["层级"] == "冲"]
    backup = [row for row in decisions if row["处理结果"] == "候补冲刺"]
    lines = [
        "# 志愿优化说明",
        "",
        "## 推荐方案",
        "",
        "- 最终结构：冲5、稳45、保30。",
        "- 辽宁、吉林、黑龙江全部排除；江西仅保留南昌。",
        f"- “已考虑”20项中保留{checks['considered_retained']}项，另有{checks['considered_backup_sprint']}项转为候补冲刺。",
        f"- 民办专科{checks['private_associate_count']}项；中外合作{checks['sino_foreign_count']}项。",
        "- 只有2个本科，均为低概率冲刺；专科负责稳保。",
        "",
        "## 五个冲刺",
        "",
        "|新序号|院校|专业|学历层次|2025位次差|",
        "|---:|---|---|---|---:|",
    ]
    for row in sprint:
        lines.append(
            f"|{row['志愿序号']}|{row['院校名称']}|{row['专业名称']}|"
            f"{row['学历层次']}|{row['2025位次差']}|"
        )
    lines.extend(
        [
            "",
            "## 已考虑但转候补",
            "",
            "|原序号|院校|专业|原因|",
            "|---:|---|---|---|",
        ]
    )
    for row in backup:
        lines.append(
            f"|{row['原序号']}|{row['院校名称']}|{row['专业名称']}|{row['处理原因']}|"
        )
    lines.extend(
        [
            "",
            "## 还可调整的取舍",
            "",
            "- 如果20个“已考虑”必须全部保留，则冲刺数必须恢复到14，不能把真实冲刺项改标为稳。",
            "- 如果要求专科全部公办，在只保留5个冲的条件下，当前候选池无法补足80个；可选择减少志愿总数或增加冲刺项。",
            "- 民办专科虽然都在每年3万元学费上限内，仍应逐项确认城市、住宿费和真实就读意愿。",
            "- 提交前在浙江官方系统核对院校代码、专业代码、剩余计划和招生章程。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="按已考虑清单和新增地域条件优化80志愿。")
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
        default=ROOT / "outputs" / "optimized_2026_460",
    )
    args = parser.parse_args()

    volunteers, decisions, checks = optimize(
        read_csv_rows(args.considered),
        read_csv_rows(args.candidate_pool),
        read_json(args.profile),
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv_rows(
        args.output_dir / "optimized_volunteer_table.csv",
        volunteers,
        VOLUNTEER_COLUMNS,
    )
    write_csv_rows(
        args.output_dir / "已考虑取舍.csv",
        decisions,
        ["原序号", "原层级", "院校名称", "专业名称", "处理结果", "新序号", "处理原因"],
    )
    (args.output_dir / "优化约束检查.json").write_text(
        json.dumps(checks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (args.output_dir / "优化说明.md").write_text(
        optimization_markdown(volunteers, decisions, checks),
        encoding="utf-8",
    )
    print(json.dumps(checks, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
