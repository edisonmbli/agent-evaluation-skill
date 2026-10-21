"""
三层可观测追踪防泄漏与尾部采样模板 (Tracing Guards & Tail Sampler)

解决两大核心工程痛点：
1. 严防本地跑离线评测时，因环境变量串台把带有题库/用户完整正文的实验数据误推上云端 APM。
2. 线上生产追踪执行严格的“属性白名单脱敏（Scrubbing）”与“智能尾部采样（Tail Sampling）”：
   报错、慢请求、关键判分、用户点踩 100% 保留，普通请求按比例采样，既省免费额度又保住排障线索。
"""

from __future__ import annotations
import hashlib
import random
from urllib.parse import urlparse

# ==============================================================================
# 1. 线上生产 Span 属性白名单（不在白名单内的属性如 Prompt 正文、回答原文一律抹除）
# ==============================================================================
ALLOWED_PROD_ATTR_KEYS: frozenset[str] = frozenset({
    "user.hash",
    "thread.id",
    "agent.name",
    "prompt.version",
    "model",
    "tokens.input",
    "tokens.cache_hit",
    "tokens.output",
    "cost.usd",
    "latency.first_token_ms",
    "tool.calls",
    "retrieval.section_ids",
    "error.code",
    "finish_reason",          # 如 'length' 代表输出被截断
    "guardrail.rule",         # 命中的前置护栏规则
    "thinking.mode",          # 'on' | 'off' | 'adaptive'
    "thinking.reason",        # 开启或关闭思考模式的触发原因
})

# 100% 强制保留的 Span 名称或事件标记
ALWAYS_KEEP_SPAN_NAMES: frozenset[str] = frozenset({
    "cpa.grading",
    "cpa.feedback_down",
    "cpa.guardrail_blocked",
})

_PROD_TRACING_ACTIVE = False
_LOCAL_EVAL_TRACING_ACTIVE = False


# ==============================================================================
# 2. 本机离线评测追踪的三道防线（严禁评测正文上云）
# ==============================================================================
def assert_safe_local_eval_endpoint(endpoint: str) -> None:
    """
    防线 1 & 3：校验离线评测的 Collector 地址必须是本机回环地址，
    且当前进程未开启生产环境追踪器。
    """
    global _LOCAL_EVAL_TRACING_ACTIVE
    if _PROD_TRACING_ACTIVE:
        raise RuntimeError(
            "[SECURITY BLOCK] 检测到当前进程已启用生产追踪，严禁在同一进程挂载离线评测追踪（防止脱敏被绕开）！"
        )

    parsed = urlparse(endpoint)
    host = (parsed.hostname or "").lower()
    if host not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError(
            f"[SECURITY BLOCK] 离线评测包含完整 Prompt 与数据正文，仅允许发送至本机 Phoenix (localhost/127.0.0.1)，"
            f"拒绝非法远程地址: {endpoint}"
        )
    _LOCAL_EVAL_TRACING_ACTIVE = True


# ==============================================================================
# 3. 线上生产白名单脱敏与尾部采样判定逻辑
# ==============================================================================
def scrub_span_attributes(raw_attrs: dict[str, object]) -> dict[str, object]:
    """只保留白名单内的结构化度量字段，抹除一切题干、用户输入与模型输出正文。"""
    return {k: v for k, v in raw_attrs.items() if k in ALLOWED_PROD_ATTR_KEYS}


def should_keep_span(
    *,
    span_name: str,
    is_error: bool,
    duration_ms: float,
    attributes: dict[str, object],
    sample_rate: float = 0.15,
    slow_threshold_ms: float = 8000.0,
    trace_id_hex: str = "",
) -> bool:
    """
    尾部采样决策（在 Span 结束时判定）：
    1. 报错 Span (StatusCode.ERROR 或带 error.code) -> 100% 保留
    2. 慢请求 (duration_ms >= slow_threshold_ms) -> 100% 保留
    3. 关键业务事件 (判分、用户点踩 👎、护栏拦截) -> 100% 保留
    4. 其余正常请求 -> 按 trace_id 哈希确定性采样 sample_rate (如 15%)
    """
    if is_error or attributes.get("error.code") is not None:
        return True
    if duration_ms >= slow_threshold_ms:
        return True
    if span_name in ALWAYS_KEEP_SPAN_NAMES:
        return True

    if sample_rate <= 0.0:
        return False
    if sample_rate >= 1.0:
        return True

    if trace_id_hex:
        bucket = int(hashlib.sha256(trace_id_hex.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF
        return bucket < sample_rate
    return random.random() < sample_rate
