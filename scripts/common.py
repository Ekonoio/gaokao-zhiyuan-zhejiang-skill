from __future__ import annotations

import csv
import json
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_YEARS = [2025, 2024, 2023]

REQUIRED_INPUT_FIELDS = [
    "source_province",
    "exam_year",
    "candidate_category",
    "application_stage",
    "score",
    "rank",
    "subjects",
    "gender",
    "foreign_language",
    "target_region",
    "only_undergraduate",
    "accept_associate",
    "accept_private",
    "accept_sino_foreign",
    "tuition_limit",
    "accepted_majors",
    "rejected_majors",
    "priority",
    "risk_preference",
    "medical_limits",
    "need_volunteer_table",
    "volunteer_count",
    "tier_strategy",
]

VOLUNTEER_COLUMNS = [
    "志愿序号",
    "层级",
    "学历层次",
    "填报段次",
    "院校代码",
    "院校名称",
    "专业代码",
    "专业名称",
    "城市",
    "校区",
    "学制",
    "学费",
    "2026招生计划数",
    "2025最低分",
    "2025最低位次",
    "2024最低分",
    "2024最低位次",
    "2023最低分",
    "2023最低位次",
    "用户位次",
    "2025位次差",
    "2024位次差",
    "2023位次差",
    "近三年位次稳定性",
    "招生计划变化",
    "选科是否符合",
    "学费是否超预算",
    "是否中外合作",
    "是否民办",
    "体检风险",
    "是否需要强制复核",
    "排序理由",
    "风险提示",
    "数据来源",
    "人工复核项",
]

EXCLUDED_COLUMNS = [
    "院校代码",
    "院校名称",
    "专业代码",
    "专业名称",
    "排除原因",
    "排除类型",
    "证据来源",
    "是否可人工复核后恢复",
]

AUDIT_COLUMNS = ["风险项", "是否存在", "影响范围", "严重程度", "说明", "建议动作"]

PROCESSED_FIELD_MAP = {
    "admissions_plan.csv": [
        "year",
        "province",
        "school_province",
        "batch",
        "application_stage",
        "school_code",
        "school_name",
        "major_code",
        "major_name",
        "major_group",
        "plan_count",
        "tuition",
        "duration",
        "campus",
        "city",
        "subject_requirement",
        "foreign_language_requirement",
        "single_subject_requirement",
        "gender_requirement",
        "medical_requirement",
        "remarks",
        "is_public",
        "is_private",
        "is_sino_foreign",
        "degree_level",
        "plan_status",
        "source_access",
        "source_file",
        "source_url",
        "updated_at",
    ],
    "historical_admission.csv": [
        "year",
        "province",
        "segment",
        "school_code",
        "school_name",
        "major_code",
        "major_name",
        "subject_requirement",
        "duration",
        "degree_level",
        "plan_count",
        "min_score",
        "min_rank",
        "source_file",
        "source_url",
        "updated_at",
    ],
    "score_rank.csv": [
        "year",
        "province",
        "score",
        "count",
        "cumulative_count",
        "rank_start",
        "rank_end",
        "source_file",
        "source_url",
        "updated_at",
    ],
    "school_info.csv": [
        "school_code",
        "school_name",
        "province",
        "city",
        "school_type",
        "is_public",
        "is_private",
        "is_985",
        "is_211",
        "is_double_first_class",
        "under_department",
        "official_site",
        "admission_site",
        "source",
        "updated_at",
    ],
    "major_catalog.csv": [
        "major_code",
        "major_name",
        "discipline_category",
        "major_class",
        "duration",
        "degree",
        "is_controlled",
        "is_special",
        "source",
        "updated_at",
    ],
}

SAMPLE_TO_PROCESSED = {
    "sample_admissions_plan.csv": "admissions_plan.csv",
    "sample_historical_admission.csv": "historical_admission.csv",
    "sample_score_rank.csv": "score_rank.csv",
    "sample_school_info.csv": "school_info.csv",
    "sample_major_catalog.csv": "major_catalog.csv",
    "sample_charter_chunks.jsonl": "charter_chunks.jsonl",
}


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"缺少数据文件：{path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv_rows(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", restval="")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: stringify(row.get(key, "")) for key in fieldnames})


def stringify(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return ",".join(str(item) for item in value)
    return str(value)


def to_int(value: object, default: int | None = None) -> int | None:
    if value is None or value == "":
        return default
    text = str(value).strip()
    if re.fullmatch(r"\d+-\d+", text):
        text = text.rsplit("-", 1)[1]
    try:
        return int(float(text))
    except ValueError:
        return default


def to_float(value: object, default: float | None = None) -> float | None:
    if value is None or value == "":
        return default
    try:
        return float(str(value).strip())
    except ValueError:
        return default


def to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "yes", "y", "1", "是", "接受", "需要"}


def split_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        raw = value
    else:
        text = str(value).strip()
        if text in {"", "无", "不限", "none", "None"}:
            return []
        raw = text.replace("，", ",").replace("、", ",").replace(";", ",").split(",")
    return [str(item).strip() for item in raw if str(item).strip()]


def parse_scalar(value: str) -> object:
    text = value.strip()
    if text.lower() in {"true", "false"}:
        return text.lower() == "true"
    if text in {"是", "否"}:
        return text == "是"
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        return split_list(inner)
    if "," in text or "，" in text or "、" in text:
        return split_list(text)
    as_integer = to_int(text)
    if as_integer is not None and str(as_integer) == text:
        return as_integer
    return text


def load_key_values_from_markdown(path: Path) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"缺少输入文件：{path}")
    data: dict[str, object] = {}
    in_code_block = False
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_code_block = not in_code_block
            continue
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if not key or " " in key:
            continue
        data[key] = parse_scalar(value)
    return data


def allocate_tiers(total: int) -> dict[str, int]:
    if total < 1 or total > 80:
        raise ValueError("志愿数量必须在 1-80 之间")
    if total < 4:
        return {"冲": 0, "稳": total, "保": 0}
    base = total // 4
    return {"冲": base, "稳": 2 * base + total % 4, "保": base}


