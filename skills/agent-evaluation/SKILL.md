---
name: agent-evaluation
description: >-
  Comprehensive architectural guide, audit framework, and step-by-step implementation
  playbook for AI Agent Evaluation (Evals), deterministic unit testing, LLM-as-a-Judge
  calibration, and production observability flywheels. Use this skill whenever the
  user wants to: (1) design or bootstrap an evaluation system from scratch for a new
  Agent, RAG, or LLM application, (2) review, audit, or enhance the testing and
  evaluation maturity of an existing codebase, (3) perform error analysis (Open/Axial
  Coding) on failure traces, (4) build golden datasets with controlled perturbations
  or reverse red-line cases, or (5) design, debias, and calibrate an LLM-as-a-Judge
  (智能体评测、构建评测体系、存量项目评测Review、误差分析、构建金标测试集、校准模型评委).
---

# Agent Evaluation (Evals) 架构设计、项目体检与落地指南

本 Skill 用于指导 AI Agent / RAG / LLM 应用的**测试与评测（Evaluation）体系建设**。无论是从零启动一个新项目的评测地基，还是对存量代码库进行深度 Review 与加固，请严格遵循以下工作流与工程纪律。

---

## 0. 十条核心评测工程铁律（Core Tenets）

在给出任何建议或编写代码前，始终以这十条原则作为判断基准：

1. **代码定流程，模型做判断**：凡是有确定性答案、算术加权、状态流转或用户已通过 UI 按钮明确表达意图的事，一律剥离进纯函数并用传统单元测试（`pytest` / `vitest`）锁死；绝不把确定性逻辑塞进 Prompt 让模型包办
2. **守住模型大门前的最后一米**：在不调真实大模型的前提下，必须用代码单测锁死发给模型的组装层（HTTP 请求体逐字节快照比对 Request Snapshot、拦截逻辑的零调用反向断言、评测入口与生产接口的参数漂移守卫 Drift Guards）
3. **先看数据做误差分析，别急着调参**：指标不佳时，先打开 20~50 条真实失败 Trace 做 Open Coding（写具体现象备忘）和 Axial Coding（归纳业务专属故障标签），找准根因再动手
4. **好用例靠“受控扰动”与“反向红线”**：拒绝满屏简单的 Happy Path；主观判分/生成类用例按“全对 / 部分对 / 全错”做受控扰动（Perturbation），安全与记忆类功能必须配齐要求 100% 通过的“反向用例（Reverse Cases）”
5. **能用确定性规则判的，绝不劳烦模型评委**：格式校验、可读性分块、草稿话泄漏检测（`draft_leak`）、基于 Trace 已见材料白名单的虚构引用核对（`fabricated_citations`），一律用零成本代码评估器先行判定
6. **模型评委（LLM-as-a-Judge）必须异构、盲化、代码算总账**：跨家族选评委（绝不自审）；导出待评任务时剥离身份标签（全盲 ID）；Pairwise 对比按哈希确定性翻转 A/B 顺序；评委只给维度分，最终 `Pass / Fail` 由代码按规则派生，绝不采信评委自报的结论
7. **用“严重度强绑定”根治评委老好人偏见**：要求评委对每条问题标注 `"severity": "error" | "minor"`，凡标为 `error` 的维度得分必须 $\le 3$ 分（不合格），并用脚本强制拦截“嘴上指出事实错误、手下仍给 4 分及格”的判定
8. **考官本身也要被考（盲种子与校准）**：每批评审混入无标记的已知缺陷样本（盲种子 Sentinel Seeds，检出率 $< 80\%$ 整批作废）；上线前与人类专家/黄金参照集对齐 TPR 与 TNR
9. **数据集带指纹，基线手动晋升**：数据集计算 SHA256 内容指纹，严格遵守“先改考卷建基线（Commit 1）、再改答题比高低（Commit 2）”；基线必须经人工确认后手动 `promote` 并与代码同 Commit 提交，绝不自动刷新基线防止门槛悄悄下沉
10. **区分“致命漏洞”与“阶段性合理取舍”**：在 Review 项目时，结合团队规模与项目阶段（个人/MVP vs 成熟生产系统）给建议，不机械照搬教条

---

## 1. 意图识别与三路工作流路由（Workflow Router）

收到用户请求后，首先判断任务属于以下哪种模式，并按对应 SOP 逐步执行（**切勿一次性读取所有 Reference，仅按当前步骤指示按需读取**）：

- **Mode A：新项目从 0 到 1 奠基（Greenfield Bootstrap）** $\rightarrow$ 见 **§2**
- **Mode B：存量项目深度体检与增强（Brownfield Audit & Enhance）** $\rightarrow$ 见 **§3**
- **Mode C：专项深水区作业（Targeted Playbooks）** $\rightarrow$ 见 **§4**

---

## 2. Mode A：新项目从 0 到 1 搭建评测地基（Step-by-Step）

当用户希望为新项目（或尚无评测体系的项目）搭建 Evaluation 地基时，按以下 5 个步骤交互式推进：

