"""Stack Exchange 数据爬取脚本:安全灌入公共库(精选高质量报错数据)。

支持两个数据源(都官方托管、CC BY-SA 4.0、批量下载合法):

1. **ClickHouse SO Parquet(推荐)** —— 按年分文件的 Stack Overflow Posts 数据,
   免账号、免解压,直接 HTTP 下载,选 1-2 个年份正好 1-2G:
       python -m crawler.stackexchange_crawler --year 2023 --limit 200000

2. **archive.org 官方 dump(小站点)** —— 每站点一个 .7z,内含 Posts.xml:
       python -m crawler.stackexchange_crawler --site unix.stackexchange.com

两种源的清洗/筛选/灌库逻辑完全复用(见 _records_from_posts),只是「读原始行」的方式不同
(XML 用 lxml.iterparse / Parquet 用 pyarrow 流式读)。

合规:source 字段存 `{site}/{question_id}`(可拼回原帖链接,满足 CC BY-SA 署名);
清洗剥离 <script>/<style>,只留纯文本。
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from typing import Iterable, Iterator, Optional

# 保证从任意目录运行本脚本都能 import core / crawler
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crawler.html_clean import html_to_text  # noqa: E402
from core.models import PublicRecord  # noqa: E402
from core.storage import PublicDatabase  # noqa: E402

# archive.org 上 stackexchange item 的下载基地址(每站点一个 {domain}.7z)
ARCHIVE_BASE = "https://archive.org/download/stackexchange"

# ClickHouse 托管的 Stack Overflow Posts Parquet(按年,CC BY-SA 4.0)
CLICKHOUSE_SO_BASE = "https://datasets-documentation.s3.eu-west-3.amazonaws.com/stackoverflow/parquet/posts"

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

# 每批写库条数(避免一次写几十万条占内存;每批落一次 JSON + 索引 pickle)
BATCH_SIZE = 8000

# 下载限速(字节/秒),默认 2 MB/s,对数据源礼貌且不触发限流
DOWNLOAD_RATE = 2 * 1024 * 1024


# ---------- 报错判定 ----------

# 标题/正文里的报错特征(不区分大小写)
_ERROR_MARKER_RE = re.compile(
    r"traceback|exception|\berror\b|errors|warning|warnings|\braise\b|"
    r"\bfailed\b|\bfails\b|failure|crash|segfault|not working|"
    r"\bcannot\b|\bcan['’]t\b|\bunable to\b",
    re.IGNORECASE,
)

# 从文本里提取报错类型:形如 XxxError / XxxException / XxxWarning
_ERROR_TYPE_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*(?:Error|Exception|Warning|Fault|Failure)\b")

# 报错类标签(问题 Tags 命中即视为报错问题)
_ERROR_TAGS = {
    "error", "errors", "exception", "traceback", "stack-trace",
    "segmentation-fault", "debugging", "warnings", "crash",
}

# tag → 语言 映射(从问题 Tags 推断语言)
_LANG_TAGS = {
    "python": "Python", "python-2.x": "Python", "python-3.x": "Python",
    "django": "Python", "flask": "Python", "pandas": "Python", "numpy": "Python",
    "java": "Java", "javascript": "JavaScript", "node.js": "JavaScript",
    "typescript": "TypeScript", "c++": "C++", "c": "C", "c#": "C#",
    "php": "PHP", "ruby": "Ruby", "go": "Go", "golang": "Go", "rust": "Rust",
    "swift": "Swift", "kotlin": "Kotlin", "scala": "Scala", "r": "R",
    "bash": "Bash", "shell": "Bash", "sql": "SQL", "mysql": "SQL",
    "postgresql": "SQL", "matlab": "MATLAB", "perl": "Perl", "lua": "Lua",
    "dart": "Dart", "haskell": "Haskell", "objective-c": "Objective-C",
    "assembly": "Assembly", "html": "HTML", "css": "CSS",
}


def parse_tags(tags) -> list[str]:
    """Tags 字段多种形态,统一拆成 list[str]:
    - XML 源:`<python><pip>`(尖括号包裹)
    - ClickHouse Parquet 源:`|python|pip|`(竖线分隔,首尾各一个竖线)
    - 也可能是 list。
    """
    if not tags:
        return []
    if isinstance(tags, str):
        if "|" in tags:
            return [t.strip() for t in tags.split("|") if t.strip()]
        return re.findall(r"<([^>]+)>", tags)
    return [str(t).strip() for t in tags if str(t).strip()]


def _decode_bytes(v):
    """Parquet 的 binary 列读出来是 bytes,统一解码成 str;其它类型原样返回。"""
    if isinstance(v, bytes):
        return v.decode("utf-8", errors="replace")
    return v


def infer_language(tags: list[str]) -> str:
    """从 Tags 推断语言;推断不出返回空串。"""
    for t in tags:
        if t in _LANG_TAGS:
            return _LANG_TAGS[t]
    return ""


def extract_error_type(text: str) -> str:
    """从文本里提取第一个报错类型词;没有则返回空串。"""
    m = _ERROR_TYPE_RE.search(text or "")
    return m.group(0) if m else ""


def is_error_question(title: str, body: str, tags: list[str]) -> bool:
    """判断一条问题是否为报错类:标签含报错类标签,或标题/正文含报错特征。

    报错特征分两类:通用词(traceback/error/failed...)与具体异常名(TypeError 等)。
    """
    if any(t in _ERROR_TAGS for t in tags):
        return True
    text = f"{title} {body}"
    return bool(_ERROR_MARKER_RE.search(text) or _ERROR_TYPE_RE.search(text))


# ---------- 通用:从「行流」产出报错记录(两个源复用) ----------

def _records_from_posts(rows: Iterable[dict], site: str) -> Iterator[PublicRecord]:
    """从 (PostTypeId, 字段) 行流产出报错类 PublicRecord(问题 + 最佳答案)。

    rows 每项是一个 dict,至少含:PostTypeId("1"=问题 / "2"=答案)、Id、以及问题需
    Title/Body/Tags/AcceptedAnswerId,答案需 ParentId/Score/Body。
    单遍扫:报错问题暂存内存,答案命中父问题时记录「采纳答案优先、否则最高分」答案。
    """
    questions: dict[str, dict] = {}
    answers: dict[str, dict] = {}

    def _flush(qid: str, q: dict) -> Optional[PublicRecord]:
        a = answers.get(qid)
        if not a or not a.get("body"):
            return None
        solution = a["body"]
        message = q["title"] or q["body"]
        if len(solution) < 20 or len(message) < 10:
            return None
        error_type = extract_error_type(q["title"] + " " + q["body"])
        tags = q["tags"]
        lang = q["lang"] or infer_language(tags)
        return PublicRecord(
            error_type=error_type,
            error_message=message,
            language=lang,
            solution=solution,
            tags=tags[:10],                      # 控制 tags 数量,避免过长
            source=f"{site}/{qid}",              # 满足 CC BY-SA 署名,可拼回链接
        )

    for row in rows:
        post_type = str(row.get("PostTypeId", ""))
        if post_type == "1":                     # 问题
            title = str(row.get("Title") or "")
            body = html_to_text(str(row.get("Body") or ""))
            tags = parse_tags(row.get("Tags"))
            if is_error_question(title, body, tags):
                qid = str(row.get("Id", ""))
                questions[qid] = {
                    "title": title,
                    "body": body,
                    "tags": tags,
                    "lang": infer_language(tags),
                    "accepted_id": str(row.get("AcceptedAnswerId") or ""),
                }
        elif post_type == "2":                   # 答案
            parent = str(row.get("ParentId", ""))
            if parent in questions:
                score = int(row.get("Score") or 0)
                body = html_to_text(str(row.get("Body") or ""))
                is_accepted = bool(body) and questions[parent]["accepted_id"] == str(row.get("Id", ""))
                cur = answers.get(parent)
                if is_accepted:
                    answers[parent] = {"body": body, "is_accepted": True, "score": score}
                elif cur is None or (not cur.get("is_accepted") and score > cur["score"]):
                    answers[parent] = {"body": body, "is_accepted": False, "score": score}

    for qid, q in questions.items():
        rec = _flush(qid, q)
        if rec is not None:
            yield rec


# ---------- 阶段 1:下载 ----------

def download(url: str, dest: Path, rate: int = DOWNLOAD_RATE, chunk: int = 256 * 1024) -> Path:
    """流式下载 URL 到 dest,支持断点续传(Range)与限速。返回 dest。"""
    import httpx

    dest.parent.mkdir(parents=True, exist_ok=True)
    headers: dict[str, str] = {}
    existing = dest.stat().st_size if dest.exists() else 0
    if existing:
        headers["Range"] = f"bytes={existing}-"

    with httpx.stream("GET", url, headers=headers, follow_redirects=True, timeout=60.0) as resp:
        resp.raise_for_status()
        if resp.status_code == 206:      # 断点续传生效
            mode, offset = "ab", existing
        elif resp.status_code == 200:     # 服务器忽略 Range,重新下载
            mode, offset = "wb", 0
        else:
            raise RuntimeError(f"下载失败:HTTP {resp.status_code}")

        # 总大小:优先 Content-Range(续传),否则 Content-Length;都拿不到则不显百分比
        total: Optional[int] = None
        cr = resp.headers.get("Content-Range")
        if cr and "/" in cr:
            total = int(cr.rsplit("/", 1)[1])
        else:
            cl = resp.headers.get("Content-Length")
            if cl and cl.isdigit():
                total = int(cl)

        def _progress(done: int) -> None:
            mb = done / 1048576
            if total:
                print(f"\r  已下载 {mb:.1f}MB / {total / 1048576:.1f}MB ({done * 100 // total}%)",
                      end="", flush=True)
            else:
                print(f"\r  已下载 {mb:.1f}MB", end="", flush=True)

        with dest.open(mode) as f:
            last = time.monotonic()
            reported = -1
            for block in resp.iter_bytes(chunk_size=chunk):
                f.write(block)
                offset += len(block)
                # 限速:按 rate 字节/秒估算该 chunk 应耗时,不足则睡
                now = time.monotonic()
                expected = len(block) / rate
                elapsed = now - last
                if elapsed < expected:
                    time.sleep(expected - elapsed)
                last = time.monotonic()
                # 每 ~10MB 报一次进度(避免刷屏)
                if offset - reported >= 10 * 1024 * 1024:
                    _progress(offset)
                    reported = offset
            _progress(offset)
            print()
    return dest


# ---------- 阶段 2:解压(仅 archive.org XML 源用) ----------

def extract(archive_path: Path, out_dir: Path) -> Path:
    """用 py7zr 解出 .7z,返回 Posts.xml 路径。"""
    import py7zr

    out_dir.mkdir(parents=True, exist_ok=True)
    with py7zr.SevenZipFile(archive_path, mode="r") as z:
        z.extractall(path=out_dir)
    xml = out_dir / "Posts.xml"
    if not xml.exists():
        hits = list(out_dir.rglob("Posts.xml"))
        if not hits:
            raise FileNotFoundError(f"解压后未找到 Posts.xml:{out_dir}")
        xml = hits[0]
    return xml


# ---------- 阶段 3+4+5:流式解析 + 清洗筛选 + 生成记录 ----------

def parse_posts(xml_path: Path, site: str, max_rows: int = 0) -> Iterator[PublicRecord]:
    """流式解析 Posts.xml,产出报错类 PublicRecord(问题 + 最佳答案)。"""
    from lxml import etree

    def _xml_rows() -> Iterator[dict]:
        row_count = 0
        with xml_path.open("rb") as f:
            context = etree.iterparse(f, events=("end",), tag="row")
            for _, elem in context:
                row_count += 1
                yield dict(elem.attrib)
                # 内存安全:清空已处理元素并释放兄弟节点(大 XML 必备)
                elem.clear()
                while elem.getprevious() is not None:
                    del elem.getparent()[0]
                if max_rows and row_count >= max_rows:
                    break

    yield from _records_from_posts(_xml_rows(), site)


def parse_posts_parquet(parquet_path: Path, site: str = "stackoverflow.com") -> Iterator[PublicRecord]:
    """流式读 Parquet Posts,产出报错类 PublicRecord(与 XML 版共用清洗逻辑)。

    注意:ClickHouse 的 Parquet 里所有文本列(Title/Body/Tags/ParentId…)都是 binary,
    读出来是 bytes,须先解码成 str —— 否则 `str(b'12345')` 会变成 "b'12345'",与问题的
    整数 Id 转出的 "12345" 永远不相等,导致答案匹配失败、0 条产出。
    """
    import pyarrow.parquet as pq

    pf = pq.ParquetFile(parquet_path)

    def _parquet_rows() -> Iterator[dict]:
        for batch in pf.iter_batches(batch_size=50000):
            for row in batch.to_pylist():
                yield {k: _decode_bytes(v) for k, v in row.items()}

    yield from _records_from_posts(_parquet_rows(), site)


# ---------- 分批灌库(两个源共用) ----------

def _ingest(records_iter: Iterator[PublicRecord], limit: int, batch: int) -> int:
    """把记录流分批写入公共库,返回最终记录总数。"""
    db = PublicDatabase()
    records: list[PublicRecord] = []
    written = 0

    def flush() -> None:
        nonlocal written
        if not records:
            return
        total = db.write_from_crawler(records)
        written += len(records)
        print(f"      已写入 {written} 条(公共库现 {total} 条)")
        records.clear()

    for rec in records_iter:
        records.append(rec)
        if limit and written + len(records) >= limit:
            flush()
            break
        if len(records) >= batch:
            flush()
    flush()
    print(f"完成,公共库共 {db.count()} 条")
    return db.count()


def source_to_url(source: str) -> str:
    """把 source(`{site}/{qid}`)拼回原帖链接,用于 CC BY-SA 署名核对。"""
    if "/" not in source:
        return ""
    site, qid = source.split("/", 1)
    return f"https://{site}/questions/{qid}"


# ---------- 主流程 ----------

def build_url(site: str) -> str:
    """根据站点名拼出下载地址。site 形如 `unix.stackexchange.com`。"""
    if site.startswith("http"):
        return site
    return f"{ARCHIVE_BASE}/{site}.7z"


def run(site: str, url: str | None = None, limit: int = 200000,
        max_rows: int = 0, raw_dir: Path = RAW_DIR, batch: int = BATCH_SIZE) -> int:
    """archive.org XML 源 pipeline:下载 → 解压 → 解析 → 分批灌库。"""
    url = url or build_url(site)
    raw_dir.mkdir(parents=True, exist_ok=True)
    archive_path = raw_dir / f"{site}.7z"
    xml_path = raw_dir / f"{site}" / "Posts.xml"

    if not xml_path.exists():
        if not archive_path.exists():
            print(f"[1/5] 下载 {url}")
            download(url, archive_path)
        else:
            print(f"[1/5] 已存在 {archive_path.name},跳过下载")
        print(f"[2/5] 解压 {archive_path.name}")
        xml_path = extract(archive_path, raw_dir / f"{site}")

    print(f"[3/5] 解析 {xml_path.name}")
    return _ingest(parse_posts(xml_path, site, max_rows=max_rows), limit, batch)


def run_clickhouse(year: int, limit: int = 200000,
                   raw_dir: Path = RAW_DIR, batch: int = BATCH_SIZE) -> int:
    """ClickHouse SO Parquet 源 pipeline:下载某年 Posts.parquet → 解析 → 分批灌库。"""
    site = "stackoverflow.com"
    raw_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = raw_dir / f"so-posts-{year}.parquet"

    if not parquet_path.exists():
        url = f"{CLICKHOUSE_SO_BASE}/{year}.parquet"
        print(f"[1/2] 下载 {url}")
        download(url, parquet_path)
    else:
        print(f"[1/2] 已存在 {parquet_path.name},跳过下载")

    print(f"[2/2] 解析 {parquet_path.name}")
    return _ingest(parse_posts_parquet(parquet_path, site), limit, batch)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="爬 Stack Exchange 数据灌公共库")
    parser.add_argument("--site", default="", help="站点域名,如 unix.stackexchange.com(archive.org XML 源)")
    parser.add_argument("--url", default=None, help="直接指定 .7z 下载地址(覆盖 --site)")
    parser.add_argument("--year", type=int, default=0, help="年份(ClickHouse SO Parquet 源,如 2023)")
    parser.add_argument("--limit", type=int, default=200000, help="最多灌入条数(默认 20 万)")
    parser.add_argument("--max-rows", type=int, default=0, help="最多解析行数(XML 冒烟测试用,0=不限)")
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR, help="原始数据目录")
    args = parser.parse_args(argv)

    if args.year:
        return run_clickhouse(args.year, args.limit, args.raw_dir)
    if not args.site and not args.url:
        parser.error("需指定 --year(ClickHouse SO Parquet)或 --site/--url(archive.org XML)")
    site = args.site or Path(args.url).stem
    return run(args.site, args.url, args.limit, args.max_rows, args.raw_dir)


if __name__ == "__main__":
    raise SystemExit(main())
