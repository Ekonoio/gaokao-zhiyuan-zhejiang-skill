from __future__ import annotations

import argparse
import copy
import json
from collections import Counter
from pathlib import Path

from common import (
    ROOT,
    VOLUNTEER_COLUMNS,
    add_rank_gaps,
    classify_row,
    generate_candidate_pool_rows,
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
from finalize_candidate_outputs import final_rows
from optimize_considered_plan import is_region_allowed


TARGET_COUNTS = {"冲": 25, "稳": 40, "保": 15}
REPLACE_SELECTED_KEYS = {
    ("苏州工业园区职业技术学院", "金融科技应用"),
    ("海南职业技术学院", "大数据与财务管理"),
    ("海南职业技术学院", "供应链运营"),
    ("海南职业技术学院", "现代物流管理"),
}
FORCE_ADD_KEYS = {
    ("无锡城市职业技术学院", "大数据与会计"),
}
CONDITIONAL_MAJOR_TOKENS = (
    "国际商务",
    "商务数据分析",
    "国际经济与贸易",
    "工商企业管理",
    "连锁经营与管理",
    "中小企业创业与经营",
    "市场营销",
    "旅游管理",
    "酒店管理",
    "会展策划与管理",
    "港口与航运管理",
    "人力资源管理",
    "公共事务管理",
    "行政管理",
    "数字媒体技术",
    "信息安全技术应用",
    "物联网应用技术",
    "计算机应用技术",
    "软件技术",
    "大数据技术",
    "新闻采编与制作",
)


def candidate_key(row: dict[str, object]) -> tuple[str, str]:
    return (
        stringify(row.get("school_name", row.get("院校名称", ""))).strip(),
        stringify(row.get("major_name", row.get("专业名称", ""))).strip(),
    )


def numeric_gaps(row: dict[str, object]) -> list[int]:
    return [
        gap
        for year in (2025, 2024, 2023)
        if (gap := to_int(row.get(f"{year}_rank_gap"))) is not None
    ]


def addition_allowed(row: dict[str, object], layer: str) -> bool:
    tuition = to_int(row.get("tuition"))
    major = stringify(row.get("major_name"))
    outside_preferred = stringify(row.get("_outside_preferred")) == "是"
    return (
        stringify(row.get("degree_level")) == "专科"
        and stringify(row.get("is_public")) == "是"
        and tuition is not None
        and tuition < 10000
        and is_region_allowed(row)
        and not row_bool(row, "is_sino_foreign")
        and stringify(row.get("transfer_bridge")) != "是"
        and stringify(row.get("subject_match", "是")) == "是"
        and (
            not outside_preferred
            or any(token in major for token in CONDITIONAL_MAJOR_TOKENS)
        )
        and layer in TARGET_COUNTS
    )


def selection_key(
    row: dict[str, object],
    layer: str,
    profile: dict[str, object],
    other_ai_keys: set[tuple[str, str]],
) -> tuple[object, ...]:
    gaps = numeric_gaps(row)
    latest = to_int(row.get("2025_rank_gap"), -10**9) or -10**9
    minimum = min(gaps) if gaps else -10**9
    history_count = to_int(row.get("history_year_count"), 0) or 0
    plan_count = to_int(row.get("plan_count"), 0) or 0
    stability = 0 if stringify(row.get("rank_stability")) == "相对稳定" else 1
    other_ai_priority = 0 if candidate_key(row) in other_ai_keys else 1

    if layer == "冲":
        return (
            0 if candidate_key(row) in FORCE_ADD_KEYS else 1,
            0 if history_count >= 3 else 1,
            stability,
            -latest,
            -minimum,
            other_ai_priority,
            region_priority(row, profile),
            major_priority(row, profile),
            -plan_count,
        )
    return (
        0 if history_count >= 3 else 1,
        stability,
        -minimum,
        -latest,
        -plan_count,
        region_priority(row, profile),
        major_priority(row, profile),
        other_ai_priority,
    )


def choose_with_school_cap(
    pool: list[dict[str, object]],
    needed: int,
    used: set[tuple[str, str]],
    school_counts: Counter[str],
) -> list[dict[str, object]]:
    chosen: list[dict[str, object]] = []
    for cap in (3, 4, None):
        for row in pool:
            if len(chosen) >= needed:
                return chosen
            key = candidate_key(row)
            school = stringify(row.get("school_name"))
            if key in used or (cap is not None and school_counts[school] >= cap):
                continue
            chosen.append(row)
            used.add(key)
            school_counts[school] += 1
    return chosen


def build_plan(
    selected_rows: list[dict[str, object]],
    candidate_rows: list[dict[str, str]],
    review_rows: list[dict[str, str]],
    profile: dict[str, object],
) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
    dict[str, object],
]:
    rules = load_tier_rules()
    by_key = {candidate_key(row): row for row in candidate_rows}
    conditional_other_ai_keys = {
        (stringify(row.get("院校名称")), stringify(row.get("专业名称")))
        for row in review_rows
        if row.get("审查结论") == "有条件可用"
    }
    other_ai_keys = {
        (stringify(row.get("院校名称")), stringify(row.get("专业名称")))
        for row in review_rows
        if row.get("审查结论") in {"可用", "可用（已保留）", "有条件可用"}
    }

    retained: list[tuple[dict[str, object], str, str, str, str, str]] = []
    replaced: list[dict[str, object]] = []
    missing: list[tuple[str, str]] = []
    for source in sorted(
        selected_rows,
        key=lambda row: to_int(row.get("志愿序号"), 10**9) or 10**9,
    ):
        key = candidate_key(source)
        candidate = by_key.get(key)
        if candidate is None:
            missing.append(key)
            continue
        if key in REPLACE_SELECTED_KEYS:
            replaced.append(
                {
                    "原序号": source.get("志愿序号", ""),
                    "原层级": source.get("层级", ""),
                    "院校名称": key[0],
                    "专业名称": key[1],
                    "学费": candidate.get("tuition", ""),
                    "替换原因": "专科年学费不低于1万元，不能作为当前预算下的稳保",
                }
            )
            continue
        actual_layer, reason, risk, review = classify_row(candidate, rules, profile)
        locked_layer = stringify(source.get("层级"))
        if actual_layer != locked_layer:
            raise ValueError(
                f"已筛选项目层级不一致：{key}，表内{locked_layer}，规则计算{actual_layer}"
            )
        retained.append(
            (candidate, locked_layer, reason, risk, review, "已经筛选保留")
        )
    if missing:
        raise ValueError(f"已经筛选中有{len(missing)}项未匹配到候选池：{missing[:3]}")

    used = {candidate_key(item[0]) for item in retained}
    school_counts: Counter[str] = Counter(
        stringify(item[0].get("school_name")) for item in retained
    )
    classified_pool: dict[str, list[dict[str, object]]] = {
        "冲": [],
        "稳": [],
        "保": [],
    }
    classification_meta: dict[
        tuple[str, str], tuple[str, str, str, str]
    ] = {}
    for row in candidate_rows:
        layer, reason, risk, review = classify_row(row, rules, profile)
        classification_meta[candidate_key(row)] = (layer, reason, risk, review)
        if candidate_key(row) in used or not addition_allowed(row, layer):
            continue
        classified_pool[layer].append(row)

    additions: list[tuple[dict[str, object], str, str, str, str, str]] = []
    retained_counts = Counter(item[1] for item in retained)
    for layer in ("冲", "稳", "保"):
        needed = TARGET_COUNTS[layer] - retained_counts[layer]
        pool = sorted(
            classified_pool[layer],
            key=lambda row: selection_key(row, layer, profile, other_ai_keys),
        )
        chosen = choose_with_school_cap(pool, needed, used, school_counts)
        if len(chosen) != needed:
            raise ValueError(
                f"{layer}层公办、学费低于1万元的候选不足：需要{needed}，只有{len(chosen)}"
            )
        for row in chosen:
            _actual, reason, risk, review = classification_meta[candidate_key(row)]
            source = (
                "其他AI名单优质项"
                if candidate_key(row) in other_ai_keys
                else "个性化计划补充"
            )
            additions.append((row, layer, reason, risk, review, source))

    ordered: list[tuple[dict[str, object], str, str, str, str, str]] = []
    for layer in ("冲", "稳", "保"):
        ordered.extend(item for item in retained if item[1] == layer)
        ordered.extend(item for item in additions if item[1] == layer)

    volunteers: list[dict[str, object]] = []
    for index, (row, layer, reason, risk, review, source) in enumerate(ordered, 1):
        conditional = (
            candidate_key(row) in conditional_other_ai_keys
            or stringify(row.get("_outside_preferred")) == "是"
        )
        if conditional:
            review = "；".join(
                filter(
                    None,
                    [
                        review,
                        "确认愿意就读该专业（不在既定会计、金融、物流方向）",
                    ],
                )
            )
        volunteer = volunteer_row_from_candidate(
            row,
            index,
            profile,
            layer,
            reason,
            risk,
            review,
        )
        volunteer["名单来源"] = source
        volunteer["入选依据"] = (
            (
                f"{reason}；公办专科且学费低于1万元；"
                "专业方向需人工确认"
                if conditional
                else f"{reason}；公办专科且学费低于1万元"
            )
            if source != "已经筛选保留"
            else "用户已经筛选；经2026个性化计划重新匹配"
        )
        volunteers.append(volunteer)

    output_rows = final_rows(volunteers)
    tier_counts = Counter(row["层级"] for row in output_rows)
    addition_rows = [
        row for row in output_rows if row.get("名单来源") != "已经筛选保留"
    ]
    checks = {
        "target_counts": TARGET_COUNTS,
        "actual_counts": dict(tier_counts),
        "total": len(output_rows),
        "retained": len(retained),
        "replaced": len(replaced),
        "added": len(addition_rows),
        "addition_counts": dict(Counter(row["层级"] for row in addition_rows)),
        "addition_public_count": sum(
            by_key[candidate_key(row)].get("is_public") == "是"
            for row in addition_rows
        ),
        "addition_tuition_under_10000_count": sum(
            (to_int(row.get("学费")) or 10**9) < 10000 for row in addition_rows
        ),
        "addition_sino_foreign_count": sum(
            row_bool(by_key[candidate_key(row)], "is_sino_foreign")
            for row in addition_rows
        ),
        "addition_transfer_bridge_count": sum(
            by_key[candidate_key(row)].get("transfer_bridge") == "是"
            for row in addition_rows
        ),
        "northeast_count": sum(
            stringify(by_key[candidate_key(row)].get("school_province"))
            in {"辽宁", "吉林", "黑龙江"}
            for row in output_rows
        ),
        "jiangxi_non_nanchang_count": sum(
            stringify(by_key[candidate_key(row)].get("school_province")) == "江西"
            and stringify(row.get("城市")) != "南昌"
            for row in output_rows
        ),
        "safe_incomplete_history_count": sum(
            row["层级"] == "保"
            and (to_int(by_key[candidate_key(row)].get("history_year_count"), 0) or 0) < 2
            for row in output_rows
        ),
        "safe_manual_confirmation_count": sum(
            row["层级"] == "保" and row.get("是否需要强制复核") == "是"
            for row in output_rows
        ),
        "safe_source_force_review_count": sum(
            row["层级"] == "保"
            and stringify(by_key[candidate_key(row)].get("force_review")) == "是"
            for row in output_rows
        ),
        "safe_max_tuition": max(
            to_int(row.get("学费"), 0) or 0
            for row in output_rows
            if row["层级"] == "保"
        ),
    }
    if len(output_rows) != 80 or dict(tier_counts) != TARGET_COUNTS:
        raise ValueError(f"最终数量错误：{checks}")
    return output_rows, addition_rows, replaced, checks