### Step 1：扫描业务架构，划清“代码单测”与“模型评测”边界
1. **探测代码库**：检查项目的技术栈、Agent 定义、工具（Tools）、检索（RAG）与状态存储方式
2. **查阅指南**：读取 [01-boundary-and-unit-tests.md](./references/01-boundary-and-unit-tests.md) 与 [06-framework-adaptation.md](./references/06-framework-adaptation.md)
3. **输出边界切分方案**：
   - 列出当前混在 Prompt 或 Agent 流程中、应剥离到 `domain/` 纯函数的确定性逻辑（如算分加权、数值比对、前置护栏正则、记忆隐私清洗）
   - 为项目建立三大组装层防线：**HTTP 请求体快照测试（Request Snapshot）**、**拦截逻辑零调用反向断言**、**评测漂移守卫（Drift Guards）**
4. **验证点（Validation）**：运行项目的单元测试命令（如 `pytest` / `vitest`），确认脱机零 Token 消耗且全绿通过

### Step 2：初始化评测目录骨架、指纹锁与门禁配置
1. **查阅指南**：读取 [04-ci-gates-and-flywheel.md](./references/04-ci-gates-and-flywheel.md) 的 §1~§2
2. **搭建目录与脚手架**：
   - 创建 `evals/datasets/<suite>/`、`evals/baselines/`、`evals/reports/`、`evals/runs/`（将 `evals/runs/` 加入 `.gitignore`）
   - 参考 [thresholds.example.toml](./resources/thresholds.example.toml) 生成项目的门禁配置文件 `evals/thresholds.toml`
   - 将 [dataset_fingerprint.py](./scripts/dataset_fingerprint.py) 接入或复制到项目的评测工具目录，确保每次加载数据集时计算 SHA256 内容指纹
   - 在 `Makefile` 或 `package.json` 中配置标准入口：`eval-check`（离线校验金标与评分标准）、`eval`（支持 `SUITE=`、`QUICK=1`、`EXP=`）、`eval-promote`（手动晋升基线）
3. **验证点（Validation）**：运行 `python3 <path>/dataset_fingerprint.py` 验证指纹生成正常，运行 `eval-check` 退出码为 0

### Step 3：构造首批高区分度金标数据集（Golden Dataset）
1. **查阅指南**：读取 [02-error-analysis-and-cases.md](./references/02-error-analysis-and-cases.md)
2. **按套件设计首批用例（每个核心套件 10~20 条起步）**：
   - **客观/检索类**：优先寻找业务中已有的结构化映射（如“问题 $\rightarrow$ 知识点 $\rightarrow$ 文档章节”）零成本转化为检索金标，并补充 10~20 条跑题负例标定分数下限
   - **判分/结构化决策类**：采用**受控扰动法（Controlled Perturbation）**，按“全对（换等价解法/改措辞）、部分对（故意改错单一环节）、全错（仅给结论无过程）”三档构造，记录 `perturbation` 说明
   - **安全/护栏/记忆类**：构造**反向红线用例（Reverse Cases）**（如 Prompt 注入、隐私信息、不该触发工具的闲聊），设为 100% 必过门禁
3. **验证点（Validation）**：确认每条用例输入上下文完备、条件无歧义，且包含元数据字段（`id`, `status: draft|approved`, `reviewed_by`）

### Step 4：落地确定性评估器 + 防偏见模型评委（LLM-as-a-Judge）
1. **查阅指南**：读取 [03-llm-judge-and-calibration.md](./references/03-llm-judge-and-calibration.md)
2. **先写确定性代码评估器**：
   - 参考 [deterministic_metrics.py](./resources/deterministic_metrics.py)，优先实现格式校验、篇幅/分块可读性检查、草稿话泄漏检测（`draft_leak`）、以及基于 Trace 已见材料的虚构引用核对（`fabricated_citations`）
3. **再配模型评委与防偷懒自检器**：
   - 若存在开放生成任务（如多轮辅导、摘要、创意生成），参考 [judge_prompt_template.md](./resources/judge_prompt_template.md) 编写评委 Rubric（必须包含 `key_points` 核对清单与 `severity: "error" | "minor"` 强绑定规则）
   - 接入 [check_verdicts.py](./scripts/check_verdicts.py) 强制校验评委输出（拦截 `error` 却给 $>3$ 分、拦截重复评语套模板、拦截全满分水军）
   - 准备 5~10 条已知缺陷的**盲种子（Sentinel Seeds）**混入评审批次，并使用 [calibrate_judge.py](./scripts/calibrate_judge.py) 完成首次 TPR/TNR 校准
4. **验证点（Validation）**：对测试样例运行 `check_verdicts.py` 与 `calibrate_judge.py`，确认自检与校准计算链路畅通

