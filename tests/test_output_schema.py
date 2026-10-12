from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from common import (
    AUDIT_COLUMNS,
    EXCLUDED_COLUMNS,
    VOLUNTEER_COLUMNS,
    audit_rows,
    build_report,
    raw_data_status,
    run_sample_pipeline,
)


def test_output_table_fields_complete():
    assert "志愿序号" in VOLUNTEER_COLUMNS
    assert "学历层次" in VOLUNTEER_COLUMNS
    assert "填报段次" in VOLUNTEER_COLUMNS
    assert "人工复核项" in VOLUNTEER_COLUMNS
    assert "排除原因" in EXCLUDED_COLUMNS
    assert "建议动作" in AUDIT_COLUMNS
    assert len(VOLUNTEER_COLUMNS) == 35


def test_candidate_shortage_report_explains_reason():
    profile = {
        "need_volunteer_table": True,
        "volunteer_count": 80,
        "application_stage": "二段",
        "score": 460,
        "rank": 220000,
        "subjects": ["思想政治", "历史", "地理"],
        "remaining_queue_at_or_above": 12000,
    }
    report = build_report(profile, [], [], audit_rows([], [], profile))
    assert "缺少登录后下载的2026个性化二段剩余计划" in report
    assert "用户可设置 1-80" in report
    assert "该数字不是原始位次" in report
    assert "本科资格" in report
    assert "听力状态" in report


def test_raw_data_missing_has_clear_message():
    raw_dir = ROOT / "outputs" / "test_empty_raw"
    shutil.rmtree(raw_dir, ignore_errors=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    ok, message = raw_data_status(raw_dir)
    assert not ok
    assert "data/raw/" in message


def test_sample_workflow_runs_complete():
    output_dir = ROOT / "outputs" / "test_sample_workflow"
    shutil.rmtree(output_dir, ignore_errors=True)
    result = run_sample_pipeline(ROOT, output_dir)
    assert len(result["volunteers"]) == 8
    assert (output_dir / "volunteer_table.csv").exists()
    assert (output_dir / "volunteer_table.xlsx").exists()
    assert (output_dir / "final_report.md").exists()
    assert (output_dir / "excluded_list.csv").exists()
    assert any(item["排除原因"].find("选科不符合") >= 0 for item in result["excluded"])
    assert all(
        row["层级"] == "冲"
        for row in result["volunteers"]
        if row["学历层次"] in {"本科", "职业本科"}
    )
