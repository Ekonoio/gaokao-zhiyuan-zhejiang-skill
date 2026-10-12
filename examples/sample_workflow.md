> 所有示例成绩、位次和偏好均为模拟配置；正式使用请替换为本人数据。

# sample 工作流

在 `gaokao-zhiyuan-zhejiang-skill/` 目录执行：

```powershell
$py = 'python'
& $py scripts/clean_admission_data.py --use-sample
& $py scripts/merge_plan_history.py
& $py scripts/validate_input.py --input examples/sample_input.md --output outputs/validated_input.json
& $py scripts/generate_candidate_pool.py
& $py scripts/calculate_rank_gap.py
& $py scripts/classify_tier.py
& $py scripts/audit_plan.py
& $py scripts/search_charter.py --school-code MOCK006 --risk-type 体检 --keyword 色弱
& $py scripts/generate_report.py
& $py -m pytest tests
```

真实数据接入时，先自动抓取公开官方数据：

```powershell
& $py scripts/fetch_official_data.py
& $py scripts/run_candidate_workflow.py
```

登录后可见的2026个性化二段剩余计划必须由用户手工下载：

```powershell
& $py scripts/import_second_stage_plan.py data/raw/current_second_stage_plan.xlsm
& $py scripts/run_candidate_workflow.py
```

没有个性化计划时只输出历史判断，不生成2026具体院校专业名单。