def normalize_profile(raw_profile: dict[str, object]) -> dict[str, object]:
    errors: list[str] = []
    empty_list_allowed = {
        "accepted_majors",
        "rejected_majors",
        "medical_limits",
        "transfer_bridge_majors",
    }
    for field in REQUIRED_INPUT_FIELDS:
        value = raw_profile.get(field)
        if (
            field not in raw_profile
            or value is None
            or value == ""
            or (isinstance(value, list) and not value and field not in empty_list_allowed)
        ):
            errors.append(f"缺少必填字段：{field}")

    profile = dict(raw_profile)
    profile["source_province"] = str(profile.get("source_province", "")).strip()
    profile["candidate_category"] = str(profile.get("candidate_category", "")).strip()
    stage = str(profile.get("application_stage", "")).strip().replace("普通类", "")
    profile["application_stage"] = stage
    if profile["source_province"] and profile["source_province"] != "浙江":
        errors.append("source_province 必须为 浙江")
    if profile["candidate_category"] and profile["candidate_category"] != "普通类":
        errors.append("candidate_category 必须为 普通类")
    if stage not in {"一段", "二段"}:
        errors.append("application_stage 必须为 一段 或 二段")

    numeric_fields = [
        "exam_year",
        "score",
        "rank",
        "tuition_limit",
        "volunteer_count",
        "chinese_score",
        "math_score",
        "english_score",
        "politics_score",
        "history_score",
        "geography_score",
        "second_stage_line",
        "remaining_queue_at_or_above",
    ]
    for field in numeric_fields:
        if field not in profile or profile.get(field) in {"", None}:
            continue
        value = to_int(profile.get(field))
        if value is None:
            errors.append(f"{field} 必须是数字")
        else:
            profile[field] = value

    for field in [
        "only_undergraduate",
        "accept_associate",
        "accept_private",
        "accept_sino_foreign",
        "need_volunteer_table",
        "tuition_hard_cap",
        "public_associate_priority",
    ]:
        profile[field] = to_bool(profile.get(field))

    for field in [
        "subjects",
        "accepted_majors",
        "rejected_majors",
        "transfer_bridge_majors",
        "preferred_major_families",
        "excluded_regions",
        "medical_limits",
        "medical_exclusions",
        "major_priority_tokens",
    ]:
        profile[field] = split_list(profile.get(field))
    profile["subjects"] = ["思想政治" if item == "政治" else item for item in profile["subjects"]]
    profile["hearing_status"] = str(profile.get("hearing_status", "待确认")).strip() or "待确认"
    profile["undergraduate_sprint_only"] = to_bool(profile.get("undergraduate_sprint_only", True))

    count = to_int(profile.get("volunteer_count"))
    if count is not None:
        try:
            profile["tier_counts"] = allocate_tiers(count)
        except ValueError as exc:
            errors.append(str(exc))

    if str(profile.get("tier_strategy", "")).strip() != "1:2:1":
        errors.append("第一版只支持 tier_strategy=1:2:1")

    if errors:
        raise ValueError("\n".join(errors))
    return profile


def load_profile(path: Path) -> dict[str, object]:
    if path.suffix.lower() == ".json":
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    else:
        raw = load_key_values_from_markdown(path)
    return normalize_profile(raw)


def write_json(path: Path, payload: object) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def copy_sample_to_processed(root: Path = ROOT) -> list[Path]:
    sample_dir = root / "data" / "sample"
    processed_dir = root / "data" / "processed"
    ensure_dir(processed_dir)
    copied: list[Path] = []
    for source_name, target_name in SAMPLE_TO_PROCESSED.items():
        source = sample_dir / source_name
        target = processed_dir / target_name
        if not source.exists():
            raise FileNotFoundError(f"缺少 sample 数据：{source}")
        shutil.copyfile(source, target)
        copied.append(target)
    return copied


def raw_data_status(raw_dir: Path) -> tuple[bool, str]:
    files = [item for item in raw_dir.glob("*") if item.is_file() and not item.name.startswith(".")]
    if not files:
        return False, (
            "data/raw/ 中没有可直接复制的标准数据。公开官网数据请运行 "
            "scripts/fetch_official_data.py；2026个性化二段计划须登录考试院手工下载后运行 "
            "scripts/import_second_stage_plan.py。"
        )
    return True, f"发现 {len(files)} 个顶层原始文件；请核对字段映射后再生成 processed 数据。"


def validate_processed_tables(processed_dir: Path) -> list[str]:
    errors: list[str] = []
    for filename, required_fields in PROCESSED_FIELD_MAP.items():
        path = processed_dir / filename
        if not path.exists():
            errors.append(f"缺少 processed 表：{filename}")
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, [])
        missing = [field for field in required_fields if field not in header]
        if missing:
            errors.append(f"{filename} 缺少字段：{', '.join(missing)}")
    charter_path = processed_dir / "charter_chunks.jsonl"
    if not charter_path.exists():
        errors.append("缺少 processed 表：charter_chunks.jsonl")
    return errors


def load_tier_rules(path: Path | None = None) -> dict[str, object]:
    path = path or (ROOT / "config" / "tier_rules.yaml")
    rules: dict[str, object] = {
        "safe_gap_min": 25000,
        "steady_gap_min": 10000,
        "sprint_gap_min": -5000,
        "large_plan_drop_ratio": -0.30,
        "min_complete_history_years": 2,
        "missing_history_tier": "冲",
        "forced_review_not_low_risk": True,
    }
    if not path.exists():
        return rules
    current_section = ""
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        if not raw_line.strip() or raw_line.strip().startswith("#"):
            continue
        if not raw_line.startswith(" ") and raw_line.endswith(":"):
            current_section = raw_line.strip()[:-1]
            continue
        if current_section != "tier_thresholds" or ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value.lower() in {"true", "false"}:
            rules[key] = value.lower() == "true"
        elif to_int(value) is not None and "." not in value:
            rules[key] = to_int(value)
        elif to_float(value) is not None:
            rules[key] = to_float(value)
        else:
            rules[key] = value
    return rules


def subject_matches(requirement: str, user_subjects: list[str]) -> bool:
    requirement = (requirement or "").strip()
    if requirement in {"", "不限", "不提科目要求"}:
        return True
    normalized = (
        re.sub(r"(?<!思想)政治", "思想政治", requirement)
        .replace("，", "+")
        .replace("、", "+")
        .replace("/", "+")
        .replace("&", "+")
        .replace("＆", "+")
    )
    if "或" in normalized:
        options = [item.strip() for item in normalized.split("或") if item.strip()]
        return any(option in user_subjects for option in options)
    required = [item.strip() for item in normalized.split("+") if item.strip()]
    return all(item in user_subjects for item in required)


def normalize_stage(value: object) -> str:
    return stringify(value).strip().replace("普通类", "")


def is_undergraduate_level(value: object) -> bool:
    return stringify(value).strip() in {"本科", "职业本科"}


def language_matches(requirement: str, language: str) -> bool:
    text = requirement.strip()
    if text in {"", "不限", "无"}:
        return True
    if "英语" in text and language == "英语":
        return True
    return language in text


def subject_score_status(requirement: str, profile: dict[str, object]) -> tuple[str, str]:
    text = requirement.strip()
    if text in {"", "不限", "无"}:
        return "match", ""
    score_fields = {
        "语文": "chinese_score",
        "数学": "math_score",
        "英语": "english_score",
        "外语": "english_score",
        "思想政治": "politics_score",
        "政治": "politics_score",
        "历史": "history_score",
        "地理": "geography_score",
    }
    parsed = False
    for subject, field in score_fields.items():
        pattern = rf"{subject}.*?(?:>=|≥|不低于|达到)\s*(\d+)"
        match = re.search(pattern, text)
        if not match:
            continue
        parsed = True
        actual = to_int(profile.get(field))
        if actual is None:
            return "review", f"缺少{subject}单科成绩"
        if actual < int(match.group(1)):
            return "mismatch", f"{subject}单科成绩不符合"
    return ("match", "") if parsed else ("review", "单科要求无法自动解析")


def gender_matches(requirement: str, gender: str) -> bool:
    text = requirement.strip()
    if text in {"", "不限", "无"}:
        return True
    if any(marker in text for marker in ["只招男", "限男", "仅男"]):
        return gender == "男"
    if any(marker in text for marker in ["只招女", "限女", "仅女"]):
        return gender == "女"
    return True


def row_bool(row: dict[str, object], key: str) -> bool:
    return to_bool(row.get(key, ""))


def boolean_label(row: dict[str, object], key: str) -> str:
    value = stringify(row.get(key, "")).strip()
    if not value:
        return "待确认"
    return "是" if to_bool(value) else "否"


