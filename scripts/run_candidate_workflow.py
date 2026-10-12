from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from common import (
    EXCLUDED_COLUMNS,
    HISTORICAL_YEARS,
    ROOT,
    VOLUNTEER_COLUMNS,
    add_rank_gaps,
    assess_undergraduate_opportunity,
    audit_rows,
    classify_and_select_volunteers,
    enrich_plan_with_school_info,
    generate_all_outputs,
    generate_candidate_pool_rows,
    load_profile,
    merge_plan_history_rows,
    read_csv_rows,
    read_json,
    write_csv_rows,
    write_json,
)
from second_stage_plan import OFFICIAL_PLAN_PORTAL


def copy_official_manifest(output_dir: Path) -> None:
    source = ROOT / "data" / "raw" / "official" / "source_manifest.csv"
    if source.exists():
        shutil.copyfile(source, output_dir / "official_source_manifest.csv")


def main() -> int:
    parser = argparse.ArgumentParser(description="基于用户档案运行浙江普通类二段工作流。")
    parser.add_argument("--profile", type=Path, default=ROOT / "examples" / "target_candidate.json")
    parser.add_argument("--processed-dir", type=Path, default=ROOT / "data" / "processed")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs" / "target_candidate")
    args = parser.parse_args()

    profile = load_profile(args.profile)
    context_path = args.processed_dir / "official_context.json"
    if context_path.exists():
        context = read_json(context_path)
        for field in ["first_segment_line", "second_segment_line", "remaining_queue_at_or_above"]:
            if field in context:
                profile[field] = context[field]

    plan_path = args.processed_dir / "admissions_plan.csv"
    historical_path = args.processed_dir / "historical_admission.csv"
    historical = read_csv_rows(historical_path) if historical_path.exists() else []
    plan_rows = read_csv_rows(plan_path) if plan_path.exists() else []
    school_path = args.processed_dir / "school_info.csv"
    school_rows = read_csv_rows(school_path) if school_path.exists() else []
    if school_rows:
        plan_rows = enrich_plan_with_school_info(plan_rows, school_rows)
    current_plan_verified = bool(plan_rows) and all(
        row.get("source_access") == "personalized-login-download" for row in plan_rows
    )
    profile["current_plan_verified"] = current_plan_verified
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_json(args.output_dir / "validated_input.json", profile)

    if not current_plan_verified:
        opportunity = assess_undergraduate_opportunity(
            profile,
            [],
            historical_rows=historical,
            current_plan_verified=False,
        )
        audit = audit_rows([], [], profile)
        generate_all_outputs(args.output_dir, profile, [], [], audit, opportunity)
        copy_official_manifest(args.output_dir)
        print("未检测到经登录下载并导入的2026个性化二段计划。")
        print("已生成历史判断，但没有生成任何2026院校专业推荐。")
        print(f"请从 {OFFICIAL_PLAN_PORTAL} 下载计划后运行 scripts/import_second_stage_plan.py。")
        print(f"历史判断报告：{args.output_dir / 'final_report.md'}")
        return 0

    merged = merge_plan_history_rows(plan_rows, historical)
    merged_fields = list(plan_rows[0].keys())
    for year in HISTORICAL_YEARS:
        merged_fields.extend([f"{year}_min_score", f"{year}_min_rank", f"{year}_plan_count"])
    merged_fields.extend(["plan_change", "history_match_method"])
    write_csv_rows(args.output_dir / "merged_plan_history.csv", merged, merged_fields)

    candidates, excluded = generate_candidate_pool_rows(profile, merged)
    candidate_fields = merged_fields + [
        "subject_match",
        "tuition_over_budget",
        "transfer_bridge",
        "medical_risk",
        "force_review",
        "candidate_notes",
    ]
    write_csv_rows(args.output_dir / "candidate_pool.csv", candidates, candidate_fields)
    write_csv_rows(args.output_dir / "excluded_list.csv", excluded, EXCLUDED_COLUMNS)

    ranked = add_rank_gaps(candidates, int(profile["rank"]))
    rank_fields = candidate_fields + [
        *[f"{year}_rank_gap" for year in HISTORICAL_YEARS],
        "history_year_count",
        "rank_stability",
    ]
    write_csv_rows(args.output_dir / "rank_gap.csv", ranked, rank_fields)
    volunteers = classify_and_select_volunteers(ranked, profile)
    write_csv_rows(args.output_dir / "volunteer_table.csv", volunteers, VOLUNTEER_COLUMNS)
    audit = audit_rows(volunteers, excluded, profile)
    opportunity = assess_undergraduate_opportunity(
        profile,
        ranked,
        historical_rows=historical,
        current_plan_verified=True,
    )
    generate_all_outputs(args.output_dir, profile, volunteers, excluded, audit, opportunity)
    copy_official_manifest(args.output_dir)
    print(
        f"工作流完成：本科可报{opportunity['undergraduate_eligible_count']}个，"
        f"共生成{len(volunteers)}个志愿。"
    )
    print(f"最终报告：{args.output_dir / 'final_report.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
