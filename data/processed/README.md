# data/processed

此目录存放标准化数据。公开数据由 `fetch_official_data.py` 生成；个性化二段计划由 `import_second_stage_plan.py` 生成；`--use-sample` 只用于测试。

## admissions_plan.csv

2026考生个性化二段剩余计划。核心字段：

- `year`, `province`, `batch`, `application_stage`
- `school_code`, `school_name`, `major_code`, `major_name`, `major_group`
- `plan_count`, `tuition`, `duration`, `campus`, `city`
- `subject_requirement`, `foreign_language_requirement`, `single_subject_requirement`
- `gender_requirement`, `medical_requirement`, `remarks`
- `is_public`, `is_private`, `is_sino_foreign`
- `degree_level`, `plan_status`, `source_access`
- `source_file`, `source_url`, `updated_at`

约束：

- `application_stage=二段` 不决定 `degree_level`。
- `degree_level` 只能是 `本科`、`职业本科` 或 `专科`，不得按段次推断。
- 真实个性化计划的 `source_access` 必须是 `personalized-login-download`。
- 没有经登录下载的当前计划时，不得生成2026院校专业推荐。

## historical_admission.csv

2023-2025官方专业录取数据：

- `year`, `province`, `segment`
- `school_code`, `school_name`, `major_code`, `major_name`
- `subject_requirement`, `duration`, `degree_level`
- `plan_count`, `min_score`, `min_rank`
- `source_file`, `source_url`, `updated_at`

历史表只用于机会判断和位次差，不代表2026仍有剩余计划。

## second_stage_remaining_score_rank.csv

2026二段线上未录取考生成绩分数段表：

- `year`, `province`, `score`, `count`, `cumulative_count`
- `queue_type`, `source_file`, `source_url`, `updated_at`

`cumulative_count` 是二段未录取考生队列累计人数，不是普通类原始位次。对460分考生，原始位次始终使用220000。

## official_context.json

保存分段线、固定考生原始位次、460分对应的二段剩余队列和口径说明。不得用队列数字覆盖 `candidate_original_rank`。

## charter_chunks.jsonl

公开招生章程检索片段：

- `year`, `school_code`, `school_name`, `chunk_id`, `chunk_text`
- `section_title`, `risk_type`
- `source_url`, `source_file`, `updated_at`

章程检索仅提供证据，不替代结构化硬过滤，也不参与主观评分。

## 其他兼容表

原有 `score_rank.csv`、`school_info.csv` 和 `major_catalog.csv` 可继续按项目既有字段接入，但不应覆盖上述二段专用数据口径。
