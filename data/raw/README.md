# data/raw

此目录同时承载“可自动获取的公开文件”和“用户必须手工下载的登录文件”。

## 自动获取

运行：

```powershell
& $py scripts/fetch_official_data.py
```

脚本会把公开页面和PDF保存到 `official/files/`，并写入 `official/source_manifest.csv`。来源清单至少包含：

- `source_url`
- `download_date`
- `sha256`
- `parse_status`
- 数据用途和备注

已下载文件可用 `--reuse-downloads` 重新解析，不重复联网。

## 手工下载

以下内容不能自动获取：

- `current_second_stage_plan.xlsm` 或 `.xlsx`：登录浙江省教育考试院后下载的考生个性化二段剩余计划。
- 验证码、账号信息和任何考生个人隐私数据。
- 无公开固定URL、需要逐校确认的招生章程。
- 考生听力、体检和残疾证明的准确结论。

个性化计划默认路径：

`data/raw/current_second_stage_plan.xlsm`

下载后运行：

```powershell
& $py scripts/import_second_stage_plan.py data/raw/current_second_stage_plan.xlsm
```

## 公开章程队列

如需自动抓取公开章程，可创建 `data/raw/charter_urls.csv`：

```csv
year,school_code,school_name,source_url
2026,院校代码,院校名称,公开章程URL
```

只填写无需登录、无需验证码且允许正常公开访问的页面。抓取结果会写入 `data/processed/charter_chunks.jsonl`。
