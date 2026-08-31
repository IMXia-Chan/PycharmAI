"""把公共库按语言拆分:Python 留主库,其余语言归档到 data/archive/。

背景:
    公共库 public_db.json 最初把 Stack Overflow 各语言的报错混在一起
    (20001 条,Python 只占约 16%)。当前插件只做 Python,非 Python 记录会
    污染中文检索(命中 LaTeX/TypeScript/Go 等)。但又不能删 —— 后续要把
    「Python 报错修正」拓展到多语言,这些数据还有用。

    于是做「可逆归档」:非 Python 记录按 language 字段拆到
    data/archive/{语言}/records.json,主库 public_db.json 只保留 Python。
    未来要支持某语言,把对应 records.json 合并回 public_db.json 并重建索引即可。

用法:
    python tools/archive_non_python.py

说明:
    - 归档目录 data/archive/,每个语言一个子文件夹;language 为空(框架类/
      未识别)的归到 _other/;tags 含 python 但 language 空的漏标记录仍归 Python。
    - 拆分会删除旧的 BM25/向量索引(数据变了,索引必须重建),需随后重建。
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PUBLIC_DB = DATA_DIR / "public_db.json"
ARCHIVE_DIR = DATA_DIR / "archive"
INDEX_DIR = DATA_DIR / "index"

# language 字段里含 Windows 路径不便字符的,映射成安全目录名
_LANG_DIR = {
    "C#": "csharp",
    "C++": "cpp",
    "F#": "fsharp",
    "Objective-C": "objective-c",
    "Visual Basic": "visual-basic",
}
_OTHER = "_other"  # language 为空(框架类/未识别)的归档目录


def _dir_name(lang: str) -> str:
    if not lang:
        return _OTHER
    return _LANG_DIR.get(lang, lang.lower().replace(" ", "-"))


def _load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return data.get("records", [])


def _save(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump({"records": records}, f, ensure_ascii=False, indent=2)


def _is_python(r: dict) -> bool:
    lang = str(r.get("language") or "")
    if lang.lower() == "python":
        return True
    tags = r.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    # language 漏标但 tags 明确带 python 的,仍算 Python
    return not lang and any("python" in str(t).lower() for t in tags)


def main() -> None:
    records = _load(PUBLIC_DB)
    print(f"原始公共库 {len(records)} 条")

    python_records: list[dict] = []
    archived: dict[str, list[dict]] = defaultdict(list)

    for r in records:
        if _is_python(r):
            python_records.append(r)
        else:
            archived[_dir_name(str(r.get("language") or ""))].append(r)

    # 1) 主库只留 Python
    _save(PUBLIC_DB, python_records)
    print(f"主库 public_db.json 保留 Python: {len(python_records)} 条")

    # 2) 归档非 Python
    total = 0
    for dname in sorted(archived):
        recs = archived[dname]
        _save(ARCHIVE_DIR / dname / "records.json", recs)
        total += len(recs)
        print(f"  归档 {dname}: {len(recs)} 条")
    print(f"共归档 {total} 条 -> data/archive/")

    # 3) 归档清单
    with (ARCHIVE_DIR / "manifest.json").open("w", encoding="utf-8") as f:
        json.dump(
            {
                "note": "非 Python 记录归档。主库 public_db.json 只留 Python。"
                        "要恢复某语言:把 data/archive/{语言}/records.json 合并回 public_db.json 并重建索引。",
                "total_archived": total,
                "languages": {d: len(archived[d]) for d in sorted(archived)},
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    # 4) 删除旧索引(数据已变,数量不匹配会触发重建;主动删掉更干净,避免误用)
    for p in (INDEX_DIR / "public.pkl", INDEX_DIR / "public_vec.pkl"):
        if p.exists():
            p.unlink()
            print(f"已删除旧索引 {p.name}")
    print("完成。下一步:重建 BM25 + 向量索引(见后续命令)。")


if __name__ == "__main__":
    main()
