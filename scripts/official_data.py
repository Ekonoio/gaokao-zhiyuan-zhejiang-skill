from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import unicodedata
from collections.abc import Iterable
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from common import ensure_dir, stringify, to_int, write_csv_rows, write_json


SOURCE_MANIFEST_COLUMNS = [
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
]

HISTORICAL_COLUMNS = [
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
]

SECOND_STAGE_SCORE_COLUMNS = [
    "year",
    "province",
    "score",
    "count",
    "cumulative_count",
    "queue_type",
    "source_file",
    "source_url",
    "updated_at",
]


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href = ""
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        self._href = dict(attrs).get("href") or ""
        self._text = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href:
            self.links.append((self._href, "".join(self._text).strip()))
            self._href = ""
            self._text = []


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def decode_html(payload: bytes) -> str:
    for encoding in ["utf-8", "gb18030"]:
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8", errors="replace")


def visible_text(page_html: str) -> str:
    text = re.sub(r"(?is)<script.*?>.*?</script>|<style.*?>.*?</style>", " ", page_html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def extract_links(page_html: str, base_url: str) -> list[tuple[str, str]]:
    parser = LinkParser()
    parser.feed(page_html)
    return [(urljoin(base_url, href), text) for href, text in parser.links]


def download(url: str, timeout: int = 45) -> tuple[bytes, str]:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 Codex Zhejiang Gaokao Skill/1.0",
            "Accept": "text/html,application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read(), response.headers.get("Content-Type", "")


def parse_segment_lines(page_html: str) -> dict[str, int]:
    text = visible_text(page_html)
    match = re.search(
        r"普通类\s+第\s*一\s*段\s+第\s*二\s*段\s+分数线\s+(\d+)\s+(\d+)",
        text,
    )
    if not match:
        raise ValueError("未能从官方页面解析普通类一段、二段分数线")
    return {"first_segment_line": int(match.group(1)), "second_segment_line": int(match.group(2))}


def parse_second_stage_score_pdf(
    path: Path,
    year: int,
    source_url: str,
) -> list[dict[str, object]]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("缺少 pypdf，无法解析二段剩余考生分数段表") from exc

    rows: list[dict[str, object]] = []
    updated_at = utc_now()
    for page in PdfReader(path).pages:
        for raw_line in (page.extract_text() or "").splitlines():
            line = unicodedata.normalize("NFKC", raw_line).strip()
            match = re.fullmatch(r"(\d{3})\s+(\d+)\s+(\d+)", line)
            if not match:
                continue
            rows.append(
                {
                    "year": year,
                    "province": "浙江",
                    "score": int(match.group(1)),
                    "count": int(match.group(2)),
                    "cumulative_count": int(match.group(3)),
                    "queue_type": "二段线上未录取考生，不是普通类原始位次",
                    "source_file": path.name,
                    "source_url": source_url,
                    "updated_at": updated_at,
                }
            )
    if not rows:
        raise ValueError("二段剩余考生分数段PDF未解析到数据行")
    return rows


def parse_historical_admission_pdf(
    path: Path,
    year: int,
    source_url: str,
) -> list[dict[str, object]]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError("缺少 pypdf，无法解析历史录取PDF") from exc

    page_texts = ((page.extract_text() or "") for page in PdfReader(path).pages)
    return parse_historical_page_texts(page_texts, year, source_url, path.name)


def parse_historical_page_texts(
    page_texts: Iterable[str],
    year: int,
    source_url: str,
    source_file: str,
) -> list[dict[str, object]]:
    subject_pattern = (
        r"(不限|不提科目要求|(?:思想政治|政治|历史|地理|物理|化学|生物)"
        r"(?:\s*[&＆+/]\s*(?:思想政治|政治|历史|地理|物理|化学|生物))*)"
    )
    row_pattern = re.compile(r"^(.*?)\s+" + subject_pattern + r"\s+(\d+)\s+([2-6])\s+(.+)$")
    school_pattern = re.compile(r"^(\d{4})\s+(.+?)(?:\s*)[（(]")
    rows: list[dict[str, object]] = []
    school_code = ""
    school_name = ""
    pending_school_code = ""
    updated_at = utc_now()
    in_parallel_section = False

    for page_text in page_texts:
        page_text = str(page_text or "")
        normalized_page = re.sub(r"\s+", "", unicodedata.normalize("NFKC", page_text))
        if (
            "普通类平行投档一、二段各专业录取情况" in normalized_page
            and "院校代码、院校" in normalized_page
        ):
            in_parallel_section = True
        if not in_parallel_section:
            continue
        for raw_line in page_text.splitlines():
            line = unicodedata.normalize("NFKC", raw_line).strip()
            school_match = school_pattern.match(line)
            if school_match:
                school_code = school_match.group(1)
                school_name = school_match.group(2).strip()
                pending_school_code = ""
                continue
            if re.fullmatch(r"\d{4}", line):
                pending_school_code = line
                continue
            if pending_school_code and re.search(r"[（(]", line):
                school_code = pending_school_code
                school_name = re.split(r"[（(]", line, maxsplit=1)[0].strip()
                pending_school_code = ""
                continue
            match = row_pattern.match(line)
            if not match or not school_code:
                continue
            major_name, requirement, admitted_count, duration, tail = match.groups()
            numbers = [int(value) for value in re.findall(r"\d+", tail)]
            if len(numbers) < 3:
                continue
            if len(numbers) >= 5:
                segment = "二段"
                min_score, min_rank = numbers[-2], numbers[-1]
            else:
                segment = "一段"
                min_score, min_rank = numbers[-2], numbers[-1]
            if not (100 <= min_score <= 750 and 1 <= min_rank <= 500000):
                continue
            requirement = re.sub(r"(?<!思想)政治", "思想政治", requirement)
            requirement = requirement.replace("&", "+").replace("＆", "+").replace("/", "或")
            duration_years = int(duration)
            rows.append(
                {
                    "year": year,
                    "province": "浙江",
                    "segment": segment,
                    "school_code": school_code,
                    "school_name": school_name,
                    "major_code": "",
                    "major_name": major_name.strip(),
                    "subject_requirement": requirement,
                    "duration": f"{duration_years}年",
                    "degree_level": "本科" if duration_years >= 4 else "专科",
                    "plan_count": int(admitted_count),
                    "min_score": min_score,
                    "min_rank": min_rank,
                    "source_file": source_file,
                    "source_url": source_url,
                    "updated_at": updated_at,
                }
            )
    if not rows:
        raise ValueError(f"{source_file} 未解析到历史专业录取数据")
    return rows


def load_source_config(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_manifest(path: Path, rows: list[dict[str, object]]) -> None:
    write_csv_rows(path, rows, SOURCE_MANIFEST_COLUMNS)


def read_charter_queue(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def charter_chunks(
    page_html: str,
    school_code: str,
    school_name: str,
    source_url: str,
    source_file: str,
    year: int,
) -> list[dict[str, object]]:
    text = visible_text(page_html)
    chunks: list[dict[str, object]] = []
    for index in range(0, len(text), 1800):
        chunk = text[index : index + 1800].strip()
        if not chunk:
            continue
        chunks.append(
            {
                "year": year,
                "school_code": school_code,
                "school_name": school_name,
                "chunk_id": f"{school_code or 'UNKNOWN'}-{index // 1800 + 1:03d}",
                "chunk_text": chunk,
                "section_title": "招生章程网页自动抓取",
                "risk_type": "其他",
                "source_url": source_url,
                "source_file": source_file,
                "updated_at": utc_now(),
            }
        )
    return chunks


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    ensure_dir(path.parent)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
