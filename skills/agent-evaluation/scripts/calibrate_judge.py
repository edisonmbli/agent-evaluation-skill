#!/usr/bin/env python3
"""
calibrate_judge.py — LLM-as-a-Judge 校准计算器与真实通过率无偏修正工具 (零第三方依赖)

功能：
1. 对比人类专家/黄金参照集 (Reference) 与待测模型评委 (Judge) 的 Pass/Fail 判定，
   计算一致率 (Agreement)、真阳率 (TPR)、真阴率 (TNR) 及盲种子检出率 (Sentinel Recall)。
2. 基于校准得出的 TPR 与 TNR，使用 Rogan-Gladen 公式对全量评测集的表面通过率 p 进行偏差修正，
   输出无偏真实通过率估计值 θ_hat 与 Bootstrap 95% 置信区间。

用法 1（输入 JSONL 校准对账文件，每行含 {"id": "...", "ref_pass": true, "judge_pass": true, "is_sentinel": false}）：
    python3 scripts/calibrate_judge.py --pairs calibration_pairs.jsonl --observed-pass-rate 0.81

用法 2（直接传校准统计数计算修正后通过率）：
    python3 scripts/calibrate_judge.py --tpr 0.92 --tnr 0.88 --n-pos 25 --n-neg 25 --observed-pass-rate 0.80 --n-eval 100
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path
import random
import sys


def rogan_gladen_estimate(p_obs: float, tpr: float, tnr: float) -> float:
    """
    Rogan-Gladen 无偏估计公式：
        theta_hat = clip((p_obs + TNR - 1) / (TPR + TNR - 1), 0.0, 1.0)
    """
    denom = tpr + tnr - 1.0
    if denom <= 1e-6:
        return p_obs
    est = (p_obs + tnr - 1.0) / denom
    return max(0.0, min(1.0, est))


def bootstrap_ci(
    p_obs: float,
    n_eval: int,
    tpr: float,
    n_pos: int,
    tnr: float,
    n_neg: int,
    *,
    iterations: int = 2000,
    seed: int = 42,
) -> tuple[float, float]:
    """使用非参数/二项 Bootstrap 计算修正后通过率 theta_hat 的 95% 置信区间。"""
    rng = random.Random(seed)

    def _binom_rate(n: int, p: float) -> float:
        if n <= 0:
            return p
        hits = sum(1 for _ in range(n) if rng.random() < p)
        return hits / n

    samples: list[float] = []
    for _ in range(iterations):
        sim_tpr = _binom_rate(n_pos, tpr)
        sim_tnr = _binom_rate(n_neg, tnr)
        sim_p = _binom_rate(n_eval, p_obs)
        if sim_tpr + sim_tnr > 1.05:
            samples.append(rogan_gladen_estimate(sim_p, sim_tpr, sim_tnr))

    if not samples:
        return (0.0, 1.0)
    samples.sort()
    lo_idx = int(0.025 * len(samples))
    hi_idx = int(0.975 * len(samples))
    return samples[lo_idx], samples[min(hi_idx, len(samples) - 1)]


def load_pairs(path: Path) -> dict[str, float | int]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    sentinels = [r for r in rows if r.get("is_sentinel")]
    regulars = [r for r in rows if not r.get("is_sentinel")]

    sentinel_total = len(sentinels)
    sentinel_caught = sum(1 for r in sentinels if not bool(r.get("judge_pass")))
    sentinel_recall = (sentinel_caught / sentinel_total) if sentinel_total else 1.0

    pos = [r for r in regulars if bool(r.get("ref_pass"))]
    neg = [r for r in regulars if not bool(r.get("ref_pass"))]
    tp = sum(1 for r in pos if bool(r.get("judge_pass")))
    tn = sum(1 for r in neg if not bool(r.get("judge_pass")))

    total_reg = len(regulars)
    agree = tp + tn
    agreement = (agree / total_reg) if total_reg else 0.0
    tpr = (tp / len(pos)) if pos else 1.0
    tnr = (tn / len(neg)) if neg else 1.0

    return {
        "sentinel_total": sentinel_total,
        "sentinel_caught": sentinel_caught,
        "sentinel_recall": sentinel_recall,
        "total_regular": total_reg,
        "n_pos": len(pos),
        "n_neg": len(neg),
        "agreement": agreement,
        "tpr": tpr,
        "tnr": tnr,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="LLM-as-a-Judge 校准一致率与 Rogan-Gladen 真实得分修正器")
    parser.add_argument("--pairs", type=Path, help="校准样本对 JSONL 文件路径")
    parser.add_argument("--tpr", type=float, help="直接指定校准得出的 TPR (0~1)")
    parser.add_argument("--tnr", type=float, help="直接指定校准得出的 TNR (0~1)")
    parser.add_argument("--n-pos", type=int, default=20, help="校准集中的正样本数 (默认: 20)")
    parser.add_argument("--n-neg", type=int, default=20, help="校准集中的负样本数 (默认: 20)")
    parser.add_argument("--observed-pass-rate", type=float, help="全量评测中评委给出的表面通过率 p (0~1)")
    parser.add_argument("--n-eval", type=int, default=50, help="全量评测样本总数 (默认: 50)")
    parser.add_argument("--min-agreement", type=float, default=0.80, help="最低可接受一致率门槛 (默认: 0.80)")
    parser.add_argument("--min-sentinel-recall", type=float, default=0.80, help="最低盲种子检出率门槛 (默认: 0.80)")
    args = parser.parse_args()

    if args.pairs:
        stats = load_pairs(args.pairs)
        tpr = float(stats["tpr"])
        tnr = float(stats["tnr"])
        n_pos = int(stats["n_pos"])
        n_neg = int(stats["n_neg"])
        print("=== LLM-as-a-Judge 校准报告 ===")
        if stats["sentinel_total"] > 0:
            print(
                f"盲种子检出率 (Sentinel Recall) : {stats['sentinel_caught']}/{stats['sentinel_total']} "
                f"({stats['sentinel_recall']:.1%})"
            )
        print(
            f"参照集一致率 (Agreement Rate)  : {stats['agreement']:.1%} "
            f"(正样本 {n_pos} 条, 负样本 {n_neg} 条)"
        )
        print(f"真阳率 TPR (P(Judge=Pass|Ref=Pass)): {tpr:.3f}")
        print(f"真阴率 TNR (P(Judge=Fail|Ref=Fail)): {tnr:.3f}")

        failed = False
        if stats["sentinel_total"] > 0 and stats["sentinel_recall"] < args.min_sentinel_recall:
            print(f"❌ 告警：盲种子检出率低于 {args.min_sentinel_recall:.0%} 门槛，该评委批次不可信！", file=sys.stderr)
            failed = True
        if stats["total_regular"] > 0 and stats["agreement"] < args.min_agreement:
            print(f"❌ 告警：与参照集一致率低于 {args.min_agreement:.0%} 门槛，请优化 Rubric 或启用严重度强绑定！", file=sys.stderr)
            failed = True
    elif args.tpr is not None and args.tnr is not None:
        tpr = args.tpr
        tnr = args.tnr
        n_pos = args.n_pos
        n_neg = args.n_neg
        failed = False
        print(f"=== 使用指定校准参数: TPR={tpr:.3f}, TNR={tnr:.3f} ===")
    else:
        parser.error("请提供 --pairs 文件路径，或同时提供 --tpr 与 --tnr")
        return 2

    if args.observed_pass_rate is not None:
        p_obs = args.observed_pass_rate
        theta_hat = rogan_gladen_estimate(p_obs, tpr, tnr)
        ci_lo, ci_hi = bootstrap_ci(p_obs, args.n_eval, tpr, n_pos, tnr, n_neg)
        print("\n=== Rogan-Gladen 真实通过率修正 ===")
        print(f"评委表面通过率 (Observed p)     : {p_obs:.1%}")
        print(f"修正后真实通过率 (Corrected θ)  : {theta_hat:.1%}")
        print(f"Bootstrap 95% 置信区间 (95% CI) : [{ci_lo:.1%}, {ci_hi:.1%}]")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
