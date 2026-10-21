#!/usr/bin/env python3
"""
dataset_fingerprint.py — 评测数据集 SHA256 内容指纹计算器 (零第三方依赖)

设计目的：
守住“先改考卷建基线（Commit 1）、再改答题比高低（Commit 2）”的评测纪律。
对数据集目录或文件计算确定性的 SHA256 内容指纹（如 cpa.grading@626c8eb8）：
- 自动忽略人工审核流转等不影响评测题目实质的元数据字段（status, reviewed_by, author, updated_at）
- 一旦题干、输入、参考答案或讲解要点发生任何改动，指纹立即改变，提示不可与旧考卷基线直接比较

用法：
    python3 scripts/dataset_fingerprint.py evals/datasets/grading --suite-name cpa.grading
"""

from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

# 不计入考卷实质内容的审核元数据字段（抽检状态变更不会导致基线失效）
IGNORED_META_KEYS: frozenset[str] = frozenset({
    "status",
    "reviewed_by",
    "reviewed_at",
    "author",
    "created_at",
    "updated_at",
})


def _strip_meta(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            k: _strip_meta(v)
            for k, v in sorted(obj.items())
            if k not in IGNORED_META_KEYS
        }
    if isinstance(obj, list):
        return [_strip_meta(item) for item in obj]
    return obj


def compute_fingerprint(target: Path, *, short_len: int = 8) -> tuple[str, int]:
    files = sorted(
        [target] if target.is_file() else [
            p for p in target.rglob("*")
            if p.is_file() and p.suffix.lower() in {".jsonl", ".json", ".yaml", ".yml"}
        ]
    )
    if not files:
        raise FileNotFoundError(f"未在路径下找到任何数据集文件 (.jsonl/.json/.yaml): {target}")

    hasher = hashlib.sha256()
    record_count = 0

    for fp in files:
        suffix = fp.suffix.lower()
        lines = fp.read_text(encoding="utf-8").splitlines()
        if suffix == ".jsonl":
            for raw_line in lines:
                stripped = raw_line.strip()
                if not stripped:
                    continue
                record = json.loads(stripped)
                canonical = json.dumps(_strip_meta(record), ensure_ascii=False, sort_keys=True)
                hasher.update(canonical.encode("utf-8"))
                hasher.update(b"\n")
                record_count += 1
        elif suffix == ".json":
            record = json.loads("\n".join(lines))
            canonical = json.dumps(_strip_meta(record), ensure_ascii=False, sort_keys=True)
            hasher.update(canonical.encode("utf-8"))
            record_count += len(record) if isinstance(record, list) else 1
        else:
            # 针对 YAML 文件（零第三方依赖：剔除注释与忽略行后按规范化行计算）
            for raw_line in lines:
                s = raw_line.strip()
                if not s or s.startswith("#"):
                    continue
                if any(s.startswith(f"{k}:") for k in IGNORED_META_KEYS):
                    continue
                hasher.update(s.encode("utf-8"))
                hasher.update(b"\n")
                if s.startswith("- "):
                    record_count += 1

    digest = hasher.hexdigest()[:short_len]
    return digest, record_count


def main() -> int:
    parser = argparse.ArgumentParser(description="计算评测数据集的 SHA256 内容指纹（忽略审核状态元数据）")
    parser.add_argument("path", type=Path, help="数据集文件或目录路径")
    parser.add_argument("--suite-name", type=str, default="", help="可选套件前缀名（如 cpa.grading）")
    parser.add_argument("--length", type=int, default=8, help="指纹截取长度 (默认: 8)")
    args = parser.parse_args()

    try:
        digest, count = compute_fingerprint(args.path, short_len=args.length)
    except Exception as exc:
        print(f"❌ 指纹计算失败: {exc}", file=sys.stderr)
        return 1

    tag = f"{args.suite_name}@{digest}" if args.suite_name else f"sha256:{digest}"
    print(f"{tag}  (records={count}, path={args.path})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
