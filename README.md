# Architec

**Incremental architecture review for AI-assisted codebases.**

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![CLI](https://img.shields.io/badge/CLI-archi-222222)](#quick-start)
[![Login](https://img.shields.io/badge/login-not_required-green)](#no-login-required)

[English](#architec) | [中文](#中文说明)

Architec is an advisory architecture analysis CLI. It helps answer one
practical question:

> Will this change make the codebase harder to maintain?

It reviews current changes by default, asks an LLM to interpret compact
selected-scope evidence, and reports architecture risks such as duplicated
logic, shadow implementations, unclear boundaries, stale structure, topology
pressure, and risky hotspots.

Architec does not make merge decisions and does not edit code. It gives
structured advice for humans and coding agents to review.

## Why Architec

LLM-assisted development can move quickly, but architecture can drift quietly.
Architec is designed to catch the kinds of issues that accumulate over time:

- repeated implementations and "same idea twice" code;
- compatibility paths that blur into canonical implementations;
- changed files crossing intended module boundaries;
- stale cleanup/archive candidates;
- high-risk work landing in churn-heavy areas;
- full-project topology pressure that is easy to miss during local edits.

The default workflow is incremental-first:

```bash
archi
```

Use full review when you want the whole-project baseline:

```bash
archi --full
```

## How It Fits Together

Architec is the review layer. It uses two companion components:

| Component | Command / package | Role |
| --- | --- | --- |
| **Architec** | `archi` / `architec` | Runs architecture review, calls the LLM through llmgateway, writes advisory results under `.architec/`. |
| **Hippo** | `hippo` / `hippocampus` | Builds structural project snapshots under `.hippocampus/`: file manifests, code signatures, repository indexes, structure prompts, and metrics. |
| **llmgateway** | `llmgateway` | Owns provider credentials, base URLs, API style, model names, and strong/weak model routing. |

```text
source tree + git changes
        |
        v
Hippo structural snapshot  ->  .hippocampus/
        |
        v
Architec evidence builder  ->  selected-scope or full-project context
        |
        v
llmgateway LLM call        ->  strong / weak model tiers
        |
        v
Architec review output     ->  .architec/
```

Day-to-day `archi` runs still use the LLM, but they avoid refreshing the whole
Hippo snapshot unless requested. `archi --full` uses the Hippo snapshot more
heavily, and `archi --refresh-from-hippo --full` refreshes it before review.

## How It Works

Architec combines deterministic code signals with LLM interpretation. The
deterministic layer keeps the review grounded in concrete evidence; the LLM
layer turns that evidence into readable architecture advice.

1. **Select scope**
   - `archi` reads the current git changes and focuses on changed files.
   - `archi --full` reviews the whole project.

2. **Read structural context**
   - Hippo produces `.hippocampus/` snapshots: file manifests, code signatures,
     repository indexes, metrics, and structure prompts.
   - Architec checks whether that snapshot is present, stale, or unknown.

3. **Build architecture evidence**
   - Architec runs static scanners for duplicated logic, shadow
     implementations, import-boundary pressure, cleanup/archive candidates,
     hotspots, topology pressure, and snapshot freshness.
   - Incremental review keeps selected-change concerns separate from broader
     project context so small diffs are not drowned by global noise.

4. **Ask the LLM for interpretation**
   - Architec sends compact evidence to llmgateway.
   - llmgateway chooses the configured strong or weak model tier and owns all
     provider credentials.

5. **Write advisory output**
   - Architec ranks concerns, keeps raw artifacts for inspection, and writes
     human-readable plus machine-readable output under `.architec/`.
   - The result is advice, not an automatic merge decision or proof of runtime
     correctness.

## Install

Architec requires Python 3.11+.

Recommended install from GitHub:

```bash
python3 -m pip install --user "architec @ git+https://github.com/bfly123/architec.git"
```

This installs:

- `archi`, the Architec CLI;
- `llmgateway`, the LLM provider gateway;
- `hippocampus`, the package that provides Hippo structural snapshots.

Packaged release installer:

```bash
curl -fsSL https://www.architec.top/downloads/latest/install_prod.sh -o install_prod.sh
bash install_prod.sh
```

Local development from this repository:

```bash
python3 -m pip install -e .
```

## Configure LLM Access

Architec gets all LLM access through **llmgateway**. Configure provider
credentials and model tiers in:

```text
~/.llmgateway/config.yaml
```

Minimal example:

```yaml
version: 1
provider:
  provider_type: openai
  api_style: openai_responses
  base_url: https://your-llm-endpoint/v1
  api_key: sk-...
settings:
  strong_model: your-strong-model
  weak_model: your-fast-model
```

Architec consumes the configured `strong_model` and `weak_model` tiers. It does
not store model-provider credentials itself.

Check the installation and LLM route:

```bash
archi --check .
```

If the check reports missing LLM configuration, update
`~/.llmgateway/config.yaml`.

## Quick Start

Review the current selected changes:

```bash
archi
```

Run whole-project architecture review:

```bash
archi --full
```

Save JSON output:

```bash
archi --out review.json
archi --full --out full-review.json
```

Refresh Hippo inputs before full review:

```bash
archi --refresh-from-hippo --full
```

## Command Summary

| Command | Purpose |
| --- | --- |
| `archi` | Incremental LLM architecture review for current selected changes. |
| `archi --full` | Full-project LLM architecture review. |
| `archi --out review.json` | Save incremental review JSON. |
| `archi --full --out full-review.json` | Save full-review JSON. |
| `archi --refresh-from-hippo --full` | Refresh Hippo structural inputs, then run full review. |
| `archi --check .` | Validate Hippo bundle state and llmgateway configuration. |

Advanced compatibility flags and older subcommands may still be accepted for
existing automation, but new usage should prefer the commands above.

## What Architec Reports

Architec reports advisory concerns and signals, including:

- **Duplication**: repeated logic and suspicious near-duplicates.
- **Shadow implementations**: second implementations of similar behavior.
- **Architecture contracts**: import-boundary or dependency-direction pressure.
- **Cleanup/archive candidates**: stale or legacy-looking code and docs.
- **Hotspots**: churn-heavy or structurally risky areas.
- **Topology pressure**: flat or confusing project structure.
- **Snapshot freshness**: missing, stale, or unknown Hippo context.
- **Risk context**: optional external facts attached to existing concerns.

The output is advisory. It is not a pass/fail result and is not proof of
runtime correctness.

## Outputs

Architec writes generated files under `.architec/`:

```text
.architec/
  architec-analysis.json
  architec-summary.md
  architec-viz.html
  code-review-concerns.json
  code-review-discovery.json
  review-events.jsonl
  cache/
```

Hippo writes structural inputs under `.hippocampus/`.

Start with `.architec/architec-summary.md` for the human-readable report, then
open `.architec/architec-analysis.json` for exact scores, concerns, signals,
and artifact paths.

## Agent Command Compatibility

The commands above describe the current public workflow. Some older installed
`archi` binaries may still show the previous command shape, where full review
is `archi .` and incremental review is `archi --diff .`.

Agents and automation should inspect the local binary before choosing commands:

```bash
archi --help
```

| Help output | Incremental review | Full review |
| --- | --- | --- |
| Includes `--full` | `archi` | `archi --full` |
| Lacks `--full` but includes `--diff` | `archi --diff .` | `archi .` |

## No Login Required

Architecture analysis does not require `archi login`.

Account commands such as `archi login`, `archi whoami --json`, and
`archi devices --json` may exist for portal diagnostics or release smoke tests,
but they are not part of normal Architec analysis.

## Development

Run tests:

```bash
PYTHONPATH=src python3 -m pytest -q
```

Run Architec from this checkout:

```bash
PYTHONPATH=src python3 -m architec
PYTHONPATH=src python3 -m architec --full
```

Maintenance commands:

```bash
archi update
archi uninstall
```

## More Documentation

- [Usage manual](docs/usage-manual.md)
- [Architecture stability notes](docs/advisory-review/topics/architecture-stability.md)
- [Evidence model](docs/advisory-review/topics/evidence-model.md)

---

## 中文说明

**面向 AI 辅助开发的增量架构审查 CLI。**

Architec 是一个建议型架构分析工具，核心问题是：

> 这次改动会不会让项目更难长期维护？

默认命令是：

```bash
archi
```

它会审查当前 git 变更，构建紧凑的架构证据，并通过 LLM 给出可读的架构建议。
如果需要查看整个项目的架构基线，使用：

```bash
archi --full
```

Architec 只给建议，不做合并判定，不自动修改代码，也不要求登录。

### 为什么需要 Architec

AI 辅助开发会显著加快编码速度，但也容易带来架构漂移：

- 新实现重复造轮子；
- 兼容路径和主实现混在一起；
- 小改动绕过了模块边界；
- helper 逐渐膨胀成无归属子系统；
- 陈旧代码、陈旧文档和清理候选长期堆积；
- 高风险文件在高 churn 区域继续扩张。

Architec 会把这些信号整理成结构化审查结果，帮助人类 reviewer 或 coding agent
更快判断哪些建议值得进一步检查。

### Architec、Hippo 和 llmgateway

Architec 本身是架构审查层，依赖两个运行时组件：

| 组件 | 命令 / 包 | 作用 |
| --- | --- | --- |
| **Architec** | `archi` / `architec` | 执行架构审查，通过 llmgateway 调用 LLM，并把结果写入 `.architec/`。 |
| **Hippo** | `hippo` / `hippocampus` | 生成 `.hippocampus/` 结构快照，包括文件清单、代码签名、仓库索引、结构 prompt 和指标。 |
| **llmgateway** | `llmgateway` | 管理 provider 凭据、base URL、API 风格、模型名，以及 strong/weak 模型路由。 |

```text
源码树 + git 变更
        |
        v
Hippo 结构快照       ->  .hippocampus/
        |
        v
Architec 证据构建    ->  增量范围或全项目上下文
        |
        v
llmgateway LLM 调用  ->  strong / weak 模型
        |
        v
Architec 审查输出    ->  .architec/
```

日常 `archi` 仍然会使用 LLM，但不会默认刷新完整 Hippo 快照。`archi --full`
更依赖 Hippo 的全项目结构信息；如果要先刷新结构快照，可以运行：

```bash
archi --refresh-from-hippo --full
```

### 工作原理

Architec 结合确定性代码信号和 LLM 解释：

1. **选择范围**
   - `archi` 读取当前 git 变更，聚焦 changed files。
   - `archi --full` 审查整个项目。

2. **读取结构上下文**
   - Hippo 生成 `.hippocampus/` 快照。
   - Architec 判断快照是否存在、是否陈旧、是否无法判断 freshness。

3. **构建架构证据**
   - 静态扫描重复逻辑、shadow implementation、边界压力、清理候选、热点、拓扑压力等。
   - 增量审查会把 selected-change concerns 和全局上下文分开，避免小 diff 被全局噪音淹没。

4. **交给 LLM 解释**
   - Architec 把紧凑证据发送给 llmgateway。
   - llmgateway 根据配置选择 strong 或 weak 模型，并负责 provider 凭据。

5. **输出建议**
   - Architec 对 concerns 排序，保留原始 artifacts，并生成 Markdown / JSON 输出。
   - 输出是架构建议，不是 pass/fail，也不是运行时正确性的证明。

### 安装

需要 Python 3.11+。

推荐从 GitHub 安装：

```bash
python3 -m pip install --user "architec @ git+https://github.com/bfly123/architec.git"
```

这会安装：

- `archi`：Architec CLI；
- `llmgateway`：LLM provider 网关；
- `hippocampus`：提供 Hippo 结构快照能力的包。

也可以使用发布安装器：

```bash
curl -fsSL https://www.architec.top/downloads/latest/install_prod.sh -o install_prod.sh
bash install_prod.sh
```

本地开发安装：

```bash
python3 -m pip install -e .
```

### 配置 LLM

Architec 的 LLM 调用全部通过 **llmgateway**。请在下面的文件中配置 provider
和 strong/weak 模型：

```text
~/.llmgateway/config.yaml
```

最小示例：

```yaml
version: 1
provider:
  provider_type: openai
  api_style: openai_responses
  base_url: https://your-llm-endpoint/v1
  api_key: sk-...
settings:
  strong_model: your-strong-model
  weak_model: your-fast-model
```

检查安装和 LLM 路由：

```bash
archi --check .
```

### 快速使用

审查当前变更：

```bash
archi
```

全项目架构审查：

```bash
archi --full
```

保存 JSON 输出：

```bash
archi --out review.json
archi --full --out full-review.json
```

刷新 Hippo 快照后再全量审查：

```bash
archi --refresh-from-hippo --full
```

### 命令速查

| 命令 | 用途 |
| --- | --- |
| `archi` | 对当前 selected changes 进行增量 LLM 架构审查。 |
| `archi --full` | 对整个项目进行 LLM 架构审查。 |
| `archi --out review.json` | 保存增量审查 JSON。 |
| `archi --full --out full-review.json` | 保存全量审查 JSON。 |
| `archi --refresh-from-hippo --full` | 刷新 Hippo 结构输入后运行全量审查。 |
| `archi --check .` | 检查 Hippo bundle 状态和 llmgateway 配置。 |

### 输出

Architec 写入 `.architec/`：

```text
.architec/
  architec-analysis.json
  architec-summary.md
  architec-viz.html
  code-review-concerns.json
  code-review-discovery.json
  review-events.jsonl
  cache/
```

Hippo 写入 `.hippocampus/`。

建议先读 `.architec/architec-summary.md`，需要精确字段时再看
`.architec/architec-analysis.json`。

### 无需登录

架构分析不需要 `archi login`。账号相关命令可能用于门户诊断或发布 smoke test，
但不是日常 Architec 分析流程的一部分。
