from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from common import apply_hard_filter


def profile():
    return {
        "subjects": ["物理", "化学", "生物"],
        "application_stage": "二段",
        "only_undergraduate": False,
        "accept_associate": True,
        "accept_private": False,
        "accept_sino_foreign": True,
        "target_region": "浙江全省",
        "rejected_majors": [],
        "accepted_majors": ["工科", "医学", "管理"],
        "foreign_language": "英语",
        "tuition_limit": 30000,
        "tuition_hard_cap": False,
        "transfer_bridge_majors": [],
        "medical_limits": ["色弱"],
        "medical_exclusions": [],
        "hearing_status": "正常",
    }


def row(**overrides):
    base = {
        "school_code": "MOCK",
        "school_name": "MOCK样例大学",
        "major_code": "M001",
        "major_name": "智能工程（sample）",
        "major_group": "工科",
        "city": "杭州",
        "application_stage": "二段",
        "degree_level": "本科",
        "subject_requirement": "物理+化学",
        "tuition": "6000",
        "remarks": "sample/mock",
        "is_private": "false",
        "is_sino_foreign": "false",
        "source_file": "sample/mock",
    }
    base.update(overrides)
    return base


def test_subject_mismatch_excluded():
    included, excluded = apply_hard_filter(row(subject_requirement="历史"), profile())
    assert included is None
    assert excluded is not None
    assert "选科不符合" in excluded["排除原因"]


def test_tuition_over_budget_flagged_not_excluded():
    included, excluded = apply_hard_filter(row(tuition="42000"), profile())
    assert excluded is None
    assert included is not None
    assert included["tuition_over_budget"] == "是"


def test_tuition_over_hard_cap_is_excluded():
    candidate = profile()
    candidate["tuition_hard_cap"] = True
    included, excluded = apply_hard_filter(row(tuition="42000"), candidate)
    assert included is None
    assert "学费超过每年30000元硬上限" in excluded["排除原因"]


def test_marxism_major_is_excluded():
    candidate = profile()
    candidate["rejected_majors"] = ["马克思主义"]
    included, excluded = apply_hard_filter(
        row(major_name="马克思主义理论", subject_requirement="不限"),
        candidate,
    )
    assert included is None
    assert "专业命中不接受专业" in excluded["排除原因"]


def test_ecommerce_is_kept_only_as_transfer_bridge():
    candidate = profile()
    candidate["transfer_bridge_majors"] = ["电子商务"]
    included, excluded = apply_hard_filter(
        row(major_name="电子商务", subject_requirement="不限"),
        candidate,
    )
    assert excluded is None
    assert included["transfer_bridge"] == "是"
    assert included["force_review"] == "是"
    assert any("转专业跳板" in note for note in included["candidate_notes"])


def test_medical_conflict_forces_review():
    included, excluded = apply_hard_filter(row(remarks="sample/mock 色弱需复核"), profile())
    assert excluded is None
    assert included is not None
    assert included["force_review"] == "是"


def test_private_excluded_when_user_rejects_private():
    included, excluded = apply_hard_filter(row(is_private="true"), profile())
    assert included is None
    assert "民办" in excluded["排除原因"]


def test_associate_excluded_when_user_rejects_associate():
    p = profile()
    p["accept_associate"] = False
    included, excluded = apply_hard_filter(row(degree_level="专科"), p)
    assert included is None
    assert "专科" in excluded["排除原因"]


def test_associate_allowed_when_user_accepts_associate():
    included, excluded = apply_hard_filter(row(degree_level="专科"), profile())
    assert excluded is None
    assert included is not None


def test_second_stage_undergraduate_is_allowed():
    included, excluded = apply_hard_filter(
        row(application_stage="二段", degree_level="本科", subject_requirement="不限"),
        profile(),
    )
    assert excluded is None
    assert included is not None


def test_politics_history_geography_excludes_physics_chemistry():
    candidate = profile()
    candidate["subjects"] = ["思想政治", "历史", "地理"]
    included, excluded = apply_hard_filter(row(subject_requirement="物理+化学"), candidate)
    assert included is None
    assert "选科不符合" in excluded["排除原因"]


def test_pending_hearing_requires_review():
    candidate = profile()
    candidate["hearing_status"] = "待确认"
    included, excluded = apply_hard_filter(row(subject_requirement="不限"), candidate)
    assert excluded is None
    assert included["force_review"] == "是"
    assert "听力" in included["medical_risk"]
