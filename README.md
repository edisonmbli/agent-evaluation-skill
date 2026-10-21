# 🎯 agent-evaluation — AI Agent 评测基建与项目体检 Skill

> **An opinionated, battle-tested Agent Skill for building, auditing, and calibrating AI Agent Evaluation (Evals) systems.**
> 适用工具：**Google Antigravity** · **Claude Code** · **Cursor** · 以及所有兼容 `SKILL.md` 规范的 AI Coding Agent。

做 AI Agent 最让人提心吊胆的时刻，往往不是写第一版 Demo，而是**改完一段长达几千字的提示词、换了底层模型、或者升级了框架版本之后，你根本不知道系统到底是变好了，还是在某个看不见的角落悄悄变蠢了**。

`agent-evaluation` 把业界系统的 Agent Evaluation 方法论与真实生产项目淬炼出的防坑纪律，浓缩成了一套**按需渐进加载（Progressive Disclosure）**的工程化 Skill，并内置了开箱即用的自检脚本、校准计算器与代码模板。

---

## ✨ 为什么需要这个 Skill？（解决四大工程痛点）

1. **知识密度太高，做新项目时总怕漏掉关键防线**
   - 评测不是调个 SDK 那么简单，它横跨“架构职责切分 $\rightarrow$ 请求体快照 $\rightarrow$ 样本误差分析 $\rightarrow$ 受控扰动造题 $\rightarrow$ 评委防偏见与校准 $\rightarrow$ 基线门禁与线上飞轮”。这个 Skill 把全流程固化成标准 SOP，替你守住每一道卡口
2. **分不清哪些该写普通单测、哪些该上大模型评测**
   - 教你用“代码定流程、模型做判断”划清边界，并用 **HTTP 请求体逐字节快照（Request Snapshot）**、**零调用反向断言** 和 **评测漂移守卫（Drift Guards）** 守住“模型大门前的最后一米”，在零 Token 消耗下拦住 70% 的低级退步
3. **LLM-as-a-Judge 评委充当“老好人”甚至偷懒套模板**
   - 内置**“严重度强绑定（`severity: error` 对应维度必须 $\le 3$ 分）”**、**盲种子（Sentinel Seeds）混入机制**、**整批防偷懒自检脚本（`check_verdicts.py`）** 与 **Rogan-Gladen 真实通过率修正器（`calibrate_judge.py`）**，彻底治好模型评委嘴上说有错、手下给及格的毛病
4. **存量项目想加固评测，不知道从哪下手**
   - 内置 **《4 维 20 项评测成熟度体检表》** 与 **《8 大反模式排查清单》**，自动扫描你的代码库，区分“高危工程漏洞（P0/P1）”与“阶段性合理取舍”，输出带具体文件行号的改造路线图

---

## 🚀 30 秒极速安装

### 方式一：一行命令全局安装（推荐，对本机所有项目生效）
自动检测并安装到 Antigravity（`~/.gemini/config/skills/agent-evaluation`）与 Claude Code（`~/.claude/skills/agent-evaluation`）：

```bash
curl -fsSL https://raw.githubusercontent.com/edisonmbli/agent-evaluation-skill/main/install.sh | bash
```

### 方式二：安装到当前项目的 `.agents/skills/`（随仓库 Git 共享给团队）
```bash
curl -fsSL https://raw.githubusercontent.com/edisonmbli/agent-evaluation-skill/main/install.sh | bash -s -- --workspace
```

### 方式三：本地 Clone + 软链接安装（适合二次定制与同步更新）
```bash
git clone https://github.com/edisonmbli/agent-evaluation-skill.git
cd agent-evaluation-skill
./install.sh --symlink
```

> 🗑️ **卸载命令**：`./install.sh --uninstall`（或指定 `--workspace --uninstall`）

---

## 🛠️ 三大核心使用场景与触发口令

安装完成后，无需手动塞入大量文档，直接在聊天框用自然语言召唤即可：

### 场景 1：存量项目深度 Review 与加固（Mode B: Audit & Enhance）
当你接手一个已有 Agent 项目，或者想检查当前项目的测试与评测有没有漏洞时：

> 💬 **触发口令示例**：
> `请用 agent-evaluation 对当前项目做一次全面的评测成熟度体检，指出目前的亮点、阶段性合理取舍以及 P0/P1 风险点，并给出 step-by-step 增强指引。`