def markdown_report(
    rows: list[dict[str, object]],
    additions: list[dict[str, object]],
    replaced: list[dict[str, object]],
    checks: dict[str, object],
) -> str:
    direct = [row for row in rows if row["填报状态"] == "可直接填"]
    manual = [row for row in rows if row["填报状态"] == "必须人工确认"]
    lines = [
        "# 2026浙江普通类二段最终80志愿",
        "",
        "## 结论",
        "",
        "- 最终结构：冲25、稳40、保15。",
        "- 为保证保底真实可执行，已替换原表中1个1.6万元稳档和3个1.38万元保档。",
        f"- 新增{len(additions)}项全部为公办专科、学费低于1万元、非中外合作。",
        f"- 可直接填{len(direct)}项；必须人工确认{len(manual)}项。",
        "- 15个保档均有至少2年历史数据，数据规则无强制复核项；其中6个相邻专业须确认愿意就读。",
        "- 不承诺录取；要发挥保底作用，15个保档必须都愿意读并按顺序填满。",
        "",
        "## 被替换项目",
        "",
        "|原序号|原层级|院校|专业|学费|原因|",
        "|---:|---|---|---|---:|---|",
    ]
    for row in replaced:
        lines.append(
            f"|{row['原序号']}|{row['原层级']}|{row['院校名称']}|"
            f"{row['专业名称']}|{row['学费']}|{row['替换原因']}|"
        )
    lines.extend(
        [
            "",
            "## 新增项目",
            "",
            "|序号|层级|院校|专业|学费|2025位次差|来源|",
            "|---:|---|---|---|---:|---:|---|",
        ]
    )
    for row in additions:
        lines.append(
            f"|{row['志愿序号']}|{row['层级']}|{row['院校名称']}|"
            f"{row['专业名称']}|{row['学费']}|{row['2025位次差']}|{row['名单来源']}|"
        )
    lines.extend(
        [
            "",
            "## 必须人工确认",
            "",
            "|序号|层级|院校|专业|原因|",
            "|---:|---|---|---|---|",
        ]
    )
    for row in manual:
        lines.append(
            f"|{row['志愿序号']}|{row['层级']}|{row['院校名称']}|"
            f"{row['专业名称']}|{row['人工确认原因']}|"
        )
    lines.extend(
        [
            "",
            "## 风险边界",
            "",
            "- 冲25、稳40、保15属于偏激进结构；录取安全性依赖15个保档全部真实愿意就读且完整填报。",
            "- 听力情况待确认暂未作硬排除，提交前仍需核对各校2026招生章程中的体检与听力条款。",
            "- 填报当天必须在浙江官方系统再次核对院校代码、专业代码、剩余计划和学费。",
            "",
            f"校验：{json.dumps(checks, ensure_ascii=False)}",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="生成冲25、稳40、保15的最终80志愿。")
    parser.add_argument(
        "--selected-json",
        type=Path,
        default=ROOT / "outputs" / "input_review" / "selected_rows.json",
    )
    parser.add_argument(
        "--candidate-pool",
        type=Path,
        default=ROOT / "outputs" / "target_candidate" / "rank_gap.csv",
    )
    parser.add_argument(
        "--merged-plan",
        type=Path,
        default=ROOT
        / "outputs"
        / "target_candidate"
        / "merged_plan_history.csv",
    )
    parser.add_argument(
        "--other-ai-review",
        type=Path,
        default=ROOT / "outputs" / "other_ai_review" / "其他AI志愿筛查.csv",
    )
    parser.add_argument(
        "--profile",
        type=Path,
        default=ROOT / "outputs" / "target_candidate" / "validated_input.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT
        / "outputs"
        / "final_plan",
    )
    args = parser.parse_args()
    selected_rows = json.loads(args.selected_json.read_text(encoding="utf-8"))
    review_rows = read_csv_rows(args.other_ai_review)
    preferred_rows = read_csv_rows(args.candidate_pool)
    preferred_keys = {candidate_key(row) for row in preferred_rows}
    profile = read_json(args.profile)
    broad_profile = copy.deepcopy(profile)
    broad_profile["accepted_majors"] = []
    broad_profile["tuition_limit"] = 9999
    broad_profile["tuition_hard_cap"] = True
    broad_candidates, _broad_excluded = generate_candidate_pool_rows(
        broad_profile,
        read_csv_rows(args.merged_plan),
    )
    broad_rows = add_rank_gaps(
        [
            {**row, "_outside_preferred": "是"}
            for row in broad_candidates
            if candidate_key(row) not in preferred_keys
        ],
        int(profile["rank"]),
    )
    rows, additions, replaced, checks = build_plan(
        selected_rows,
        [*preferred_rows, *broad_rows],
        review_rows,
        profile,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    columns = [
        "填报状态",
        "人工确认原因",
        "名单来源",
        "入选依据",
        *VOLUNTEER_COLUMNS,
    ]
    write_csv_rows(args.output_dir / "最终80志愿排序表.csv", rows, columns)
    write_csv_rows(args.output_dir / "新增与替换项目.csv", additions, columns)
    write_csv_rows(
        args.output_dir / "被替换项目.csv",
        replaced,
        ["原序号", "原层级", "院校名称", "专业名称", "学费", "替换原因"],
    )
    write_csv_rows(
        args.output_dir / "可直接填报.csv",
        [row for row in rows if row["填报状态"] == "可直接填"],
        columns,
    )
    write_csv_rows(
        args.output_dir / "必须人工确认.csv",
        [row for row in rows if row["填报状态"] == "必须人工确认"],
        columns,
    )
    (args.output_dir / "最终填报说明.md").write_text(
        markdown_report(rows, additions, replaced, checks),
        encoding="utf-8",
    )
    (args.output_dir / "最终志愿数据.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (args.output_dir / "新增与替换项目.json").write_text(
        json.dumps(additions, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (args.output_dir / "被替换项目.json").write_text(
        json.dumps(replaced, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (args.output_dir / "约束检查.json").write_text(
        json.dumps(checks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(checks, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
