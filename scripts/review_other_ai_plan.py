from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from common import (
    ROOT,
    add_rank_gaps,
    classify_row,
    load_tier_rules,
    read_csv_rows,
    read_json,
    row_bool,
    stringify,
    subject_matches,
    to_int,
    write_csv_rows,
)
from optimize_considered_plan import is_region_allowed


REVIEW_COLUMNS = [
    "原序号",
    "其他AI梯度",
    "院校名称",
    "专业名称",
    "审查结论",
    "不能用或调整原因",
    "是否已在已经筛选",
    "2026院校代码",
    "2026专业代码",
    "学历层次",
    "城市",
    "公民办",
    "学费",
    "2026计划数",
    "选科要求",
    "实际层级",
    "2025最低位次",
    "2025位次差",
    "历史年份数",
]


def normalize_text(value: object) -> str:
    text = stringify(value).strip()
    replacements = {
        "（": "(",
        "）": ")",
        "，": ",",
        "－": "-",
        "—": "-",
        "　": "",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return re.sub(r"\s+", "", text)


def key_for(school: object, major: object) -> tuple[str, str]:
    return normalize_text(school), normalize_text(major)


def build_index(
    rows: list[dict[str, str]],
    school_key: str,
    major_key: str,
) -> dict[tuple[str, str], list[dict[str, str]]]:
    index: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        index[key_for(row.get(school_key), row.get(major_key))].append(row)
    return index


def review_rows(
    other_ai: list[dict[str, object]],
    selected: list[dict[str, object]],
    merged_plan: list[dict[str, str]],
    candidates: list[dict[str, str]],
    excluded: list[dict[str, str]],
    profile: dict[str, object],
) -> list[dict[str, object]]:
    plan_index = build_index(merged_plan, "school_name", "major_name")
    candidate_index = build_index(candidates, "school_name", "major_name")
    excluded_index = build_index(excluded, "院校名称", "专业名称")
    selected_keys = {
        key_for(row.get("院校名称"), row.get("专业名称")) for row in selected
    }
    plan_schools = {
        normalize_text(row.get("school_name")) for row in merged_plan
    }
    rules = load_tier_rules()
    tier_map = {
        "冲刺": "冲",
        "稳妥": "稳",
        "继续稳妥": "稳",
        "保底": "保",
    }
    output: list[dict[str, object]] = []
    first_seen_sequence: dict[tuple[str, str], object] = {}

    for source in other_ai:
        school = source.get("院校", "")
        major = source.get("专业", "")
        key = key_for(school, major)
        plan_matches = plan_index.get(key, [])
        candidate_matches = candidate_index.get(key, [])
        exclusion_matches = excluded_index.get(key, [])
        selected_already = key in selected_keys
        conclusion = "不可用"
        reasons: list[str] = []
        plan = plan_matches[0] if plan_matches else {}
        plan_enriched = (
            add_rank_gaps([dict(plan)], int(profile["rank"]))[0]
            if plan_matches
            else {}
        )
        candidate = candidate_matches[0] if candidate_matches else {}
        actual_layer = ""

        if not plan_matches:
            if normalize_text(school) not in plan_schools:
                reasons.append("2026个性化剩余计划中没有该院校")
            else:
                reasons.append("该院校2026个性化剩余计划中没有此专业")
        elif not candidate_matches:
            exclusion_reason = (
                exclusion_matches[0].get("排除原因", "")
                if exclusion_matches
                else ""
            )
            tuition = to_int(plan_enriched.get("tuition"))
            preference_only = exclusion_reason == "专业不在可接受专业范围"
            otherwise_eligible = (
                plan_enriched.get("degree_level") == "专科"
                and plan_enriched.get("is_public") == "是"
                and tuition is not None
                and tuition < 10000
                and is_region_allowed(plan_enriched)
                and subject_matches(
                    stringify(plan_enriched.get("subject_requirement")),
                    list(profile.get("subjects", [])),
                )
                and not row_bool(plan_enriched, "is_sino_foreign")
            )
            if preference_only and otherwise_eligible:
                actual_layer, _reason, _risk, _review = classify_row(
                    plan_enriched,
                    rules,
                    profile,
                )
                conclusion = "有条件可用"
                reasons.append("专业不在既定方向，仅在考生愿意就读时可用")
            elif exclusion_matches:
                reasons.append(exclusion_reason or "未通过当前筛选规则")
            else:
                reasons.append("未通过当前选科、专业或体检筛选规则")
        else:
            actual_layer, _reason, _risk, _review = classify_row(
                candidate,
                rules,
                profile,
            )
            tuition = to_int(candidate.get("tuition"))
            if candidate.get("degree_level") != "专科":
                reasons.append("本次补充限定公办专科")
            if candidate.get("is_public") != "是":
                reasons.append("不是公办院校")
            if tuition is None:
                reasons.append("学费缺失，不能确认低于1万元")
            elif tuition >= 10000:
                reasons.append(f"学费{tuition}元，不符合低于1万元要求")
            if not is_region_allowed(candidate):
                reasons.append("违反地域要求：东北排除，江西仅限南昌")
            if candidate.get("transfer_bridge") == "是":
                reasons.append("电子商务类只能作转专业跳板，不能承担稳保")

            if not reasons:
                conclusion = "可用（已保留）" if selected_already else "可用"
                claimed = tier_map.get(str(source.get("梯度", "")), "")
                if claimed and claimed != actual_layer:
                    reasons.append(
                        f"其他AI标为{claimed}，按当前历史位次应调整为{actual_layer}"
                    )

        if conclusion == "不可用" and selected_already:
            reasons.append("虽然已在当前表中，但需按当前人工筛选结果复核")
        if conclusion.startswith("可用") and not reasons:
            reasons.append("通过2026计划、专业方向、公办、学费和地域规则")
        if key in first_seen_sequence:
            conclusion = "不可用"
            reasons.insert(
                0,
                f"与原序号{first_seen_sequence[key]}重复，不能重复占用志愿名额",
            )
        else:
            first_seen_sequence[key] = source.get("序号", "")

        detail = candidate or plan_enriched or plan
        output.append(
            {
                "原序号": source.get("序号", ""),
                "其他AI梯度": source.get("梯度", ""),
                "院校名称": school,
                "专业名称": major,
                "审查结论": conclusion,
                "不能用或调整原因": "；".join(dict.fromkeys(reasons)),
                "是否已在已经筛选": "是" if selected_already else "否",
                "2026院校代码": detail.get("school_code", ""),
                "2026专业代码": detail.get("major_code", ""),
                "学历层次": detail.get("degree_level", ""),
                "城市": detail.get("city", ""),
                "公民办": (
                    "公办"
                    if detail.get("is_public") == "是"
                    else "民办"
                    if row_bool(detail, "is_private")
                    else "待核验"
                ),
                "学费": detail.get("tuition", ""),
                "2026计划数": detail.get("plan_count", ""),
                "选科要求": detail.get("subject_requirement", ""),
                "实际层级": actual_layer,
                "2025最低位次": detail.get("2025_min_rank", ""),
                "2025位次差": detail.get("2025_rank_gap", ""),
                "历史年份数": detail.get("history_year_count", ""),
            }
        )
    return output


def markdown_summary(rows: list[dict[str, object]]) -> str:
    usable = [row for row in rows if str(row["审查结论"]).startswith("可用")]
    conditional = [row for row in rows if row["审查结论"] == "有条件可用"]
    unusable = [row for row in rows if row["审查结论"] == "不可用"]
    lines = [
        "# 其他AI志愿组合筛查结果",
        "",
        f"- 原表实际有{len(rows)}项，不是80项。",
        f"- 可直接用{len(usable)}项，有条件可用{len(conditional)}项，不可用{len(unusable)}项。",
        "- 规则：必须出现在2026个性化剩余计划；符合既定专业方向；公办专科；学费低于1万元；地域符合；电子商务不能承担稳保。",
        "",
        "## 可用项目",
        "",
        "|原序号|原梯度|院校|专业|实际层级|是否已保留|调整说明|",
        "|---:|---|---|---|---|---|---|",
    ]
    for row in usable:
        lines.append(
            f"|{row['原序号']}|{row['其他AI梯度']}|{row['院校名称']}|"
            f"{row['专业名称']}|{row['实际层级']}|{row['是否已在已经筛选']}|"
            f"{row['不能用或调整原因']}|"
        )
    lines.extend(
        [
            "",
            "## 有条件可用项目",
            "",
            "|原序号|原梯度|院校|专业|实际层级|条件|",
            "|---:|---|---|---|---|---|",
        ]
    )
    for row in conditional:
        lines.append(
            f"|{row['原序号']}|{row['其他AI梯度']}|{row['院校名称']}|"
            f"{row['专业名称']}|{row['实际层级']}|{row['不能用或调整原因']}|"
        )
    lines.extend(
        [
            "",
            "## 不可用项目",
            "",
            "|原序号|原梯度|院校|专业|原因|",
            "|---:|---|---|---|---|",
        ]
    )
    for row in unusable:
        lines.append(
            f"|{row['原序号']}|{row['其他AI梯度']}|{row['院校名称']}|"
            f"{row['专业名称']}|{row['不能用或调整原因']}|"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="筛查其他AI生成的志愿组合。")
    parser.add_argument(
        "--other-ai-json",
        type=Path,
        default=ROOT / "outputs" / "input_review" / "other_ai_rows.json",
    )
    parser.add_argument(
        "--selected-json",
        type=Path,
        default=ROOT / "outputs" / "input_review" / "selected_rows.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "outputs" / "other_ai_review",
    )
    args = parser.parse_args()
    profile = read_json(ROOT / "outputs" / "target_candidate" / "validated_input.json")
    rows = review_rows(
        json.loads(args.other_ai_json.read_text(encoding="utf-8")),
        json.loads(args.selected_json.read_text(encoding="utf-8")),
        read_csv_rows(ROOT / "outputs" / "target_candidate" / "merged_plan_history.csv"),
        read_csv_rows(ROOT / "outputs" / "target_candidate" / "rank_gap.csv"),
        read_csv_rows(ROOT / "outputs" / "target_candidate" / "excluded_list.csv"),
        profile,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv_rows(args.output_dir / "其他AI志愿筛查.csv", rows, REVIEW_COLUMNS)
    (args.output_dir / "其他AI志愿筛查.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (args.output_dir / "其他AI志愿筛查说明.md").write_text(
        markdown_summary(rows),
        encoding="utf-8",
    )
    usable = [row for row in rows if str(row["审查结论"]).startswith("可用")]
    conditional = [row for row in rows if row["审查结论"] == "有条件可用"]
    unusable = [row for row in rows if row["审查结论"] == "不可用"]
    print(
        json.dumps(
            {
                "total": len(rows),
                "usable": len(usable),
                "conditional": len(conditional),
                "unusable": len(unusable),
                "already_selected": sum(
                    row["是否已在已经筛选"] == "是" for row in rows
                ),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