**Agent 将会自动执行**：
1. 扫描项目的 Agent 定义、`domain/` 逻辑、`tests/` 单测、`evals/` 数据集与可观测埋点
2. 对照 `references/05-maturity-audit-rubric.md` 的 **4 维 20 项评分卡** 与 **8 大反模式** 逐项对账
3. 输出带代码行号链接的《成熟度诊断报告》，并在你确认后逐步落地改造代码

---

### 场景 2：新项目从 0 到 1 搭建评测地基（Mode A: Greenfield Bootstrap）
当你刚启动一个新 Agent / RAG 项目，想一开始就把测试与评测地基打牢时：

> 💬 **触发口令示例**：
> `我们正在启动这个 Agent 项目，请按 agent-evaluation 的最佳实践，带我从 0 到 1 搭好单元测试边界、请求体快照测试和评测框架骨架。`

**Agent 将会分 5 步带你交互式落地**：
- **Step 1**：剥离确定性业务规则到 `domain/`，搭建 HTTP 请求体逐字节快照测试与评测漂移守卫
- **Step 2**：初始化 `evals/datasets/`、`thresholds.toml`、数据集 SHA256 指纹锁与 `Makefile` 门禁命令
- **Step 3**：运用“受控扰动法”与“反向红线法”为你生成首批高区分度种子金标（10~20 条）
- **Step 4**：挂载确定性代码评估器（防草稿话泄漏、防虚构引用）与带严重度强绑定的模型评委
- **Step 5**：配置三层可观测脱敏隔离（严防带正文的本机评测数据误推上云端）

---

### 场景 3：单项深水区急救（Mode C: Targeted Playbooks）
你也可以针对某一个具体棘手问题随时调用它的专项子模块：

- **做误差分析**：“我有 30 条线上失败的对话记录，帮我按 `agent-evaluation` 的 Open Coding 和 Axial Coding 方法归纳故障分类表，别急着调参。”
- **设计并校准模型评委**：“帮我给多轮问答设计一套防老好人偏见的 LLM-as-a-Judge 协议，并接入 `check_verdicts.py` 和 `calibrate_judge.py`。”
- **构造判分/记忆测试集**：“帮我用受控扰动法设计 10 条主观题判分金标，再为 Memory 模块设计 10 条 100% 必过的反向红线用例。”

---

## 🧭 内置的十条核心评测工程铁律

1. **代码定流程，模型做判断**：算分加权、等级映射、数值比对、意图路由全部收归纯函数单测，直接忽略模型自报的分数
2. **守住模型大门前的最后一米**：用 HTTP 请求体逐字节快照比对、拦截逻辑零调用反向断言、评测入口漂移守卫锁死组装层
3. **先看样本做误差分析，别急着调参**：先拆解真实失败样本（Open & Axial Coding），分清是上游取材缺陷、评测口径错配还是模型能力问题
4. **好用例靠“受控扰动”与“反向红线”**：正向测“全对换解法 / 部分对单步错与错误传导 / 全错无过程”，反向测“Prompt 注入 / 隐私泄露 / 乱写记忆（100% 必过）”
5. **确定性规则先行**：格式、行数、结论先行、草稿话泄漏（`draft_leak`）、基于 Trace 白名单的虚构引用（`fabricated_citations`）一律由零成本代码先判
6. **模型评委必须异构、盲化、代码算总账**：跨家族选评委；全盲文件名导出；Pairwise 哈希翻转 A/B 顺序；评委只给维度分，最终 `Pass / Fail` 由代码派生
7. **严重度强绑定治好“老好人偏见”**：每条问题必标 `severity: "error" | "minor"`，凡标 `error` 的维度得分必须 $\le 3$ 分，由脚本强制拦截
8. **考官本身也要被考**：每批混入无标记的已知缺陷盲种子（检出率 $< 80\%$ 整批作废），并与参照集对齐 TPR / TNR
9. **数据集带指纹，基线手动晋升**：SHA256 指纹锁死“先改考卷建基线（Commit 1）、再改答题比高低（Commit 2）”；基线必须手动 `promote` 并与代码同 Commit 提交
10. **算清噪声与成本账**：同配置连跑 3 次用 $\max(2\sigma, 1/N)$ 标定容差；在报告首行显式打印生效的 Thinking 模式与环境配置；用三道防线严防本机评测正文泄密上云

