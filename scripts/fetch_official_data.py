from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from common import ROOT, load_profile, write_csv_rows, write_json
from official_data import (
    HISTORICAL_COLUMNS,
    SECOND_STAGE_SCORE_COLUMNS,
    charter_chunks,
    decode_html,
    download,
    extract_links,
    load_source_config,
    parse_historical_admission_pdf,
    parse_second_stage_score_pdf,
    parse_segment_lines,
    read_charter_queue,
    sha256_bytes,
    utc_now,
    write_jsonl,
    write_manifest,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="下载并解析浙江省教育考试院公开数据。")
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "official_sources.json")
    parser.add_argument("--profile", type=Path, default=ROOT / "examples" / "target_candidate.json")
    parser.add_argument("--raw-dir", type=Path, default=ROOT / "data" / "raw" / "official")
    parser.add_argument("--processed-dir", type=Path, default=ROOT / "data" / "processed")
    parser.add_argument("--skip-history", action="store_true", help="跳过2023-2025历史录取PDF解析")
    parser.add_argument("--reuse-downloads", action="store_true", help="复用已下载文件，仅重新解析")
    args = parser.parse_args()

    config = load_source_config(args.config)
    profile = load_profile(args.profile)
    args.raw_dir.mkdir(parents=True, exist_ok=True)
    args.processed_dir.mkdir(parents=True, exist_ok=True)
    files_dir = args.raw_dir / "files"
    files_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, object]] = []
    failures: list[str] = []

    def fetch(source_id: str, name: str, url: str, filename: str, used_for: str) -> tuple[Path | None, bytes | None]:
        path = files_dir / filename
        try:
            if args.reuse_downloads and path.exists():
                payload = path.read_bytes()
                status = "cached"
            else:
                payload, _ = download(url)
                path.write_bytes(payload)
                status = "downloaded"
            manifest.append(
                {
                    "source_id": source_id,
                    "source_name": name,
                    "source_type": "official-public",
                    "source_url": url,
                    "file_name": str(path.relative_to(args.raw_dir)),
                    "download_date": utc_now(),
                    "official_or_not": "是",
                    "used_for": used_for,
                    "sha256": sha256_bytes(payload),
                    "parse_status": status,
                    "notes": "",
                }
            )
            return path, payload
        except Exception as exc:
            failures.append(f"{name}: {exc}")
            manifest.append(
                {
                    "source_id": source_id,
                    "source_name": name,
                    "source_type": "official-public",
                    "source_url": url,
                    "file_name": filename,
                    "download_date": utc_now(),
                    "official_or_not": "是",
                    "used_for": used_for,
                    "sha256": "",
                    "parse_status": "error",
                    "notes": str(exc),
                }
            )
            return None, None

    segment_source = config["segment_lines"]
    segment_path, segment_payload = fetch(
        "ZJ-SEGMENT-2026",
        "2026浙江普通类分段线",
        segment_source["url"],
        segment_source["filename"],
        "本科资格和二段线",
    )
    context: dict[str, object] = {
        "year": int(profile["exam_year"]),
        "candidate_score": int(profile["score"]),
        "candidate_original_rank": int(profile["rank"]),
        "application_stage": profile["application_stage"],
        "queue_definition": "二段线上未录取考生累计人数，不是普通类原始位次",
        "updated_at": utc_now(),
    }
    if segment_payload is not None:
        try:
            context.update(parse_segment_lines(decode_html(segment_payload)))
            manifest[-1]["parse_status"] = "parsed"
        except Exception as exc:
            failures.append(f"分段线解析: {exc}")
            manifest[-1]["parse_status"] = "parse_error"
            manifest[-1]["notes"] = str(exc)

    score_source = config["second_stage_score"]
    score_page_path, score_page_payload = fetch(
        "ZJ-SECOND-STAGE-SCORE-PAGE-2026",
        "2026二段线上考生成绩分数段表页面",
        score_source["url"],
        score_source["filename"],
        "二段剩余竞争队列",
    )
    if score_page_payload is not None:
        page_html = decode_html(score_page_payload)
        pdf_links = [
            (url, text)
            for url, text in extract_links(page_html, score_source["url"])
            if ".pdf" in url.lower() or "分数段表" in text
        ]
        if pdf_links:
            score_pdf_url = pdf_links[0][0]
            score_pdf_path, _ = fetch(
                "ZJ-SECOND-STAGE-SCORE-PDF-2026",
                "2026二段线上考生成绩分数段表PDF",
                score_pdf_url,
                "2026_second_stage_remaining_score_rank.pdf",
                "二段剩余竞争队列",
            )
            if score_pdf_path:
                try:
                    score_rows = parse_second_stage_score_pdf(score_pdf_path, int(profile["exam_year"]), score_pdf_url)
                    write_csv_rows(
                        args.processed_dir / "second_stage_remaining_score_rank.csv",
                        score_rows,
                        SECOND_STAGE_SCORE_COLUMNS,
                    )
                    candidate_row = next(
                        (row for row in score_rows if int(row["score"]) == int(profile["score"])),
                        None,
                    )
                    if candidate_row:
                        context["remaining_queue_at_or_above"] = candidate_row["cumulative_count"]
                        context["remaining_same_score_count"] = candidate_row["count"]
                    manifest[-1]["parse_status"] = "parsed"
                except Exception as exc:
                    failures.append(f"二段分数段表解析: {exc}")
                    manifest[-1]["parse_status"] = "parse_error"
                    manifest[-1]["notes"] = str(exc)
        else:
            failures.append("二段分数段页面未找到PDF附件")

    if not args.skip_history:
        history_source = config["historical_admissions"]
        history_page_path, history_page_payload = fetch(
            "ZJ-HISTORY-INDEX",
            "2023-2025浙江专业录取情况索引",
            history_source["url"],
            history_source["filename"],
            "近三年投档与专业录取",
        )
        historical_rows: list[dict[str, object]] = []
        if history_page_payload is not None:
            history_links = extract_links(decode_html(history_page_payload), history_source["url"])
            for year in [2023, 2024, 2025]:
                match = next(
                    (
                        (url, text)
                        for url, text in history_links
                        if str(year) in text and (".pdf" in url.lower() or "downfile.jsp" in url.lower())
                    ),
                    None,
                )
                if not match:
                    failures.append(f"历史录取索引未找到{year}年PDF")
                    continue
                pdf_url, _ = match
                pdf_path, _ = fetch(
                    f"ZJ-HISTORY-{year}",
                    f"{year}浙江专业录取情况PDF",
                    pdf_url,
                    f"zhejiang_admission_{year}.pdf",
                    "历史位次和本科机会",
                )
                if not pdf_path:
                    continue
                try:
                    rows = parse_historical_admission_pdf(pdf_path, year, pdf_url)
                    historical_rows.extend(rows)
                    manifest[-1]["parse_status"] = f"parsed:{len(rows)}"
                except Exception as exc:
                    failures.append(f"{year}历史录取解析: {exc}")
                    manifest[-1]["parse_status"] = "parse_error"
                    manifest[-1]["notes"] = str(exc)
        if historical_rows:
            write_csv_rows(
                args.processed_dir / "historical_admission.csv",
                historical_rows,
                HISTORICAL_COLUMNS,
            )

    charter_rows: list[dict[str, object]] = []
    charter_queue = read_charter_queue(ROOT / "data" / "raw" / "charter_urls.csv")
    for index, item in enumerate(charter_queue, start=1):
        url = item.get("source_url", "")
        if not url:
            continue
        school_code = item.get("school_code", "")
        school_name = item.get("school_name", "")
        filename = f"charter_{school_code or index}.html"
        charter_path, payload = fetch(
            f"CHARTER-{school_code or index}",
            f"{school_name or school_code}招生章程",
            url,
            filename,
            "体检、单科、外语、性别等章程复核",
        )
        if charter_path and payload is not None:
            chunks = charter_chunks(
                decode_html(payload),
                school_code,
                school_name,
                url,
                charter_path.name,
                int(profile["exam_year"]),
            )
            charter_rows.extend(chunks)
            manifest[-1]["parse_status"] = f"parsed:{len(chunks)}"
    if charter_rows:
        write_jsonl(args.processed_dir / "charter_chunks.jsonl", charter_rows)

    write_json(args.processed_dir / "official_context.json", context)
    write_manifest(args.raw_dir / "source_manifest.csv", manifest)
    print(f"公开数据处理完成：{len(manifest)} 个来源，{len(failures)} 个失败。")
    if failures:
        for failure in failures:
            print(f"- {failure}")
    print(f"来源清单：{args.raw_dir / 'source_manifest.csv'}")
    print(f"官方上下文：{args.processed_dir / 'official_context.json'}")
    return 0 if not failures else 2


if __name__ == "__main__":
    sys.exit(main())
