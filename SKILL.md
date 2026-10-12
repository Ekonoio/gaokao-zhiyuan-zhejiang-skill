---
name: gaokao-zhiyuan-zhejiang-skill
description: Assist Zhejiang 2026 ordinary-category second-stage volunteer planning using a user-supplied profile, official public data and a manually downloaded personalized plan. Keep stage independent from degree level, filter eligibility, assess undergraduate opportunities and report mandatory review items without inventing plans or promising admission.
---

# Zhejiang Ordinary Second-Stage Volunteer Planning

Use this skill only for 浙江省2026普通类第二段. Do not use it for art, sports, advance admission, 三位一体, 强基计划, military/police, or special-plan paths.

## Candidate Intake

Read the user's local profile, using `templates/intake_form.md` for required fields. `examples/target_candidate.json` is synthetic test input only; never treat it as the user's data.
Confirm score, original rank, subjects, single-subject scores, year, gender, foreign language, degree preferences, budget, geographic exclusions, major preferences and medical/hearing status. Do not request identity numbers or login credentials. Ask about missing constraints before producing a final list.

Run both fetch and workflow commands with `--profile data/raw/my_profile.json`. Use a separate processed directory when working with multiple candidates. The example has Politics/History/Geography; any other profile requires rechecking all subject rules.

## Non-Negotiable Rules

- `application_stage` and `degree_level` are independent. 二段 may contain 本科、职业本科 and 专科.
- Never infer degree level from stage or stage from degree level.
- Preserve the profile's `rank` as the original rank. `remaining_queue_at_or_above` is only the second-stage unadmitted queue size.
- Filter against the user's actual subjects. For the Politics/History/Geography example, exclude plans requiring 物理、化学 or 生物.
- Hard-filter explicit single-subject, foreign-language, gender, degree, stage and medical restrictions.
- When hearing status is unknown, force manual review; do not declare the choice restriction-free.
- In second stage, every undergraduate or vocational-undergraduate option is `冲`. Never classify it as `稳` or `保`.
- Put all undergraduate options the candidate genuinely accepts before associate-degree stable/safe choices.
- Do not promise admission.

## Data Boundary

Automatically fetch public official data:

- 2026 ordinary-category segment lines.
- 2026 second-stage remaining-candidate score table.
- 2023-2025 official major admission results.
- Public charter pages listed in `data/raw/charter_urls.csv`.

Record the source URL, UTC download time, SHA256 and parse status in `data/raw/official/source_manifest.csv`.

The 2026 personalized remaining plan requires login or verification and cannot be fetched automatically. The user must download its XLSM/XLSX from the Zhejiang Education Examination Authority and place it at:

`data/raw/current_second_stage_plan.xlsm`

Without that file:

- Produce only historical undergraduate-opportunity analysis.
- Produce an empty current-year volunteer table.
- State the required manual action.
- Do not name or recommend any 2026 school/program.

## Required Workflow

Run from the skill directory:

```powershell
$py = 'python'

& $py scripts/fetch_official_data.py --profile data/raw/my_profile.json
& $py scripts/run_candidate_workflow.py --profile data/raw/my_profile.json
```

After the user downloads the personalized plan:

```powershell
& $py scripts/import_second_stage_plan.py data/raw/current_second_stage_plan.xlsm
& $py scripts/run_candidate_workflow.py --profile data/raw/my_profile.json
```

For mock development only:

```powershell
& $py scripts/clean_admission_data.py --use-sample
& $py -m pytest tests
```

## Opportunity Output

Every final report must contain four sections:

1. 本科资格.
2. 实际机会.
3. 本科冲刺.
4. 专科稳保.

It must expose:

- 本科可报数量.
- 本科最近历史位次.
- 位次差, calculated as `historical_min_rank - profile.rank`.
- 当前计划数.
- 本科机会结论.

Use 2025 `上海兴伟学院 英语`, minimum rank 185225, as a parser regression benchmark. Its rank gap for the synthetic example is `-34775`; this is historical evidence, not a 2026 recommendation.

## Output Contract

Write results under `outputs/target_candidate/`:

- `final_report.md`
- `opportunity_summary.json`
- `volunteer_table.csv`
- `volunteer_table.xlsx`
- `excluded_list.csv`
- `risk_audit.csv`
- `manual_review_list.csv`
- `data_source_log.csv`
- `official_source_manifest.csv`

Read `data/processed/README.md`, `rules/hard_filters.md`, and `rules/rank_rules.md` before changing schemas or ranking behavior.