---

## 📂 仓库目录与独立可用脚本

本仓库内的三个 Python 脚本均基于 **Python 3 标准库（零第三方依赖）** 编写，既可由 Agent 自动调用，也可在你的 CI / 本地终端直接运行：

```text
skills/agent-evaluation/
├── SKILL.md                                  # 主控路由与三大模式 Step-by-Step SOP
├── references/                               # 6 份按需加载的深度工程手册
│   ├── 01-boundary-and-unit-tests.md         # 边界切分、请求体快照、漂移守卫与 8 种免调模型测法
│   ├── 02-error-analysis-and-cases.md        # 误差分析 SOP、受控扰动、反向红线与 5 大场景矩阵
│   ├── 03-llm-judge-and-calibration.md       # 确定性评估先行、评委防偏见、严重度强绑定与校准公式
│   ├── 04-ci-gates-and-flywheel.md           # 快慢分层、手动 Promote、2σ 容差、三层脱敏追踪与线上飞轮
│   ├── 05-maturity-audit-rubric.md           # 存量项目体检：4 维 20 项评分卡、8 大反模式与报告模板
│   └── 06-framework-adaptation.md            # Pydantic AI / LangGraph / 原生 SDK / Vercel AI SDK 适配指南
├── resources/                                # 5 份开箱即用的配置与代码模板
│   ├── thresholds.example.toml               # 门禁阈值配置模板 (含 baseline / tolerance / pinned)
│   ├── judge_prompt_template.md              # 通用模型评委 Rubric 模板 (含严重度强绑定规则)
│   ├── deterministic_metrics.py              # 确定性评估器 (草稿泄漏、白名单虚构引用核对、可读性分块)
│   ├── tracing_guard_template.py             # 本地评测防上云三道防线 + 线上白名单脱敏与尾部采样
│   └── eval_worklist_template.md             # 精简版《Agent 评测全流程落地工作单》
└── scripts/                                  # 3 个零依赖命令行工具脚本
    ├── check_verdicts.py                     # 评委输出自检器 (查 error<=3 强绑定、查重复评语、防水军)
    ├── calibrate_judge.py                    # 评委校准与 Rogan-Gladen 真实通过率无偏修正计算器
    └── dataset_fingerprint.py                # 数据集 SHA256 内容指纹计算器 (忽略审核状态元数据)
```

### 命令行脚本快速示例

```bash
# 1. 计算评测数据集的 SHA256 内容指纹（忽略 status/reviewed_by 等元数据）
python3 skills/agent-evaluation/scripts/dataset_fingerprint.py evals/datasets/grading --suite-name my.grading

# 2. 校验模型评委输出的判定文件（拦截“指出 error 却给 4 分”与“批量复制评语”）
python3 skills/agent-evaluation/scripts/check_verdicts.py --verdicts-dir evals/runs/_judge-desk/verdicts

# 3. 计算评委校准一致率 (TPR/TNR) 并用 Rogan-Gladen 公式修正全量表面通过率
python3 skills/agent-evaluation/scripts/calibrate_judge.py --tpr 0.92 --tnr 0.88 --observed-pass-rate 0.80 --n-eval 100
```

---

## 🙏 致敬与参考资料（Credits & References）

本 Skill 的方法论提炼自以下业界一线研究与实战经验，特此致敬：
- **Hamel Husain & Shreya Shankar** — *Application-Centric AI Evals for Engineers and Technical Product Managers* ( Maven 课程与系列笔记：Error Analysis、Open/Axial Coding、Binary Judges、Rogan-Gladen 校准修正 )
- **Eugene Yan** — *Task-Specific LLM Evals that Do & Don't Work* / *Evaluating LLM Evaluators (LLM-as-a-Judge)*
- **Anthropic Engineering** — *Demystifying Evals for AI Agents* (`pass@k` vs `pass^k`、Agent 分层评测设计)
- **OpenAI Cookbook** — *Evaluation Best Practices & Prompt Engineering Guide*
- **Arize Phoenix** — *OpenInference Tracing & Datasets/Experiments Best Practices*
- **CPALearning 实战项目** — 提供了无领域专家（SME）场景下的异构模型互校、盲种子防作弊、严重度强绑定规则、请求体逐字节快照以及三层可观测脱敏隔离的完整工程验证

## 📄 License

[MIT License](./LICENSE)
