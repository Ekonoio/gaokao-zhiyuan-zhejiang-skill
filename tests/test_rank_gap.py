from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from common import add_rank_gaps


def test_rank_gap_formula():
    rows = [{"2025_min_rank": "35000", "2024_min_rank": "33000", "2023_min_rank": ""}]
    result = add_rank_gaps(rows, 32000)[0]
    assert result["2025_rank_gap"] == 3000
    assert result["2024_rank_gap"] == 1000
    assert result["2023_rank_gap"] == ""
    assert result["history_year_count"] == 2


def test_missing_history_marked_insufficient():
    result = add_rank_gaps([{"2025_min_rank": "", "2024_min_rank": "", "2023_min_rank": ""}], 32000)[0]
    assert result["rank_stability"] == "数据不足"
    assert result["history_year_count"] == 0
