# 数据校验规则

## 输入校验

必填字段必须存在且非空：

- source_province
- exam_year
- candidate_category
- application_stage
- score
- rank
- subjects
- gender
- foreign_language
- target_region
- only_undergraduate
- accept_associate
- accept_private
- accept_sino_foreign
- tuition_limit
- accepted_majors
- rejected_majors
- priority
- risk_preference
- medical_limits
- need_volunteer_table
- volunteer_count
- tier_strategy

`source_province` 固定为 `浙江`，`candidate_category` 固定为 `普通类`，`application_stage` 固定为 `二段`。

`rank` 可接收 `5-220000`，标准化后必须是220000。二段剩余累计人数必须存入独立字段，不得覆盖原始位次。

`volunteer_count` 必须在 1-80。

## 数据表校验

- 所有标准表必须包含 `source_file`、`source_url`、`updated_at`，用于复核。
- 当前计划必须同时包含 `application_stage` 和 `degree_level`，禁止互相推断。
- 当前计划必须包含选科、单科、外语、性别、体检限制字段；缺失时进入人工复核。
- `school_code + major_code` 是首选匹配键；官方历史PDF缺少专业代码时可使用 `school_code + 规范化专业名称`，但必须记录 `history_match_method`。
- 专业代码、学校代码、校区、学费、选科要求缺失时必须进入人工复核。
- 个性化当前计划只有在 `source_access=personalized-login-download` 时才算已验证。
- 公开抓取来源必须记录URL、下载时间、SHA256和解析状态。

## sample/mock 标识

sample 数据必须包含 `source_file=sample/mock` 或明显的 MOCK 代码和名称，不得伪装为真实数据。
