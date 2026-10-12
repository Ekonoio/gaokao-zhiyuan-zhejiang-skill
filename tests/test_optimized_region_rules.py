from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from optimize_considered_plan import is_region_allowed
from finalize_candidate_outputs import review_reasons


def test_northeast_provinces_are_excluded():
    for province in ["辽宁", "吉林", "黑龙江"]:
        assert not is_region_allowed({"school_province": province, "city": "省会"})


def test_jiangxi_only_allows_nanchang():
    assert is_region_allowed({"school_province": "江西", "city": "南昌"})
    assert not is_region_allowed({"school_province": "江西", "city": "九江"})


def test_other_regions_remain_available():
    assert is_region_allowed({"school_province": "浙江", "city": "杭州"})
    assert is_region_allowed({"school_province": "上海", "city": "上海"})


def test_private_associate_requires_manual_confirmation():
    reasons = review_reasons(
        {
            "学历层次": "专科",
            "是否民办": "是",
            "是否中外合作": "否",
            "体检风险": "无明显体检风险",
            "学费": "18000",
            "学费是否超预算": "否",
        }
    )
    assert any("民办专科" in reason for reason in reasons)
