"""
通用确定性代码评估器模板 (Deterministic Evaluators)

核心原则：能用确定性代码（正则、集合比对、AST、行高统计）判定的客观底线问题，
绝不交给大模型评委去猜。本模块零 Token 消耗、毫秒级返回、100% 可复现。
"""

from __future__ import annotations
import re
from typing import Iterable

# 1. 草稿话与思考过程泄漏检测 (Draft / Monologue Leak)
# 常见于模型关闭 Thinking 模式或连续调用工具后，把内心独白拼进了最终正文
_DRAFT_LEAK_RE = re.compile(
    r"(?:等一下|等等[，,]|让我(?:重新|再)?(?:复算|算一下|算一遍|核对)|"
    r"这个数(?:好像)?不对|不对[，,]重新|"
    r"I'll\s+(?:verify|calculate|check|look\s+up)|Let\s+me\s+(?:check|calculate|recalculate))",
    re.IGNORECASE,
)

# 2. 开头废话铺垫与结论先行线索
_BOSE_LEAD_INS = ("本题考查", "这道题考查", "关于这个问题", "首先我们来了解")
_CONCLUSION_CUES_RE = re.compile(r"(?:答案是|选\s*[A-D]|结论[：:]|等于|=|＝|核心在于|错在|是因为)")

# 3. 引用编号提取正则（示例：匹配 §3.2.1 或 第 48 题，可按业务文档编号格式调整）
_SECTION_CITE_RE = re.compile(r"§\s*(\d+(?:\.\d+)+)")
_QUESTION_CITE_RE = re.compile(r"第\s*(\d+)\s*题")


def has_draft_leak(text: str) -> bool:
    """检测回复正文中是否泄漏了模型的内心草稿或自我纠错独白。"""
    return bool(_DRAFT_LEAK_RE.search(text or ""))


def check_fabricated_citations(
    reply_text: str,
    seen_section_ids: Iterable[str],
    seen_question_nos: Iterable[int | str] = (),
) -> dict[str, object]:
    """
    基于运行 Trace 的“已见材料白名单”核对模型是否存在虚构引用（幻觉）。

    参数:
        reply_text: 模型最终输出的回复文本
        seen_section_ids: 本轮 Trace 中模型实际见过的全部小节编号集合（含初始注入 + 工具动态返回）
        seen_question_nos: 本轮 Trace 中模型实际见过的全部题号集合
    """
    seen_secs = {str(s).strip().lstrip("§") for s in seen_section_ids}
    seen_qs = {str(q).strip() for q in seen_question_nos}

    cited_secs = {m.group(1) for m in _SECTION_CITE_RE.finditer(reply_text or "")}
    cited_qs = {m.group(1) for m in _QUESTION_CITE_RE.finditer(reply_text or "")}

    # 允许前缀包含（例如模型看过了 3.2.1，在文中写 §3.2 或 §3.2.1 均算合法）
    def _is_sec_seen(cited: str) -> bool:
        return any(s == cited or s.startswith(f"{cited}.") or cited.startswith(f"{s}.") for s in seen_secs)

    fabricated_secs = sorted(c for c in cited_secs if not _is_sec_seen(c))
    fabricated_qs = sorted(q for q in cited_qs if q not in seen_qs)

    has_fabrication = bool(fabricated_secs or fabricated_qs)
    return {
        "fabricated_citation": float(has_fabrication),
        "cited_sections": sorted(cited_secs),
        "fabricated_sections": fabricated_secs,
        "fabricated_questions": fabricated_qs,
    }


def readability_scores(
    text: str,
    *,
    max_para_lines: int = 6,
    line_char_width: int = 34,
    require_analogy: bool = False,
) -> dict[str, float | None]:
    """
    评估通俗化与排版可读性（无需调用 LLM 评委）：
    - conclusion_first: 第一段是否不说套话、直接给结论
    - para_ok: 最长自然段折算手机屏幕显示行数是否 <= max_para_lines
    - formula_own_line: 含等号与数字的算式是否独立成行（未嵌在超 60 字的长句里）
    - analogy_present: 是否包含具象比喻（“打个比方”）
    """
    paragraphs = [p.strip() for p in (text or "").split("\n\n") if p.strip()]
    first_para = paragraphs[0] if paragraphs else ""
    clean_first = first_para.lstrip("*#> 　")

    conclusion_first = (
        bool(clean_first)
        and not clean_first.startswith(_BOSE_LEAD_INS)
        and bool(_CONCLUSION_CUES_RE.search(clean_first))
    )

    def _est_lines(para: str) -> int:
        return sum(max(1, (len(ln) + line_char_width - 1) // line_char_width) for ln in para.splitlines())

    max_lines = max((_est_lines(p) for p in paragraphs), default=0)

    eq_lines = [
        ln for ln in (text or "").splitlines()
        if re.search(r"\d.*[=＝]|[=＝].*\d", ln) and not ln.lstrip().startswith(("|", "$$", "```"))
    ]
    embedded_eq = [ln for ln in eq_lines if len(ln) > 60 and re.search(r"[，。；,]", ln)]

    scores: dict[str, float | None] = {
        "conclusion_first": float(conclusion_first),
        "para_ok": float(max_lines <= max_para_lines),
        "formula_own_line": (float(not embedded_eq) if eq_lines else None),
        "draft_leak": float(has_draft_leak(text)),
    }
    if require_analogy:
        scores["analogy_present"] = float("打个比方" in (text or ""))
    return scores


def derive_judge_pass(
    scores: dict[str, int],
    issues: list[dict[str, str]],
    *,
    primary_dims: tuple[str, ...] = ("correctness", "grounded"),
    primary_min: int = 4,
    secondary_min: int = 3,
) -> bool:
    """
    分数由评委给，最终 Pass/Fail 由代码算（一律忽略评委自报的 verdict）：
    1. 只要 issues 里存在任何 severity == "error" 的条目，直接判 Fail
    2. 核心维度（如 correctness, grounded）必须 >= 4 分
    3. 其余维度必须 >= 3 分
    """
    if any(item.get("severity") == "error" for item in issues):
        return False
    for dim, val in scores.items():
        threshold = primary_min if dim in primary_dims else secondary_min
        if val < threshold:
            return False
    return True
