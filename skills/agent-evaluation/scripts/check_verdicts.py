#!/usr/bin/env python3
"""
check_verdicts.py — LLM-as-a-Judge 判定结果防偏见与防偷懒自检器 (零第三方依赖)

核心检查项：
1. JSON 格式与必填字段校验 (scores, issues, rationale)
2. 严重度强绑定铁律 (Severity-Score Binding)：
   凡 issues 中包含 severity == "error" 的条目，其对应 dimension 的打分必须 <= 3 分（严禁老好人给 4/5 分）
3. 整批防偷懒查重：同一句 rationale 或 issue reason 若在 >= 3 份判定中重复出现，直接报错打回
4. 防水军盖章：当批次判定数 >= 20 时，若“全 5 分且无任何 issues”的比例超过 40%，直接报错拦截

用法：
    python3 scripts/check_verdicts.py --verdicts-dir evals/runs/_judge-desk/verdicts
"""

from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import sys


def validate_verdicts(
    verdicts_dir: Path,
    *,
    max_error_score: int = 3,
    max_duplicate_rationale: int = 3,
    min_batch_for_rubber_stamp_check: int = 20,
    max_all_perfect_ratio: float = 0.40,
) -> tuple[int, list[str]]:
    files = sorted(verdicts_dir.glob("*.json"))
    if not files:
        return 0, [f"未在目录中找到任何 .json 判定文件: {verdicts_dir}"]

    errors: list[str] = []
    rationales: Counter[str] = Counter()
    all_perfect_count = 0

    for fp in files:
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"[{fp.name}] JSON 解析失败: {exc}")
            continue

        if not isinstance(data, dict):
            errors.append(f"[{fp.name}] 顶层必须是 JSON 对象")
            continue

        scores = data.get("scores")
        issues = data.get("issues")
        rationale = str(data.get("rationale") or "").strip()

        if not isinstance(scores, dict) or not scores:
            errors.append(f"[{fp.name}] 缺少非空 'scores' 字典")
            continue
        if not isinstance(issues, list):
            errors.append(f"[{fp.name}] 'issues' 必须是数组")
            continue
        if len(rationale) < 10:
            errors.append(f"[{fp.name}] 'rationale' 过短或缺失（需具体说明判定依据）")
        else:
            rationales[rationale] += 1

        for dim, val in scores.items():
            if not isinstance(val, int) or not (1 <= val <= 5):
                errors.append(f"[{fp.name}] 维度 '{dim}' 分数必须是 1~5 的整数，当前为: {val!r}")

        for idx, issue in enumerate(issues):
            if not isinstance(issue, dict):
                errors.append(f"[{fp.name}] issues[{idx}] 必须是对象")
                continue
            dim = issue.get("dimension")
            sev = issue.get("severity")
            reason = str(issue.get("reason") or "").strip()
            if sev not in {"error", "minor"}:
                errors.append(
                    f"[{fp.name}] issues[{idx}] 缺少合法的 severity ('error' | 'minor')，当前为: {sev!r}"
                )
            if dim not in scores:
                errors.append(f"[{fp.name}] issues[{idx}] 的 dimension {dim!r} 不在 scores 维度中")
            elif sev == "error" and isinstance(scores[dim], int) and scores[dim] > max_error_score:
                errors.append(
                    f"[{fp.name}] 违反严重度强绑定规则：维度 '{dim}' 存在 severity='error' 的问题"
                    f"（{reason[:40]}...），得分必须 <= {max_error_score}，但当前给了 {scores[dim]} 分！"
                )

        if all(v == 5 for v in scores.values() if isinstance(v, int)) and len(issues) == 0:
            all_perfect_count += 1

    # 整批防偷懒检查 1：重复评语套模板
    for text, count in rationales.items():
        if count >= max_duplicate_rationale:
            errors.append(
                f"[BATCH CHEAT DETECTED] 同一句 rationale 在 {count} 份判定中完全重复（上限 < {max_duplicate_rationale}）："
                f"{text[:60]!r}... 请逐份独立阅读并撰写评语，严禁批量套模板！"
            )

    # 整批防偷懒检查 2：全满分水军比例过高
    total = len(files)
    if total >= min_batch_for_rubber_stamp_check:
        perfect_ratio = all_perfect_count / total
        if perfect_ratio > max_all_perfect_ratio:
            errors.append(
                f"[BATCH RUBBER-STAMP DETECTED] 批次共 {total} 份任务，其中 {all_perfect_count} 份"
                f"（{perfect_ratio:.1%}）为“全 5 分且 0 问题”，超过允许上限 {max_all_perfect_ratio:.0%}！"
            )

    return total, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="校验 LLM-as-a-Judge 判定文件格式、严重度强绑定与整批防偷懒规则")
    parser.add_argument("--verdicts-dir", type=Path, required=True, help="存放判定 .json 文件的目录路径")
    parser.add_argument("--max-error-score", type=int, default=3, help="存在 error 级问题时的最高允许得分 (默认: 3)")
    args = parser.parse_args()

    total, errors = validate_verdicts(args.verdicts_dir, max_error_score=args.max_error_score)
    if errors:
        print(f"❌ 判定自检未通过（共检查 {total} 份文件，发现 {len(errors)} 处问题）：", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    print(f"✅ All {total} verdicts passed validation ({total}/{total} 份判定合格).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
