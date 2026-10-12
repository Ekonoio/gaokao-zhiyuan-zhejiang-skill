from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from common import assess_undergraduate_opportunity, load_profile, read_csv_rows, to_int
from official_data import SOURCE_MANIFEST_COLUMNS, parse_historical_page_texts, parse_segment_lines
from second_stage_plan import import_second_stage_plan


def target_profile():
    return load_profile(ROOT / "examples" / "target_candidate.json")


def test_missing_personalized_plan_produces_history_only_verdict():
    official_excerpt = read_csv_rows(ROOT / "tests" / "fixtures" / "official_history_2025_excerpt.csv")
    assert official_excerpt[0]["school_name"] == "上海兴伟学院"
    assert official_excerpt[0]["major_name"] == "英语"
    opportunity = assess_undergraduate_opportunity(
        target_profile(),
        [],
        historical_rows=official_excerpt,
        current_plan_verified=False,
    )
    assert opportunity["undergraduate_eligible_count"] == "待导入2026个性化二段计划"
    assert opportunity["nearest_historical_undergraduate_rank"] == 185225
    assert opportunity["nearest_historical_rank_gap"] == -34775
    assert "待个性化剩余计划确认" in opportunity["undergraduate_verdict"]


def test_original_rank_suffix_is_not_replaced_by_second_stage_queue():
    assert to_int("5-220000") == 220000
    profile = target_profile()
    assert profile["rank"] == 220000
    assert profile["remaining_queue_at_or_above"] == 12000
    assert profile["rank"] != profile["remaining_queue_at_or_above"]


def test_public_segment_line_parser_handles_spaced_official_header():
    parsed = parse_segment_lines(
        "<table><tr><td>普通类</td><td>第 一 段</td><td>第 二 段</td>"
        "<td>分数线</td><td>494</td><td>266</td></tr></table>"
    )
    assert parsed == {"first_segment_line": 494, "second_segment_line": 266}


def test_public_source_manifest_preserves_provenance_fields():
    assert "source_url" in SOURCE_MANIFEST_COLUMNS
    assert "download_date" in SOURCE_MANIFEST_COLUMNS
    assert "sha256" in SOURCE_MANIFEST_COLUMNS
    assert "parse_status" in SOURCE_MANIFEST_COLUMNS


def test_historical_parser_keeps_school_context_across_pages_without_header():
    pages = [
        (
            "普通类平行投档一、二段各专业录取情况\n"
            "院校代码、院校\n"
            "0259 浙江大学医学院（公办）\n"
            "临床医学 物理+化学 2 5 660 650 1000"
        ),
        (
            "1106\n"
            "北京第二外国语学院中瑞酒店管理学院（民办）\n"
            "金融学（国际班） 不限 2 4 520 510 160260"
        ),
        "健康服务与管理 不限 2 4 522 512 154184",
    ]
    rows = parse_historical_page_texts(pages, 2025, "https://example.test", "fixture.pdf")
    financial = next(row for row in rows if row["major_name"] == "金融学(国际班)")
    health = next(row for row in rows if row["major_name"] == "健康服务与管理")

    assert financial["school_code"] == "1106"
    assert health["school_code"] == "1106"
    assert "浙江大学医学院" not in {financial["school_name"], health["school_name"]}


def test_verified_plan_with_no_eligible_undergraduate_reports_zero():
    opportunity = assess_undergraduate_opportunity(
        target_profile(),
        [{"degree_level": "专科", "plan_count": 10, "source_access": "personalized-login-download"}],
        current_plan_verified=True,
    )
    assert opportunity["undergraduate_eligible_count"] == 0
    assert "只能从专科选择" in opportunity["undergraduate_verdict"]


def test_xlsm_import_keeps_stage_and_degree_independent():
    from openpyxl import Workbook

    temp_dir = ROOT / "outputs" / "test_xlsx_import"
    shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    source_xlsx = temp_dir / "second_stage.xlsx"
    input_path = temp_dir / "second_stage.xlsm"
    output_path = temp_dir / "admissions_plan.csv"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(
        [
            "院校代码",
            "院校名称",
            "专业代码",
            "专业名称",
            "计划数",
            "选考科目要求",
            "专业层次",
            "学制",
            "办学性质",
        ]
    )
    sheet.append(["1001", "测试本科", "01", "历史学", 2, "历史", "本科", "四年", "民办"])
    sheet.append(["1002", "测试专科", "02", "现代物流管理", 5, "不限", "专科", "三年", "公办"])
    workbook.save(source_xlsx)
    shutil.copyfile(source_xlsx, input_path)
    rows, summary = import_second_stage_plan(input_path, output_path)
    loaded = read_csv_rows(output_path)

    assert len(rows) == 2
    assert {row["application_stage"] for row in loaded} == {"二段"}
    assert {row["degree_level"] for row in loaded} == {"本科", "专科"}
    assert summary["undergraduate_program_count"] == 1
    assert summary["associate_program_count"] == 1
