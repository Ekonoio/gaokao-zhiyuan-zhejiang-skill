from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from common import allocate_tiers, normalize_profile


def base_profile():
    return {
        "source_province": "浙江",
        "exam_year": 2026,
        "candidate_category": "普通类",
        "application_stage": "二段",
        "score": 610,
        "rank": 32000,
        "subjects": "物理,化学,生物",
        "gender": "女",
        "foreign_language": "英语",
        "target_region": "浙江全省",
        "only_undergraduate": False,
        "accept_associate": True,
        "accept_private": False,
        "accept_sino_foreign": True,
        "tuition_limit": 30000,
        "accepted_majors": "工科,医学,管理",
        "rejected_majors": "护理",
        "priority": "专业>城市>稳妥>学费>学校",
        "risk_preference": "平衡",
        "medical_limits": "色弱",
        "hearing_status": "正常",
        "need_volunteer_table": True,
        "volunteer_count": 80,
        "tier_strategy": "1:2:1",
    }


def test_tier_allocation_80():
    assert allocate_tiers(80) == {"冲": 20, "稳": 40, "保": 20}


def test_tier_allocation_79():
    assert allocate_tiers(79) == {"冲": 19, "稳": 41, "保": 19}


def test_tier_allocation_3():
    assert allocate_tiers(3) == {"冲": 0, "稳": 3, "保": 0}


def test_tier_allocation_1():
    assert allocate_tiers(1) == {"冲": 0, "稳": 1, "保": 0}


def test_validate_profile_rejects_bad_count():
    profile = base_profile()
    profile["volunteer_count"] = 81
    try:
        normalize_profile(profile)
    except ValueError as exc:
        assert "1-80" in str(exc)
    else:
        raise AssertionError("volunteer_count=81 should fail")