### Step 5：打通可观测隔离、噪声标定与落地清单
1. **查阅指南**：读取 [04-ci-gates-and-flywheel.md](./references/04-ci-gates-and-flywheel.md) 的 §3~§5
2. **配置追踪隔离與飞轮**：
   - 参考 [tracing_guard_template.py](./resources/tracing_guard_template.py)，确保本机离线评测保留完整正文（并加三道防线严禁推上云端），线上生产追踪执行白名单脱敏与智能尾部采样（错误/慢请求/负反馈 100% 保留）
   - 参考 [eval_worklist_template.md](./resources/eval_worklist_template.md)，在项目 `docs/` 下生成一份专属的《评测与可观测日常运营手册》

---

## 3. Mode B：存量项目深度体检与增强指引（Step-by-Step）

当用户要求对一个已有项目（如当前打开的工作区）进行 Evaluation Review、诊断或改进时，按以下 4 步执行：

### Step 1：全景扫描存量代码库
在给出任何评价前，先使用搜索与读文件工具全面摸底：
1. **业务与 Agent 架构**：查看有哪些 Agent、Prompt 怎么写的、挂了哪些 Tool、是否有 RAG / Memory、状态与算分逻辑写在哪里
2. **现有测试（`tests/`）**：检查单测覆盖了什么、是否混入了真实 LLM 调用、Mock 打桩是否过于宽泛、是否有 Request Snapshot 和 Drift Guards
3. **现有评测（`evals/` 或类似目录）**：检查是否有金标数据集、样本分布如何、评估器是纯规则还是 LLM-as-a-Judge、评委 Prompt 怎么写的、是否有基线门禁与校准机制
4. **可观测与线上闭环**：检查 OTel / Phoenix / Langfuse 等埋点代码、是否有脱敏与尾部采样、是否有线上负反馈回流机制

### Step 2：对照《4 维 20 项成熟度体检表》逐项对账
读取 [05-maturity-audit-rubric.md](./references/05-maturity-audit-rubric.md)，严格对照其中的 **4 大维度（边界切分、用例质量、评委可信度、门禁与飞轮）20 个检查点** 以及 **8 大常见反模式** 进行逐项评估。

### Step 3：输出结构化、有代码证据的《评测体系诊断报告》
按照 [05-maturity-audit-rubric.md](./references/05-maturity-audit-rubric.md) 末尾规定的报告模板，向用户输出包含以下四部分的深度报告（**所有结论必须附上具体的文件路径与行号链接**）：
1. **总体成熟度画像与核心亮点**：肯定项目已经做对、做得扎实的设计
2. **阶段性合理取舍（Trade-offs）**：识别哪些看似“未覆盖”实则是契合当前团队规模/阶段的务实决策，避免过度工程化说教
3. **关键风险与漏洞清单（按 P0 致命 / P1 重要 / P2 演进分级）**：精准指出当前最可能引发线上静默退步或评测失真的隐患
4. **Step-by-Step 增强改造路线图**：为每个 P0/P1 问题提供具体到文件名、函数签名和脚本命令的改造步骤

### Step 4：与用户对齐优先级并落地改造
询问用户希望先推进哪几个改造项，确认后按 Mode A / Mode C 的具体技术规范直接编写代码并验证通过。

---

## 4. Mode C：专项深水区作业（Targeted Playbooks）

当用户仅针对某一个具体环节求助时，直接加载对应的 Reference 与工具脚本执行：

| 专项任务场景 | 必读参考手册 | 配套脚本 / 模板 |
|---|---|---|
| **C1. 对失败 Trace 做误差分析（Open/Axial Coding）** | [02-error-analysis-and-cases.md](./references/02-error-analysis-and-cases.md) (§1) | — |
| **C2. 设计高区分度金标（受控扰动 / 反向用例 / 图谱复用）** | [02-error-analysis-and-cases.md](./references/02-error-analysis-and-cases.md) (§2~§4) | [dataset_fingerprint.py](./scripts/dataset_fingerprint.py) |
| **C3. 构建或校准 LLM-as-a-Judge（防老好人 / 防偷懒 / 算 TPR&TNR）** | [03-llm-judge-and-calibration.md](./references/03-llm-judge-and-calibration.md) | [judge_prompt_template.md](./resources/judge_prompt_template.md)<br>[check_verdicts.py](./scripts/check_verdicts.py)<br>[calibrate_judge.py](./scripts/calibrate_judge.py) |
| **C4. 补齐确定性规则评估器（防草稿泄漏 / 防虚构引用 / 可读性）** | [03-llm-judge-and-calibration.md](./references/03-llm-judge-and-calibration.md) (§1) | [deterministic_metrics.py](./resources/deterministic_metrics.py) |
| **C5. 落地 HTTP 请求体快照测试与评测漂移守卫** | [01-boundary-and-unit-tests.md](./references/01-boundary-and-unit-tests.md) (§2)<br>[06-framework-adaptation.md](./references/06-framework-adaptation.md) | — |
| **C6. 标定评测噪声（$2\sigma$）、配置门禁与三层脱敏可观测** | [04-ci-gates-and-flywheel.md](./references/04-ci-gates-and-flywheel.md) | [thresholds.example.toml](./resources/thresholds.example.toml)<br>[tracing_guard_template.py](./resources/tracing_guard_template.py) |