def exclusion_row(row: dict[str, object], reason: str, exclusion_type: str, recoverable: str = "否") -> dict[str, str]:
    return {
        "院校代码": stringify(row.get("school_code", "")),
        "院校名称": stringify(row.get("school_name", "")),
        "专业代码": stringify(row.get("major_code", "")),
        "专业名称": stringify(row.get("major_name", "")),
        "排除原因": reason,
        "排除类型": exclusion_type,
        "证据来源": stringify(row.get("source_file", "结构化数据")),
        "是否可人工复核后恢复": recoverable,
    }


def apply_hard_filter(row: dict[str, object], profile: dict[str, object]) -> tuple[dict[str, object] | None, dict[str, str] | None]:
    reasons: list[tuple[str, str, str]] = []
    user_subjects = profile.get("subjects", [])
    if not isinstance(user_subjects, list):
        user_subjects = split_list(user_subjects)

    if not subject_matches(stringify(row.get("subject_requirement", "")), user_subjects):
        reasons.append(("选科不符合", "硬性排除", "否"))

    row_stage = normalize_stage(row.get("application_stage", row.get("batch", "")))
    candidate_stage = normalize_stage(profile.get("application_stage", ""))
    if row_stage and row_stage != candidate_stage:
        reasons.append((f"填报段次不符合：考生{candidate_stage}、计划{row_stage}", "硬性排除", "否"))

    degree_level = stringify(row.get("degree_level", ""))
    if degree_level == "专科" and (profile.get("only_undergraduate") or not profile.get("accept_associate")):
        reasons.append(("用户不接受专科", "用户限制排除", "否"))
    if degree_level not in {"本科", "职业本科", "专科"}:
        reasons.append(("学历层次未明确，不能生成真实志愿", "数据质量排除", "是"))

    if row_bool(row, "is_private") and not profile.get("accept_private"):
        reasons.append(("用户不接受民办", "用户限制排除", "否"))

    if row_bool(row, "is_sino_foreign") and not profile.get("accept_sino_foreign"):
        reasons.append(("用户不接受中外合作", "用户限制排除", "否"))

    target_region = stringify(profile.get("target_region", "浙江全省"))
    city = stringify(row.get("city", ""))
    school_province = stringify(row.get("school_province", ""))
    excluded_regions = profile.get("excluded_regions", [])
    if any(
        region
        and (
            region in school_province
            or region in city
            or region in stringify(row.get("school_name", ""))
        )
        for region in excluded_regions
    ):
        reasons.append(("院校位于明确排除地区", "用户限制排除", "否"))
    if target_region not in {"浙江全省", "全省", "全国", "不限"}:
        if target_region in {"杭州", "宁波", "温州"} and city != target_region:
            reasons.append((f"城市不在目标区域：{target_region}", "用户限制排除", "否"))
        elif target_region == "其他" and city in {"杭州", "宁波", "温州"}:
            reasons.append(("城市不在目标区域：其他", "用户限制排除", "否"))

    major_text = stringify(row.get("major_name", "")) + " " + stringify(row.get("major_group", ""))
    rejected = profile.get("rejected_majors", [])
    if any(item and item in major_text for item in rejected):
        reasons.append(("专业命中不接受专业", "用户限制排除", "否"))

    accepted = profile.get("accepted_majors", [])
    if accepted and not any(item in major_text for item in accepted):
        reasons.append(("专业不在可接受专业范围", "用户限制排除", "是"))

    tuition = to_int(row.get("tuition"), 0) or 0
    tuition_limit = to_int(profile.get("tuition_limit"), 0) or 0
    tuition_over = tuition_limit > 0 and tuition > tuition_limit
    if tuition_limit > 0 and profile.get("tuition_hard_cap") and tuition <= 0:
        reasons.append(("学费缺失，无法验证每年费用硬上限", "数据质量排除", "是"))
    if tuition_over and profile.get("tuition_hard_cap"):
        reasons.append((f"学费超过每年{tuition_limit}元硬上限", "用户限制排除", "否"))

    remarks = stringify(row.get("remarks", ""))
    language_requirement = stringify(row.get("foreign_language_requirement", ""))
    if not language_requirement and "只招英语" in remarks:
        language_requirement = "英语"
    if not language_matches(language_requirement, stringify(profile.get("foreign_language", ""))):
        reasons.append(("外语语种不符合", "硬性排除", "否"))

    single_status, single_note = subject_score_status(stringify(row.get("single_subject_requirement", "")), profile)
    if single_status == "mismatch":
        reasons.append((single_note, "硬性排除", "否"))

    if not gender_matches(stringify(row.get("gender_requirement", "")), stringify(profile.get("gender", ""))):
        reasons.append(("性别要求不符合", "硬性排除", "否"))

    medical_text = f"{row.get('medical_requirement', '')} {remarks}"
    medical_exclusions = profile.get("medical_exclusions", [])
    if any(
        item
        and item in medical_text
        and any(marker in medical_text for marker in ["不招", "不宜", "限制", "不予录取"])
        for item in medical_exclusions
    ):
        reasons.append(("明确体检限制不符合", "硬性排除", "否"))

    if reasons:
        reason_text = "；".join(reason for reason, _, _ in reasons)
        exclusion_type = "；".join(sorted({item[1] for item in reasons}))
        recoverable = "是" if any(item[2] == "是" for item in reasons) else "否"
        return None, exclusion_row(row, reason_text, exclusion_type, recoverable)

    enriched = dict(row)
    transfer_bridge_majors = profile.get("transfer_bridge_majors", [])
    is_transfer_bridge = any(item and item in major_text for item in transfer_bridge_majors)
    medical_limits = profile.get("medical_limits", [])
    medical_conflict = any(item and item in medical_text for item in medical_limits)
    hearing_status = stringify(profile.get("hearing_status", "待确认"))
    hearing_pending = not hearing_status or any(
        marker in hearing_status for marker in ["待确认", "未知", "不清楚"]
    )
    needs_rule_review = single_status == "review"

    enriched["subject_match"] = "是"
    enriched["tuition_over_budget"] = "是" if tuition_over else "否"
    enriched["transfer_bridge"] = "是" if is_transfer_bridge else "否"
    if hearing_pending:
        enriched["medical_risk"] = "听力情况待确认"
    else:
        enriched["medical_risk"] = "体检限制需复核" if medical_conflict else "无明显体检风险"
    enriched["force_review"] = (
        "是"
        if (medical_conflict or hearing_pending or needs_rule_review or is_transfer_bridge)
        else "否"
    )
    enriched["candidate_notes"] = []
    if tuition_over:
        enriched["candidate_notes"].append("学费超预算，保留但进入风险审计")
    if medical_conflict:
        enriched["candidate_notes"].append("体检限制命中，强制人工复核")
    if hearing_pending:
        enriched["candidate_notes"].append("听力情况待确认，所有志愿填报前均须核对章程")
    if needs_rule_review:
        enriched["candidate_notes"].append(single_note)
    if is_transfer_bridge:
        enriched["candidate_notes"].append(
            "仅作为转专业跳板；必须核验转专业资格、名额、成绩门槛和失败后的就读接受度"
        )
    return enriched, None


