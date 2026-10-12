# 浙江普通类二段志愿 Skill

面向 Codex 的浙江普通类二段志愿辅助工具，目前规则与官方抓取源针对2026年，历史数据范围为2023-2025年。其他年份必须先更新并核验规则、来源和计划，不能直接套用。

本仓库是脱敏公开版本。所有默认考生信息均为模拟输入，不是真实考生资料，也不是可直接填报的志愿名单。原始招生文件、登录下载的个人计划、真实处理结果和志愿结果均不包含在仓库中。

## 安装与运行

将本仓库完整克隆到你的 Codex 技能目录，保持 `SKILL.md` 与脚本、规则的相对路径不变。Python 要求3.10或更新版本。

```powershell
git clone https://github.com/Ekonoio/gaokao-zhiyuan-zhejiang-skill.git
cd gaokao-zhiyuan-zhejiang-skill
python -m pip install -r requirements.txt
```

复制 `examples/target_candidate.json` 到 `data/raw/my_profile.json`，填写本人真实成绩、原始位次、选科、预算、地区、专业偏好与体检情况。不要将个人配置提交到 GitHub。

```powershell
python scripts/fetch_official_data.py --profile data/raw/my_profile.json
python scripts/import_second_stage_plan.py data/raw/current_second_stage_plan.xlsm
python scripts/run_candidate_workflow.py --profile data/raw/my_profile.json
```

个性化剩余计划必须由本人从考试院登录系统下载。抓取器只处理公开官方数据及用户配置的公开章程URL，不代替登录或绕过验证码。没有经导入验证的个性化计划时，只输出历史判断和空志愿表，不编造当年推荐。

新建 `data/raw/charter_urls.csv` 可参考 `data/raw/charter_urls.example.csv`。抓取日志保存来源URL、下载时间、SHA256和解析状态。不同考生不要混用同一个处理目录；换配置时重新抓取与导入计划。

## 判断边界

- 填报段次与学历层次分离：二段不等于专科，可包含本科、职业本科和专科。
- 原始位次用于历史比较；二段未录取队列累计人数不是原始位次。
- 按选科、单科、外语、性别、预算、学历、段次及明确体检条款过滤。
- 本版本采用保守二段策略：本科与职业本科只进入冲刺项，专科承担稳保。
- 听力、章程、学费、校区及其他无法核实的限制进入人工复核。
- 不承诺录取，不保证补足80项，更不能保证有学上；候选不足会如实报告。
- 示例专业、地区及冲稳保比例只是可修改配置，不是普遍建议。

## 输出与复核

默认结果位于 `outputs/target_candidate/`：志愿表CSV/XLSX、本科机会摘要、最终报告、排除记录、风险审计、人工复核清单和来源日志。

最终提交前逐项核对考试院系统的院校代码、专业代码、计划数、选科、学费、校区和最新章程。工具不代替考试院系统校验；CSV/XLSX输出不保证直接满足系统XLS导入格式，须使用本人当次下载的模板进行核对。

## 测试与辅助脚本

```powershell
python -m pytest tests
```

仓库自带 `pytest.py` 是轻量测试运行器，支持本仓库测试，不是完整的第三方pytest实现。`data/sample/` 是模拟数据；`tests/fixtures/` 中官方历史摘录只用于解析回归，不是当前招生计划。

正式入口是 `fetch_official_data.py`、`import_second_stage_plan.py`、`run_candidate_workflow.py`。早期的 `build_*`、`optimize_considered_plan.py`、`finalize_candidate_outputs.py` 等脚本保留为定制案例，其中有固定比例、偏好和模拟档案描述，不能未经检查用于其他考生。`.mjs` 还依赖 Codex 提供的 `@oai/artifact-tool`，不属于Python主流程必需依赖，运行时应在仓库根目录启动。

本项目只覆盖浙江普通类二段，不处理艺术、体育、提前批、强基、三位一体、军警或专项计划。当前未指定开源许可证；公开可浏览不等于授予任意复制、再分发或商业使用许可。
