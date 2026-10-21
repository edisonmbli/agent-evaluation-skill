# 06 · 跨框架与多语言评测落地适配指南

虽然评测的核心方法论（边界切分、请求体快照、漂移守卫、确定性评估先行、评委校准）与具体语言无关，但在写代码落地时，不同 Agent 框架的钩子与拦截方式各有不同。本指南提供四大主流技术栈的具体实现范式。

---

## 一、 Python + Pydantic AI（推荐范式）

### 1. 离线确定性单测（零 Token 消耗）
使用 `agent.override(model=FunctionModel(...))` 或 `TestModel` 替换真实模型，测试工具调用循环、结构化输出校验（`output_validator` + `ModelRetry`）与异常记账：
```python
from pydantic_ai.models.function import FunctionModel, AgentInfo
from pydantic_ai.messages import ModelResponse, TextPart

async def fake_llm(messages, info: AgentInfo) -> ModelResponse:
    return ModelResponse(parts=[TextPart(content='{"steps": ["full", "miss"]}')])

with grader_agent.override(model=FunctionModel(fake_llm)):
    result = await run_grading_turn(deps=test_deps)
```

### 2. HTTP 请求体逐字节快照测试（Request Snapshot）
在底层 `httpx.AsyncClient` 注入自定义 `MockTransport`，在请求发往大模型 API 前截获完整 JSON Body 并终止真实网络发送：
```python
import httpx, json

class WireCaptureTransport(httpx.AsyncBaseTransport):
    def __init__(self):
        self.captured_payloads: list[dict] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        self.captured_payloads.append(payload)
        # 返回合法的最小 OpenAI 兼容响应以正常结束单轮调用
        return httpx.Response(200, json={
            "id": "snap-1", "object": "chat.completion", "created": 0, "model": payload.get("model", "test"),
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "OK"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}
        })

# 断言截获的 self.captured_payloads[0] 与 tests/fixtures/agent_requests/xxx.json 逐字节相等
```

### 3. 结构化输出注意事项
- DeepSeek 等模型在 Thinking 模式下不支持强制 `tool_choice`，应使用 `PromptedOutput(MyModel)` 而非默认 Tool Output
- 不要在 Pydantic 模型字段上写大段中文 `description`（会被转义成 `\uXXXX` 塞进 System Prompt，既费钱又难读）

---

## 二、 Python + LangGraph / LangChain

### 1. 节点纯函数剥离与单测
- 不要在 Graph Node 内部把“调模型”和“改状态/算分”揉成一个大函数
- 将状态转换、路由条件（`conditional_edges` 的判断函数）拆成独立的纯函数（接收 `State` 字典/Pydantic 对象，返回路由枚举或新状态增量），直接用 `pytest` 测遍所有分支

### 2. 请求体快照与漂移守卫
- 若底层使用 `ChatOpenAI` / `ChatAnthropic`，同样通过传入 `http_async_client=httpx.AsyncClient(transport=WireCaptureTransport())` 截获最终发出的 JSON 请求体（这比只检查 LangChain 的 `PromptValue` 可靠得多，因为能一并锁死 `bind_tools` 转换后的 Tool Schema）
- **漂移守卫**：确保离线评测 Runner 直接调用生产环境的 Compiled Graph（`app_graph.ainvoke(input_state, config=...)`），严禁在评测脚本里重新 `StateGraph()` 拼装子图

---

## 三、 Python + 原生 OpenAI / Anthropic SDK（自研轻量 Agent 循环）

### 1. 共享长连接与传输层拦截
- 生产环境在应用启动（如 FastAPI `lifespan`）时全局创建一次 `AsyncOpenAI(http_client=...)`，避免每轮对话重新 TLS 握手
- 快照测试直接替换该 `http_client` 的 `transport`，即可零侵入抓取 `messages`、`tools`、`response_format` 的完整快照

### 2. 工具上限与记账兜底
- 自研 `while tool_calls:` 循环时，必须显式传入 `max_turns` / `max_tool_calls` 硬上限（按实测最大值 $\times 1.3$ 标定），超限立即优雅退出并记录 `__task_error__: "tool_calls_exceeded"`
- 用 `try...finally` 块包裹流式与非流式调用，确保**成功、抛异常、或用户中途断开 SSE 连接（`CancelledError`）时，都把已消耗的 Token 写入 `usage_ledger` 账本**（防止恶意反复点“停止”绕过每日额度）

---

## 四、 TypeScript / Node.js + Vercel AI SDK (`ai`)

### 1. 离线单测与请求体快照（Vitest）
使用 `ai/test` 提供的 `MockLanguageModelV1`（或 V2），在 `doGenerate` / `doStream` 中捕获传入的 `prompt`、`mode`（含 Tools Schema）并与本地 JSON 快照比对：
```typescript
import { generateText } from 'ai';
import { MockLanguageModelV1 } from 'ai/test';
import { expect, test } from 'vitest';

test('locks agent prompt and tool schema snapshot', async () => {
  let capturedParams: any = null;
  const mockModel = new MockLanguageModelV1({
    doGenerate: async (params) => {
      capturedParams = params;
      return {
        text: 'ok',
        finishReason: 'stop',
        usage: { promptTokens: 10, completionTokens: 2 },
        rawCall: { rawPrompt: null, rawSettings: {} },
      };
    },
  });

  await runMyAgent({ model: mockModel, userId: 'u1', questionId: 'q1' });
  expect(capturedParams.prompt).toMatchFileSnapshot('./__snapshots__/agent_prompt.json');
  expect(capturedParams.mode).toMatchFileSnapshot('./__snapshots__/agent_tools.json');
});
```

### 2. 跨端契约锁死
- 若后端是 Python、前端是 TypeScript（或前后端分离），前端 Vitest 测试里的 API 响应 Fixture 必须由后端测试导出或通过 OpenAPI Schema 自动校验，严禁前后端各自手写一套同名计算函数（如掌握度、复习间隔），所有业务口径只在服务端计算一次，前端只负责缓存与展示
