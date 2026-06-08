# Architec

**面向 AI 辅助开发代码库的增量架构审查 CLI。**

[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![CLI](https://img.shields.io/badge/CLI-archi-222222)](README.md#quick-start)
[![Login](https://img.shields.io/badge/login-not_required-green)](#无需登录)

[English](README.md) | [中文](README.zh-CN.md)

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

## 为什么需要 Architec

AI 辅助开发会显著加快编码速度，但也容易带来架构漂移：

- 新实现重复造轮子；
- 兼容路径和主实现混在一起；
- 小改动绕过了模块边界；
- helper 逐渐膨胀成无归属子系统；
- 陈旧代码、陈旧文档和清理候选长期堆积；
- 高风险文件在高 churn 区域继续扩张。

Architec 会把这些信号整理成结构化审查结果，帮助人类 reviewer 或 coding agent
更快判断哪些建议值得进一步检查。

## Architec、Hippos 和 llmgateway

Architec 本身是架构审查层，依赖两个运行时组件：

| 组件 | 命令 / 包 | 作用 |
| --- | --- | --- |
| **Architec** | `archi` / `architec` | 执行架构审查，通过 llmgateway 调用 LLM，并把结果写入 `.architec/`。 |
| **Hippos** | `hippos` / `seemseam-hippos` | 生成 `.hippos/` 结构快照，包括文件清单、代码签名、仓库索引、结构 prompt 和指标。 |
| **llmgateway** | `llmgateway` | 管理 provider 凭据、base URL、API 风格、模型名，以及 strong/weak 模型路由。 |

```text
源码树 + git 变更
        |
        v
Hippos 结构快照       ->  .hippos/
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

日常 `archi` 仍然会使用 LLM，但不会默认刷新完整 Hippos 快照。`archi --full`
更依赖 Hippos 的全项目结构信息；如果要先刷新结构快照，可以运行：

```bash
archi --refresh-from-hippos --full
```

## 工作原理

Architec 结合确定性代码信号和 LLM 解释：

1. **选择范围**
   - `archi` 读取当前 git 变更，聚焦 changed files。
   - `archi --full` 审查整个项目。

2. **读取结构上下文**
   - Hippos 生成 `.hippos/` 快照。
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

## 安装

需要 Python 3.11+。

推荐从 PyPI 安装：

```bash
python3 -m pip install --user architec
```

这会安装：

- `archi`：Architec CLI；
- `seemseam-llmgateway`：提供 LLM provider 网关能力的包；
- `seemseam-hippos`：提供 Hippos 结构快照能力的包。

运行时 import 名仍是 `llmgateway` 和 `hippos`，不需要额外配置 Python 包索引。

GitHub standalone installer：

```bash
curl -fsSL https://github.com/SeemSeam/architec/releases/latest/download/install_prod.sh -o install_prod.sh
bash install_prod.sh
```

安装器会从 `SeemSeam/architec` GitHub Releases 下载匹配当前平台的 standalone
`archi` binary，并用 release checksum 校验。它只会在
`~/.llmgateway/config.yaml` 缺失时创建模板，绝不会覆盖已有 provider 凭据。

可选的 npm binary dispatcher 安装方式：

```bash
npm install -g @seemseam/archi
```

npm 包只暴露 `archi` 命令。standalone binary 会为 Architec refresh 内部
打包 Hippos，并把 llmgateway 作为库依赖使用；普通 npm 用户不需要额外的
`hippos` 或 `llmgateway` 命令。只有需要直接使用 Hippos CLI 时，才需要单独安装
`seemseam-hippos`。
npm install 期间以及首次启动 `archi` 时，dispatcher 会在
`~/.llmgateway/config.yaml` 缺失时创建 starter config，绝不会覆盖已有
provider 配置。

## 输出语言

Architec 默认输出英文；当系统 locale 是中文时，会自动把 CLI 状态、错误和维护命令输出切换为中文。
检测顺序包括 `LC_ALL`、`LC_MESSAGES`、`LANGUAGE` 和 `LANG`，只要值以 `zh` 开头即可。

脚本或测试中可以显式覆盖：

```bash
ARCHITEC_LANG=zh archi --version
ARCHITEC_LANG=en archi --check .
```

本地开发安装：

```bash
python3 -m pip install -e .
```

## 配置 LLM

Architec 的 LLM 调用全部通过 **llmgateway**。请在下面的文件中配置 provider
和 strong/weak 模型：

```text
~/.llmgateway/config.yaml
```

公开安装器只会在该文件缺失时创建 starter template；已有
`~/.llmgateway/config.yaml` 永远不会被安装或更新流程覆盖，包括 provider
凭据。自动生成模板包含主 provider 字段、模型 tier 设置和注释形式的备用
provider 示例。备用 API 源是否生效取决于已安装的 llmgateway schema；当前
llmgateway 支持 `providers` 有序链。

请用 `archi --check .` 在分析前验证 provider 凭据。常规分析命令会在后端 LLM
配置预检找不到必需 provider、key、base URL 或模型 tier 时失败；只有预检已经通过
且后续运行时 LLM 失败时，明确传入 `--allow-static` 才会让 Architec 返回静态
code-review 信号作为降级结果。

最小示例：

```yaml
version: 1
providers:
  - provider_type: openai
    api_style: openai_chat
    base_url: https://your-llm-endpoint/v1
    api_key: sk-...
    headers: {}
    model_map: {}
settings:
  fallback_model: your-fast-model
  strong_model: your-strong-model
  weak_model: your-fast-model
  strong_reasoning_effort: high
  weak_reasoning_effort: low
```

检查安装和 LLM 路由：

```bash
archi --check .
```

## 快速使用

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

刷新 Hippos 快照后再全量审查：

```bash
archi --refresh-from-hippos --full
```

## 命令速查

| 命令 | 用途 |
| --- | --- |
| `archi` | 对当前 selected changes 进行增量 LLM 架构审查。 |
| `archi --full` | 对整个项目进行 LLM 架构审查。 |
| `archi --out review.json` | 保存增量审查 JSON。 |
| `archi --full --out full-review.json` | 保存全量审查 JSON。 |
| `archi --refresh-from-hippos --full` | 刷新 Hippos 结构输入后运行全量审查。 |
| `archi --check .` | 检查 Hippos bundle 状态和 llmgateway 配置。 |

## 输出

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

Hippos 写入 `.hippos/`。

建议先读 `.architec/architec-summary.md`，需要精确字段时再看
`.architec/architec-analysis.json`。

## Agent 命令兼容

当前公开工作流是 `archi` 和 `archi --full`。部分旧版本 `archi` 可能仍显示旧命令形态：
全量审查是 `archi .`，增量审查是 `archi --diff .`。

Agent 和自动化脚本应先检查本机命令：

```bash
archi --help
```

| Help 输出 | 增量审查 | 全量审查 |
| --- | --- | --- |
| 包含 `--full` | `archi` | `archi --full` |
| 不包含 `--full` 但包含 `--diff` | `archi --diff .` | `archi .` |

## 无需登录

架构分析不需要 `archi login`。账号相关命令可能用于诊断，但不是日常 Architec
分析流程的一部分。

## 开发

运行测试：

```bash
PYTHONPATH=src python3 -m pytest -q
```

从当前 checkout 运行 Architec：

```bash
PYTHONPATH=src python3 -m architec
PYTHONPATH=src python3 -m architec --full
```

## 更多文档

- [使用手册](docs/usage-manual.md)
- [架构稳定性说明](docs/advisory-review/topics/architecture-stability.md)
- [证据模型](docs/advisory-review/topics/evidence-model.md)
