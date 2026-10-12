from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from common import classify_and_select_volunteers, classify_row


def test_new_major_not_classified_as_bao():
    layer, reason, risk, review = classify_row(
        {
            "history_year_count": 0,
            "plan_change": "新增专业或历史数据不足",
            "force_review": "否",
            "tuition_over_budget": "否",
        }
    )
    assert layer != "保"
    assert "历史数据不足" in reason
    assert "历史数据不足" in review


def test_large_plan_drop_downgrades_low_risk():
    layer, reason, risk, review = classify_row(
        {
            "history_year_count": 3,
            "2025_rank_gap": 10000,
            "2024_rank_gap": 12000,
            "2023_rank_gap": 13000,
            "plan_change": "大幅缩招",
            "force_review": "否",
            "tuition_over_budget": "否",
        }
    )
    assert layer == "稳"
    assert "大幅缩减" in risk
    assert "计划变化" in review


def test_second_stage_undergraduate_is_always_sprint():
    layer, reason, risk, review = classify_row(
        {
            "degree_level": "本科",
            "history_year_count": 3,
            "2025_rank_gap": 10000,
            "2024_rank_gap": 12000,
            "2023_rank_gap": 13000,
            "plan_change": "计划稳定",
            "force_review": "否",
            "tuition_over_budget": "否",
        },
        profile={"application_stage": "二段", "undergraduate_sprint_only": True},
    )
    assert layer == "冲"
    assert "二段本科" in reason


def test_undergraduates_are_ordered_before_associates():
    rows = [
        {
            "school_code": "A",
            "major_code": "1",
            "degree_level": "专科",
            "history_year_count": 3,
            "2025_rank_gap": 10000,
            "2024_rank_gap": 10000,
            "2023_rank_gap": 10000,
        },
        {
            "school_code": "B",
            "major_code": "2",
            "degree_level": "本科",
            "history_year_count": 3,
            "2025_rank_gap": -20000,
            "2024_rank_gap": -20000,
            "2023_rank_gap": -20000,
        },
    ]
    profile = {
        "need_volunteer_table": True,
        "volunteer_count": 2,
        "application_stage": "二段",
        "undergraduate_sprint_only": True,
        "rank": 220000,
    }
    result = classify_and_select_volunteers(rows, profile)
    assert result[0]["学历层次"] == "本科"
    assert result[0]["层级"] == "冲"
    assert result[1]["学历层次"] == "专科"


def test_ecommerce_bridge_is_sprint_and_ordered_after_regular_undergraduate():
    rows = [
        {
            "school_code": "BRIDGE",
            "major_code": "1",
            "major_name": "电子商务",
            "degree_level": "本科",
            "transfer_bridge": "是",
            "history_year_count": 3,
            "2025_rank_gap": 5000,
            "2024_rank_gap": 5000,
            "2023_rank_gap": 5000,
        },
        {
            "school_code": "PRIMARY",
            "major_code": "2",
            "major_name": "财务管理",
            "degree_level": "本科",
            "transfer_bridge": "否",
            "history_year_count": 3,
            "2025_rank_gap": -20000,
            "2024_rank_gap": -20000,
            "2023_rank_gap": -20000,
        },
    ]
    candidate = {
        "need_volunteer_table": True,
        "volunteer_count": 2,
        "application_stage": "二段",
        "undergraduate_sprint_only": True,
        "rank": 220000,
    }
    result = classify_and_select_volunteers(rows, candidate)
    assert result[0]["专业名称"] == "财务管理"
    assert result[1]["专业名称"] == "电子商务"
    assert result[1]["层级"] == "冲"
    assert "转专业跳板" in result[1]["排序理由"]
    assert "转专业政策" in result[1]["人工复核项"]