def generate_candidate_pool_rows(
    profile: dict[str, object], merged_rows: list[dict[str, object]]
) -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    candidates: list[dict[str, object]] = []
    excluded: list[dict[str, str]] = []
    for row in merged_rows:
        included, excluded_row = apply_hard_filter(row, profile)
        if included is not None:
            candidates.append(included)
        elif excluded_row is not None:
            excluded.append(excluded_row)
    return candidates, excluded


def normalize_major_name(value: object) -> str:
    text = stringify(value)
    text = re.sub(r"\s+", "", text)
    return text.replace("（", "(").replace("）", ")")


def merge_plan_history_rows(plan_rows: list[dict[str, str]], history_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    history_by_key: dict[tuple[str, str], dict[int, dict[str, str]]] = defaultdict(dict)
    history_by_name: dict[tuple[str, str], dict[int, dict[str, str]]] = defaultdict(dict)
    for history in history_rows:
        year = to_int(history.get("year"))
        if year in HISTORICAL_YEARS:
            history_by_key[(history.get("school_code", ""), history.get("major_code", ""))][year] = history
            history_by_name[
                (history.get("school_code", ""), normalize_major_name(history.get("major_name", "")))
            ][year] = history

    rules = load_tier_rules()
    large_drop_ratio = float(rules["large_plan_drop_ratio"])
    merged: list[dict[str, object]] = []
    for plan in plan_rows:
        row: dict[str, object] = dict(plan)
        key = (plan.get("school_code", ""), plan.get("major_code", ""))
        history_for_key = history_by_key.get(key, {})
        row["history_match_method"] = "school_code+major_code"
        if not history_for_key:
            name_key = (plan.get("school_code", ""), normalize_major_name(plan.get("major_name", "")))
            history_for_key = history_by_name.get(name_key, {})
            row["history_match_method"] = "school_code+major_name" if history_for_key else "unmatched"
        for year in HISTORICAL_YEARS:
            history = history_for_key.get(year, {})
            row[f"{year}_min_score"] = history.get("min_score", "")
            row[f"{year}_min_rank"] = history.get("min_rank", "")
            row[f"{year}_plan_count"] = history.get("plan_count", "")
        current_plan = to_int(plan.get("plan_count"), 0) or 0
        previous_plan = to_int(row.get("2025_plan_count"), 0) or 0
        if stringify(plan.get("source_access")) == "personalized-login-download":
            row["plan_change"] = "二段剩余计划，不与往年完整计划数比较"
        elif not history_for_key:
            row["plan_change"] = "新增专业或历史数据不足"
        elif previous_plan == 0:
            row["plan_change"] = "缺少2025计划数，需人工复核"
        else:
            ratio = (current_plan - previous_plan) / previous_plan
            if ratio <= large_drop_ratio:
                row["plan_change"] = "大幅缩招"
            elif ratio < 0:
                row["plan_change"] = "缩招"
            elif ratio > 0:
                row["plan_change"] = "扩招"
            else:
                row["plan_change"] = "计划稳定"
        merged.append(row)
    return merged


def enrich_plan_with_school_info(
    plan_rows: list[dict[str, str]], school_rows: list[dict[str, str]]
) -> list[dict[str, str]]:
    by_name = {
        stringify(row.get("school_name")).strip(): row
        for row in school_rows
        if stringify(row.get("school_name")).strip()
    }
    enriched: list[dict[str, str]] = []
    for source_row in plan_rows:
        row = dict(source_row)
        school = by_name.get(stringify(row.get("school_name")).strip())
        if school:
            row["school_province"] = (
                stringify(row.get("school_province")).strip()
                or stringify(school.get("province")).strip()
            )
            row["city"] = (
                stringify(row.get("city")).strip()
                or stringify(school.get("city")).strip()
            )
            row["is_public"] = stringify(school.get("is_public")).strip()
            row["is_private"] = stringify(school.get("is_private")).strip()
        enriched.append(row)
    return enriched


def merge_plan_history(processed_dir: Path, output_path: Path) -> list[dict[str, object]]:
    plan_rows = read_csv_rows(processed_dir / "admissions_plan.csv")
    history_rows = read_csv_rows(processed_dir / "historical_admission.csv")
    merged = merge_plan_history_rows(plan_rows, history_rows)
    fieldnames = list(plan_rows[0].keys()) if plan_rows else []
    for year in HISTORICAL_YEARS:
        fieldnames.extend([f"{year}_min_score", f"{year}_min_rank", f"{year}_plan_count"])
    fieldnames.extend(["plan_change", "history_match_method"])
    write_csv_rows(output_path, merged, fieldnames)
    return merged


def add_rank_gaps(rows: list[dict[str, object]], user_rank: int) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for row in rows:
        enriched = dict(row)
        gaps: list[int] = []
        for year in HISTORICAL_YEARS:
            rank = to_int(row.get(f"{year}_min_rank"))
            if rank is None:
                enriched[f"{year}_rank_gap"] = ""
            else:
                gap = rank - user_rank
                enriched[f"{year}_rank_gap"] = gap
                gaps.append(gap)
        enriched["history_year_count"] = len(gaps)
        if len(gaps) < 2:
            enriched["rank_stability"] = "数据不足"
        elif max(gaps) - min(gaps) <= 5000:
            enriched["rank_stability"] = "相对稳定"
        else:
            enriched["rank_stability"] = "波动较大"
        output.append(enriched)
    return output


def classify_row(
    row: dict[str, object],
    rules: dict[str, object] | None = None,
    profile: dict[str, object] | None = None,
) -> tuple[str, str, str, str]:
    rules = rules or load_tier_rules()
    history_count = to_int(row.get("history_year_count"), 0) or 0
    min_history = int(rules["min_complete_history_years"])
    review_items: list[str] = []
    risk_notes: list[str] = []
    transfer_bridge = stringify(row.get("transfer_bridge", "")) == "是"

    if history_count < min_history:
        review_items.append("历史数据不足")
        risk_notes.append("新增专业或历史数据不足，不自动归入保")
        layer = stringify(rules["missing_history_tier"])
        if (
            profile
            and normalize_stage(profile.get("application_stage")) == "二段"
            and profile.get("undergraduate_sprint_only", True)
            and is_undergraduate_level(row.get("degree_level"))
        ):
            layer = "冲"
            risk_notes.append("二段本科仅作低概率冲刺")
        reason = "历史数据不足，按保守规则处理"
        if transfer_bridge:
            layer = "冲"
            reason += "；电子商务仅作转专业跳板"
            risk_notes.append("转专业申请存在失败风险，不能承担稳保功能")
            review_items.append("逐校核验转专业政策")
        return layer, reason, "；".join(risk_notes), "；".join(review_items)

    gaps = [to_int(row.get(f"{year}_rank_gap")) for year in HISTORICAL_YEARS]
    valid_gaps = [gap for gap in gaps if gap is not None]
    positive_count = sum(1 for gap in valid_gaps if gap >= 0)
    safe_count = sum(1 for gap in valid_gaps if gap >= int(rules["safe_gap_min"]))
    steady_count = sum(1 for gap in valid_gaps if gap >= int(rules["steady_gap_min"]))
    sprint_floor = int(rules["sprint_gap_min"])
    latest_gap = to_int(row.get("2025_rank_gap"))

    if positive_count < 2 or min(valid_gaps) < sprint_floor:
        layer = "冲"
        reason = "多数年份位次差偏负或存在明显冲刺年份"
    elif safe_count >= 2 and latest_gap is not None and latest_gap >= int(rules["steady_gap_min"]):
        layer = "保"
        reason = "多数年份位次差明显为正，且最近一年仍有安全余量"
    elif steady_count >= 2 and latest_gap is not None and latest_gap >= sprint_floor:
        layer = "稳"
        reason = "多数年份位次差为正且最近一年未明显跌破边界"
    else:
        layer = "冲"
        reason = "位次差接近边界，按冲刺处理"

    if "大幅缩招" in stringify(row.get("plan_change", "")):
        risk_notes.append("招生计划大幅缩减")
        review_items.append("计划变化")
        if layer == "保":
            layer = "稳"
            reason += "；因大幅缩招从保下调为稳"

    if stringify(row.get("force_review", "")) == "是":
        risk_notes.append("存在强制复核项")
        if not transfer_bridge:
            review_items.append("章程限制复核")
        if layer == "保" and rules.get("forced_review_not_low_risk", True):
            layer = "稳"
            reason += "；因强制复核从保下调为稳"

    if stringify(row.get("tuition_over_budget", "")) == "是":
        risk_notes.append("学费超预算")
        review_items.append("学费")

    if (
        profile
        and normalize_stage(profile.get("application_stage")) == "二段"
        and profile.get("undergraduate_sprint_only", True)
        and is_undergraduate_level(row.get("degree_level"))
    ):
        layer = "冲"
        reason = f"{reason}；二段本科按考生专用规则仅列为冲刺"
        risk_notes.append("本科录取概率低，专科需承担稳保")

    if transfer_bridge:
        layer = "冲"
        reason = f"{reason}；电子商务仅作转专业跳板"
        risk_notes.append("转专业申请存在失败风险，不能承担稳保功能")
        review_items.append("逐校核验转专业政策")

    return layer, reason, "；".join(risk_notes) or "无明显额外风险", "；".join(review_items)


def volunteer_row_from_candidate(row: dict[str, object], sequence: int, profile: dict[str, object], layer: str, reason: str, risk: str, review: str) -> dict[str, object]:
    source = stringify(row.get("source_file", ""))
    if stringify(row.get("source_url", "")):
        source = f"{source} {row.get('source_url')}".strip()
    return {
        "志愿序号": sequence,
        "层级": layer,
        "学历层次": row.get("degree_level", ""),
        "填报段次": normalize_stage(row.get("application_stage", row.get("batch", ""))),
        "院校代码": row.get("school_code", ""),
        "院校名称": row.get("school_name", ""),
        "专业代码": row.get("major_code", ""),
        "专业名称": row.get("major_name", ""),
        "城市": row.get("city", ""),
        "校区": row.get("campus", ""),
        "学制": row.get("duration", ""),
        "学费": row.get("tuition", ""),
        "2026招生计划数": row.get("plan_count", ""),
        "2025最低分": row.get("2025_min_score", ""),
        "2025最低位次": row.get("2025_min_rank", ""),
        "2024最低分": row.get("2024_min_score", ""),
        "2024最低位次": row.get("2024_min_rank", ""),
        "2023最低分": row.get("2023_min_score", ""),
        "2023最低位次": row.get("2023_min_rank", ""),
        "用户位次": profile.get("rank", ""),
        "2025位次差": row.get("2025_rank_gap", ""),
        "2024位次差": row.get("2024_rank_gap", ""),
        "2023位次差": row.get("2023_rank_gap", ""),
        "近三年位次稳定性": row.get("rank_stability", ""),
        "招生计划变化": row.get("plan_change", ""),
        "选科是否符合": row.get("subject_match", "是"),
        "学费是否超预算": row.get("tuition_over_budget", "否"),
        "是否中外合作": boolean_label(row, "is_sino_foreign"),
        "是否民办": boolean_label(row, "is_private"),
        "体检风险": row.get("medical_risk", "无明显体检风险"),
        "是否需要强制复核": "是" if (row.get("force_review") == "是" or review) else "否",
        "排序理由": reason,
        "风险提示": risk,
        "数据来源": source,
        "人工复核项": review,
    }


def rank_sort_value(row: dict[str, object]) -> int:
    gap = to_int(row.get("2025_rank_gap"))
    if gap is None:
        return -10**9
    return gap


def region_priority(row: dict[str, object], profile: dict[str, object]) -> int:
    groups = profile.get("region_priority_groups", [])
    if not isinstance(groups, list):
        return 99
    location = {
        stringify(row.get("school_province")).strip(),
        stringify(row.get("city")).strip(),
    }
    for index, group in enumerate(groups):
        values = group if isinstance(group, list) else [group]
        if any(stringify(value).strip() in location for value in values):
            return index
    return len(groups)


def major_priority(row: dict[str, object], profile: dict[str, object]) -> int:
    tokens = profile.get("major_priority_tokens", [])
    if not isinstance(tokens, list):
        return 99
    major_name = stringify(row.get("major_name"))
    for index, token in enumerate(tokens):
        if stringify(token) and stringify(token) in major_name:
            return index
    return len(tokens)


def school_nature_priority(row: dict[str, object], profile: dict[str, object]) -> int:
    if not profile.get("public_associate_priority", False):
        return 0
    if stringify(row.get("is_public")) == "是":
        return 0
    if stringify(row.get("is_private")) == "是":
        return 1
    return 2


def candidate_sort_key(
    row: dict[str, object], profile: dict[str, object]
) -> tuple[int, int, int, int, int, int]:
    bridge_order = 1 if stringify(row.get("transfer_bridge", "")) == "是" else 0
    history_missing = 1 if (to_int(row.get("history_year_count"), 0) or 0) < 2 else 0
    return (
        bridge_order,
        school_nature_priority(row, profile),
        region_priority(row, profile),
        major_priority(row, profile),
        history_missing,
        rank_sort_value(row),
    )


def classify_and_select_volunteers(
    rows: list[dict[str, object]], profile: dict[str, object], rules: dict[str, object] | None = None
) -> list[dict[str, object]]:
    if not profile.get("need_volunteer_table", True):
        return []
    target_count = int(profile["volunteer_count"])
    targets = allocate_tiers(target_count)
    rules = rules or load_tier_rules()
    grouped: dict[str, list[tuple[dict[str, object], str, str, str]]] = {"冲": [], "稳": [], "保": []}
    undergraduate: list[tuple[dict[str, object], str, str, str]] = []
    for row in rows:
        layer, reason, risk, review = classify_row(row, rules, profile)
        item = (row, reason, risk, review)
        if is_undergraduate_level(row.get("degree_level")):
            undergraduate.append(item)
        else:
            grouped.setdefault(layer, []).append(item)
    for layer in grouped:
        grouped[layer].sort(key=lambda item: candidate_sort_key(item[0], profile))
    undergraduate.sort(key=lambda item: candidate_sort_key(item[0], profile))

    selected: list[tuple[dict[str, object], str, str, str, str]] = []
    used: set[tuple[str, str]] = set()
    for row, reason, risk, review in undergraduate[:target_count]:
        key = (stringify(row.get("school_code")), stringify(row.get("major_code")))
        used.add(key)
        selected.append((row, "冲", reason, risk, review))

    adjusted_targets = dict(targets)
    adjusted_targets["冲"] = max(0, adjusted_targets["冲"] - len(selected))
    public_associate_priority = bool(profile.get("public_associate_priority"))
    for layer in ["冲", "稳", "保"]:
        quota = min(max(0, target_count - len(selected)), adjusted_targets.get(layer, 0))
        available = grouped.get(layer, [])
        if public_associate_priority:
            available = [
                item for item in available if stringify(item[0].get("is_public")) == "是"
            ]
        for item in available[:quota]:
            row, reason, risk, review = item
            key = (stringify(row.get("school_code")), stringify(row.get("major_code")))
            used.add(key)
            selected.append((row, layer, reason, risk, review))

    if len(selected) < target_count:
        fill_passes = [True, False] if public_associate_priority else [False]
        for public_only in fill_passes:
            for layer in ["稳", "保", "冲"]:
                for row, reason, risk, review in grouped.get(layer, []):
                    if public_only and stringify(row.get("is_public")) != "是":
                        continue
                    key = (stringify(row.get("school_code")), stringify(row.get("major_code")))
                    if key in used:
                        continue
                    used.add(key)
                    selected.append((row, layer, reason, risk, review))
                    if len(selected) >= target_count:
                        break
                if len(selected) >= target_count:
                    break
            if len(selected) >= target_count:
                break

    undergraduate_rows = [item for item in selected if is_undergraduate_level(item[0].get("degree_level"))]
    associate_rows = [item for item in selected if not is_undergraduate_level(item[0].get("degree_level"))]
    associate_rows.sort(
        key=lambda item: (
            {"冲": 0, "稳": 1, "保": 2}.get(item[1], 3),
            *candidate_sort_key(item[0], profile),
        )
    )
    ordered = undergraduate_rows + associate_rows
    return [
        volunteer_row_from_candidate(row, index + 1, profile, layer, reason, risk, review)
        for index, (row, layer, reason, risk, review) in enumerate(ordered[:target_count])
    ]


def count_by_column(rows: list[dict[str, object]], column: str) -> Counter:
    return Counter(stringify(row.get(column, "")) for row in rows)


def assess_undergraduate_opportunity(
    profile: dict[str, object],
    current_rows: list[dict[str, object]],
    historical_rows: list[dict[str, object]] | None = None,
    current_plan_verified: bool | None = None,
) -> dict[str, object]:
    if current_plan_verified is None:
        current_plan_verified = to_bool(profile.get("current_plan_verified", False)) or any(
            stringify(row.get("source_access", "")) in {"personalized-login-download", "sample/mock"}
            for row in current_rows
        )

    undergraduate_rows = [row for row in current_rows if is_undergraduate_level(row.get("degree_level"))]
    current_plan_count = sum(to_int(row.get("plan_count"), 0) or 0 for row in current_rows)
    nearest_candidates = [
        to_int(row.get("2025_min_rank"))
        for row in undergraduate_rows
        if to_int(row.get("2025_min_rank")) is not None
    ]

    if historical_rows and not current_plan_verified:
        user_subjects = profile.get("subjects", [])
        if not isinstance(user_subjects, list):
            user_subjects = split_list(user_subjects)
        for row in historical_rows:
            if to_int(row.get("year")) != 2025:
                continue
            if not is_undergraduate_level(row.get("degree_level")):
                continue
            if not subject_matches(stringify(row.get("subject_requirement", "")), user_subjects):
                continue
            rank = to_int(row.get("min_rank"))
            if rank is not None:
                nearest_candidates.append(rank)

    nearest_rank = max(nearest_candidates) if nearest_candidates else None
    user_rank = to_int(profile.get("rank"))
    nearest_gap = nearest_rank - user_rank if nearest_rank is not None and user_rank is not None else None

    if not current_plan_verified:
        eligible_count: object = "待导入2026个性化二段计划"
        plan_count: object = "待确认"
        verdict = "制度上可报本科；实际机会待个性化剩余计划确认"
    elif not undergraduate_rows:
        eligible_count = 0
        plan_count = current_plan_count
        verdict = "当前个性化计划中没有通过硬过滤的本科，具体志愿只能从专科选择"
    else:
        eligible_count = len(undergraduate_rows)
        plan_count = current_plan_count
        if nearest_gap is None or nearest_gap < 0:
            verdict = "本科仅作低概率冲刺，专科承担主要稳保"
        else:
            verdict = "存在本科冲刺项，仍须以专科构成稳保"

    return {
        "undergraduate_eligibility": "是，二段可填报剩余本科计划",
        "current_plan_verified": current_plan_verified,
        "undergraduate_eligible_count": eligible_count,
        "nearest_historical_undergraduate_rank": nearest_rank if nearest_rank is not None else "数据不足",
        "nearest_historical_rank_gap": nearest_gap if nearest_gap is not None else "数据不足",
        "current_plan_count": plan_count,
        "undergraduate_verdict": verdict,
    }


def audit_rows(
    volunteer_rows: list[dict[str, object]],
    excluded_rows: list[dict[str, object]],
    profile: dict[str, object],
) -> list[dict[str, str]]:
    target = int(profile.get("volunteer_count", 80))
    desired = allocate_tiers(target)
    actual = count_by_column(volunteer_rows, "层级")

    def row(item: str, exists: bool, scope: str, severity: str, desc: str, action: str) -> dict[str, str]:
        return {
            "风险项": item,
            "是否存在": "是" if exists else "否",
            "影响范围": scope,
            "严重程度": severity,
            "说明": desc,
            "建议动作": action,
        }

    excluded_reason = "；".join(stringify(item.get("排除原因", "")) for item in excluded_rows)
    rows = [
        row("用户不需要志愿排序表", not profile.get("need_volunteer_table", True), "输出", "中", "用户设置 need_volunteer_table=false", "确认是否只需要候选池和审计表"),
        row(
            "缺少2026个性化二段计划",
            not to_bool(profile.get("current_plan_verified", False)),
            "当前计划",
            "高",
            "没有经登录下载并导入的考生个性化剩余计划，只能做历史判断",
            "登录浙江省教育考试院下载XLSM/XLSX后运行 scripts/import_second_stage_plan.py",
        ),
        row(
            "听力状态待确认",
            stringify(profile.get("hearing_status", "待确认")) in {"", "待确认", "未知", "不明确"},
            "全部候选",
            "高",
            "听力情况不明确，无法完成相关专业限制核验",
            "人工确认听力、听力残疾和体检结论",
        ),
        row("志愿数量不是80", target != 80, "输出", "低", f"本次目标数量为 {target}", "报告中说明用户可设置 1-80"),
        row("志愿数量小于4", target < 4, "分层", "低", "小于4时全部归入稳", "按规则执行并说明"),
        row("志愿数量不是4的倍数", target % 4 != 0, "分层", "低", "余数全部归入稳", "按规则执行并说明"),
        row("候选志愿不足用户要求数量", len(volunteer_rows) < target, "候选池", "高", f"生成 {len(volunteer_rows)} 个，目标 {target} 个", "补充官方数据或放宽用户限制"),
        row("选科不符合", "选科不符合" in excluded_reason, "排除清单", "高", "排除清单包含选科不符合项", "不得进入志愿表"),
        row("是否存在学费超预算", any(item.get("学费是否超预算") == "是" for item in volunteer_rows), "志愿表", "中", "存在学费超预算但未直接排除", "人工确认家庭预算"),
        row("是否存在体检明显冲突", any(stringify(item.get("体检风险", "")) not in {"", "无明显体检风险"} for item in volunteer_rows), "志愿表", "高", "存在体检强制复核项", "核对体检指导意见和招生章程"),
        row("历史数据缺失", any("历史数据不足" in stringify(item.get("人工复核项", "")) for item in volunteer_rows), "志愿表", "中", "存在历史数据不足项", "不得自动归入保"),
        row("新增专业没有历史位次", any("新增" in stringify(item.get("招生计划变化", "")) for item in volunteer_rows), "志愿表", "中", "存在新增专业或历史不足", "人工复核计划和同类数据"),
        row("专业代码匹配失败", "专业代码" in excluded_reason, "数据质量", "中", "样例流程未检测到专业代码失败", "真实数据接入时核对代码"),
        row("学校代码变化", "学校代码" in excluded_reason, "数据质量", "中", "样例流程未检测到学校代码变化", "真实数据接入时核对代码变更"),
        row("同名专业但校区不同", False, "数据质量", "低", "样例数据未出现同名专业多校区冲突", "真实数据接入时按校区复核"),
        row("中外合作名称相似但费用不同", any(item.get("是否中外合作") == "是" and item.get("学费是否超预算") == "是" for item in volunteer_rows), "志愿表", "中", "中外合作需特别核对费用", "核对招生章程和学费"),
        row("民办/公办属性缺失", any(stringify(item.get("是否民办", "")) == "" for item in volunteer_rows), "数据质量", "中", "志愿表应包含民办字段", "补齐学校属性"),
        row("招生计划大幅缩减", any("大幅缩招" in stringify(item.get("招生计划变化", "")) for item in volunteer_rows), "志愿表", "高", "大幅缩招会提高风险", "人工复核计划变化"),
        row("用户不接受民办但候选池主要是民办", (not profile.get("accept_private") and "用户不接受民办" in excluded_reason and len(volunteer_rows) < target), "候选池", "中", "民办限制可能导致候选不足", "确认是否放宽民办限制"),
        row("用户不接受专科但分数位次只适合专科", (not profile.get("accept_associate") and "用户不接受专科" in excluded_reason and len(volunteer_rows) < target), "候选池", "中", "专科限制可能导致候选不足", "确认本科/专科边界"),
        row("用户接受专科，需要纳入专科志愿", bool(profile.get("accept_associate") and any(item.get("学历层次") == "专科" for item in volunteer_rows)), "候选池", "低", "二段方案需要专科承担稳保", "核对专科志愿数量"),
        row("二段本科被错误标为稳或保", any(item.get("学历层次") in {"本科", "职业本科"} and item.get("层级") != "冲" for item in volunteer_rows), "分层", "高", "该考生的二段本科只能列为冲刺", "修正本科分层"),
        row("专科稳保不足", not any(item.get("学历层次") == "专科" and item.get("层级") in {"稳", "保"} for item in volunteer_rows), "分层", "高", "本科不能承担保底功能", "补充专科稳保志愿"),
        row("输出不足80个时必须解释原因", len(volunteer_rows) < 80, "报告", "中", "最终报告需要说明不足原因", "在 final_report.md 中说明候选池不足或限制过严"),
        row("冲刺志愿是否过多", actual["冲"] > desired["冲"], "分层", "中", f"冲：实际 {actual['冲']}，目标 {desired['冲']}", "检查是否因候选不足补位"),
        row("稳妥志愿是否不足", actual["稳"] < desired["稳"], "分层", "中", f"稳：实际 {actual['稳']}，目标 {desired['稳']}", "补充候选或调整限制"),
        row("保底志愿是否不足", actual["保"] < desired["保"], "分层", "高", f"保：实际 {actual['保']}，目标 {desired['保']}", "补充可靠保底候选"),
        row("是否集中在同一城市", max(count_by_column(volunteer_rows, "城市").values() or [0]) > max(3, len(volunteer_rows) * 0.6), "地域", "低", "城市集中度偏高", "核对目标区域是否过窄"),
        row("是否集中在同一学校", max(count_by_column(volunteer_rows, "院校名称").values() or [0]) > 2, "学校", "低", "同一学校集中度偏高", "增加学校分散度"),
        row("是否集中在同一专业类", False, "专业", "低", "当前输出未含专业类聚合字段", "真实数据接入时补充 major_group 审计"),
        row("是否存在选科不符", any(item.get("选科是否符合") != "是" for item in volunteer_rows), "志愿表", "高", "志愿表不应包含选科不符项", "修正硬性过滤"),
        row("是否存在校区不明确", any(not stringify(item.get("校区", "")) for item in volunteer_rows), "数据质量", "中", "校区缺失需复核", "补齐校区"),
        row("是否存在专业代码无法匹配", any(not stringify(item.get("专业代码", "")) for item in volunteer_rows), "数据质量", "高", "专业代码缺失需复核", "核对官方计划"),
        row("是否存在章程未复核", True, "章程", "中", "sample 流程只提供关键词检索，不替代人工复核", "填报前逐校核对招生章程"),
    ]
    return rows


def search_charter_chunks(
    path: Path,
    school_code: str = "",
    school_name: str = "",
    risk_type: str = "",
    keyword: str = "",
) -> list[dict[str, object]]:
    if not path.exists():
        return [
            {
                "chunk_text": "章程数据缺失，需人工复核",
                "school_code": school_code,
                "school_name": school_name,
                "risk_type": risk_type,
            }
        ]
    results: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if school_code and item.get("school_code") != school_code:
            continue
        if school_name and school_name not in stringify(item.get("school_name", "")):
            continue
        if risk_type and item.get("risk_type") != risk_type:
            continue
        if keyword and keyword not in stringify(item.get("chunk_text", "")):
            continue
        results.append(item)
    if not results:
        results.append(
            {
                "chunk_text": "未检索到匹配章程片段，需人工复核",
                "school_code": school_code,
                "school_name": school_name,
                "risk_type": risk_type,
            }
        )
    return results


def write_xlsx(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    ensure_dir(path.parent)
    try:
        from openpyxl import Workbook
    except ImportError as exc:
        raise RuntimeError("缺少 openpyxl，无法导出 Excel") from exc
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "volunteer_table"
    sheet.append(fieldnames)
    for row in rows:
        sheet.append([row.get(field, "") for field in fieldnames])
    workbook.save(path)


def build_report(
    profile: dict[str, object],
    volunteers: list[dict[str, object]],
    excluded: list[dict[str, object]],
    audit: list[dict[str, object]],
    opportunity: dict[str, object] | None = None,
) -> str:
    target = int(profile.get("volunteer_count", 80))
    counts = count_by_column(volunteers, "层级")
    degree_counts = count_by_column(volunteers, "学历层次")
    opportunity = opportunity or assess_undergraduate_opportunity(profile, volunteers)
    reached = len(volunteers) >= target
    if not profile.get("need_volunteer_table", True):
        shortage_reason = "用户未要求志愿排序表"
    elif reached:
        shortage_reason = "已达到用户要求数量"
    elif not opportunity["current_plan_verified"]:
        shortage_reason = "缺少登录后下载的2026个性化二段剩余计划；仅生成历史判断，不生成今年院校专业名单"
    else:
        shortage_reason = "候选池不足或硬性限制较多，未达到用户要求数量"
    risk_lines = [f"- {row['风险项']}：{row['是否存在']}（{row['严重程度']}）" for row in audit if row["是否存在"] == "是"]
    if not risk_lines:
        risk_lines = ["- 未发现结构化审计中的显著风险，但仍需人工复核。"]
    return "\n".join(
        [
            "# 浙江普通类二段志愿方案报告",
            "",
            "## 基本信息",
            "",
            f"- 考生：2026浙江普通类{profile.get('application_stage', '')}，总分{profile.get('score', '')}，原始位次{profile.get('rank', '')}",
            f"- 选考科目：{stringify(profile.get('subjects', []))}",
            f"- 听力状态：{profile.get('hearing_status', '待确认')}；按用户要求不作硬排除，仅在章程明确限制时复核",
            f"- 二段剩余队列：{profile.get('score', '待确认')}分及以上累计{profile.get('remaining_queue_at_or_above', '待获取')}人；该数字不是原始位次",
            f"- 用户是否要求志愿排序表：{'是' if profile.get('need_volunteer_table', True) else '否'}",
            f"- 本次生成志愿数量：{len(volunteers)}",
            f"- 是否达到用户要求数量：{'是' if reached else '否'}",
            f"- 如果不足，说明原因：{shortage_reason}",
            "- 默认目标为 80 个",
            "- 用户可设置 1-80",
            "",
            "## 本科资格",
            "",
            f"- 是否具有本科填报资格：{opportunity['undergraduate_eligibility']}",
            f"- 本科可报数量：{opportunity['undergraduate_eligible_count']}",
            f"- 当前计划数：{opportunity['current_plan_count']}",
            "",
            "## 实际机会",
            "",
            f"- 本科最近历史位次：{opportunity['nearest_historical_undergraduate_rank']}",
            f"- 与考生位次差：{opportunity['nearest_historical_rank_gap']}",
            f"- 本科机会结论：{opportunity['undergraduate_verdict']}",
            f"- 当前判断是否仅基于历史：{'否' if opportunity['current_plan_verified'] else '是'}",
            "",
            "## 本科冲刺",
            "",
            f"- 已列本科/职业本科志愿：{degree_counts['本科'] + degree_counts['职业本科']}",
            "- 二段本科只列为冲，不得标为稳或保。",
            "",
            "## 专科稳保",
            "",
            f"- 已列专科志愿：{degree_counts['专科']}",
            "- 专科承担主要稳保功能；没有足量专科稳保时不得宣称方案完整。",
            "",
            "## 冲稳保分布",
            "",
            f"- 冲：{counts['冲']}",
            f"- 稳：{counts['稳']}",
            f"- 保：{counts['保']}",
            "",
            "## 主要风险",
            "",
            *risk_lines,
            "",
            "## 排除概览",
            "",
            f"- 排除项数量：{len(excluded)}",
            "",
            "## 人工复核声明",
            "",
            "最终填报前必须人工核对个性化剩余计划、专业代码、学费、校区、选科要求、听力/体检限制和招生章程。本报告不承诺录取，不替代官方志愿系统。",
            "",
        ]
    )


def manual_review_rows(volunteers: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        row
        for row in volunteers
        if row.get("是否需要强制复核") == "是" or stringify(row.get("人工复核项", ""))
    ]


def data_source_rows(volunteers: list[dict[str, object]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    rows: list[dict[str, str]] = []
    for index, volunteer in enumerate(volunteers, start=1):
        source = stringify(volunteer.get("数据来源", "")) or "未记录"
        if source in seen:
            continue
        seen.add(source)
        rows.append(
            {
                "source_id": f"SRC-{index:03d}",
                "source_name": source,
                "source_type": "sample/mock" if "sample/mock" in source else "official/user-supplied",
                "source_url": "",
                "file_name": source,
                "download_date": "",
                "official_or_not": "否" if "sample/mock" in source else "待人工确认",
                "used_for": "volunteer_table",
                "sha256": "",
                "parse_status": "sample/mock" if "sample/mock" in source else "待人工确认",
                "notes": "sample/mock 数据不得当成真实数据" if "sample/mock" in source else "真实数据需人工核对",
            }
        )
    return rows


def generate_all_outputs(
    output_dir: Path,
    profile: dict[str, object],
    volunteers: list[dict[str, object]],
    excluded: list[dict[str, object]],
    audit: list[dict[str, object]],
    opportunity: dict[str, object] | None = None,
) -> None:
    ensure_dir(output_dir)
    write_csv_rows(output_dir / "volunteer_table.csv", volunteers, VOLUNTEER_COLUMNS)
    write_xlsx(output_dir / "volunteer_table.xlsx", volunteers, VOLUNTEER_COLUMNS)
    write_csv_rows(output_dir / "excluded_list.csv", excluded, EXCLUDED_COLUMNS)
    write_csv_rows(output_dir / "risk_audit.csv", audit, AUDIT_COLUMNS)
    write_csv_rows(output_dir / "manual_review_list.csv", manual_review_rows(volunteers), VOLUNTEER_COLUMNS)
    write_csv_rows(
        output_dir / "data_source_log.csv",
        data_source_rows(volunteers),
        [
            "source_id",
            "source_name",
            "source_type",
            "source_url",
            "file_name",
            "download_date",
            "official_or_not",
            "used_for",
            "sha256",
            "parse_status",
            "notes",
        ],
    )
    opportunity = opportunity or assess_undergraduate_opportunity(profile, volunteers)
    write_json(output_dir / "opportunity_summary.json", opportunity)
    (output_dir / "final_report.md").write_text(
        build_report(profile, volunteers, excluded, audit, opportunity),
        encoding="utf-8",
    )


def run_sample_pipeline(root: Path = ROOT, output_dir: Path | None = None) -> dict[str, object]:
    output_dir = output_dir or (root / "outputs")
    processed_dir = root / "data" / "processed"
    copy_sample_to_processed(root)
    merged = merge_plan_history(processed_dir, output_dir / "merged_plan_history.csv")
    profile = load_profile(root / "examples" / "sample_input.md")
    write_json(output_dir / "validated_input.json", profile)
    candidates, excluded = generate_candidate_pool_rows(profile, merged)
    candidate_fields = list(merged[0].keys()) + [
        "subject_match",
        "tuition_over_budget",
        "transfer_bridge",
        "medical_risk",
        "force_review",
        "candidate_notes",
    ]
    write_csv_rows(output_dir / "candidate_pool.csv", candidates, candidate_fields)
    write_csv_rows(output_dir / "excluded_list.csv", excluded, EXCLUDED_COLUMNS)
    ranked = add_rank_gaps(candidates, int(profile["rank"]))
    rank_fields = candidate_fields + [f"{year}_rank_gap" for year in HISTORICAL_YEARS] + ["history_year_count", "rank_stability"]
    write_csv_rows(output_dir / "rank_gap.csv", ranked, rank_fields)
    volunteers = classify_and_select_volunteers(ranked, profile)
    write_csv_rows(output_dir / "volunteer_table.csv", volunteers, VOLUNTEER_COLUMNS)
    audit = audit_rows(volunteers, excluded, profile)
    write_csv_rows(output_dir / "risk_audit.csv", audit, AUDIT_COLUMNS)
    opportunity = assess_undergraduate_opportunity(profile, ranked, current_plan_verified=True)
    generate_all_outputs(output_dir, profile, volunteers, excluded, audit, opportunity)
    return {
        "profile": profile,
        "merged": merged,
        "candidates": candidates,
        "excluded": excluded,
        "ranked": ranked,
        "volunteers": volunteers,
        "audit": audit,
        "opportunity": opportunity,
        "output_dir": output_dir,
    }
