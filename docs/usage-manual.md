# Architec 使用手册

本文档面向第一次接入 `architec` 的使用者，覆盖安装、依赖、配置、运行方式、输出说明和常见问题。内容以当前代码实现为准。

## 1. 工具定位

`architec` 是一个只做分析、不做自动修复的架构评审 CLI。

它依赖 Hippo 先产出项目快照，再基于这些输入执行架构分析，并把结果写到项目根目录下的 `.architec/`。

输入目录：

- `.hippocampus/`

输出目录：

- `.architec/`

## 2. 运行前提

### 2.1 Python 版本

项目要求：

```bash
python3 --version
```

需要 Python `3.11` 或更高版本。

### 2.2 必要依赖

安装 `architec` 前，需要确保本机具备：

- `python3`
- `pip`
- Hippo 产物，或者可执行的 `hippo` 命令

如果你要使用 `--refresh-from-hippo`，则必须满足以下任一条件：

- `hippo` 已在 `PATH` 中
- 当前项目根目录下存在 `hippocampus/src`，可通过 `python -m hippocampus.cli` 调用

## 3. 安装

在项目根目录执行：

```bash
./install.sh
```

安装脚本会优先读取现有全局配置；只有缺项时才会要求配置以下两项：

- `architec_llm_main_url`
- `architec_llm_main_api_key`

如果当前 shell 是交互式终端，脚本会只提示输入缺失项；如果是非交互式环境，则必须提前通过环境变量传入缺失项。

安装脚本完成的动作包括：

- 执行 `python3 -m pip install -e .`
- 读取已有 LLM URL 和 API Key，或补齐缺失项
- 生成用户级全局网关配置 `~/.llmgateway/config.yaml`
- 初始化全局 `rubric.json` 和 `scoring-policy.json`
- 生成用户级 Architec 配置 `~/.architec/config.yaml`
- 安装 4 个 Codex skills 到 `~/.codex/skills`
- 安装 4 个 Claude skills 到 `~/.claude/skills`
- 执行一次后端 LLM 预检查

如果设置了 `ARCHITEC_USER_CONFIG_DIR`，则会写到该目录下的：

- `config.yaml`

非交互式安装示例：

```bash
architec_llm_main_url=https://your-llm-endpoint \
architec_llm_main_api_key=your_api_key \
./install.sh
```

安装完成后可验证命令是否可用：

```bash
architec --help
```

## 3.1 Skills

安装脚本会同步安装以下 4 个 skills：

- `archi-full`
- `archi-diff`
- `archi-goal`
- `archi-advice`

职责划分：

- `archi-full`
  全量架构分析基线，对应 `archi .`
- `archi-diff`
  基于当前 `git diff` 的增量架构分析，对应 `archi --diff .`
- `archi-goal`
  围绕具体目标的架构落点分析，对应 `archi --goal "<goal>" .`
- `archi-advice`
  结合全量分析基线，再按需叠加 `goal` 或 `diff`，形成分阶段的架构改进建议

推荐顺序：

1. 先用 `archi-full` 建立当前结构基线
2. 有活动改动时再用 `archi-diff`
3. 有明确目标时再用 `archi-goal`
4. 最后用 `archi-advice` 产出具体的改造计划

误用边界：

- 不要用 `archi-diff` 代替全量基线分析
- 不要在没有明确目标时使用 `archi-goal`
- 不要脱离 `archi-full` 单独使用 `archi-advice`

最小示例 prompt：

- `archi-full`
  "Analyze this repo's overall architecture and summarize the main structural problems."
- `archi-diff`
  "Review the current git diff from an architecture perspective."
- `archi-goal`
  "Use the goal 'stabilize service boundaries' and identify the right target components."
- `archi-advice`
  "Based on the current architecture, give me a phased architecture improvement plan."

建议输出模板：

- `archi-full`
  `Score -> Problems -> Improvements`
- `archi-diff`
  `Verdict -> Impacted Areas -> Required Changes`
- `archi-goal`
  `Goal -> Recommended Placement -> Risks -> Next Moves`
- `archi-advice`
  `Current Position -> Immediate -> Next -> Later`

## 4. LLM 配置

`architec` 的分析依赖后端 LLM。默认推荐通过安装脚本完成首次配置。

### 4.1 方式一：安装脚本自动生成全局配置

安装脚本默认会把配置写到：

- `~/.llmgateway/config.yaml`
- `~/.architec/config.yaml`

前者负责 provider / api_key / base_url / max_concurrent，以及 strong / weak 两档具体模型和推理强度；后者只负责 Architec 各任务映射到 `strong` 或 `weak` tier。

如果你希望临时改目录，可以使用 `ARCHITEC_USER_CONFIG_DIR`。

### 4.2 方式二：环境变量输入给安装脚本

最小输入方式：

```bash
export architec_llm_main_api_key=your_api_key
export architec_llm_main_url=https://your-llm-endpoint
```

然后执行：

```bash
architec --check .
```

### 4.3 方式三：手动维护配置文件

运行时默认查找：

- `~/.llmgateway/config.yaml`
- `~/.architec/config.yaml`

如果你显式在项目里放了下面这个文件，它会覆盖全局配置：

- `.architec/config.yaml`

项目内同时提供了模板文件：

- `config/config.example.yaml`
- `config/config.default.yaml`

注意：

- `config/config.default.yaml` 现在更适合作为模板参考，不建议把它当作运行时主配置位置
- 推荐把源配置和 strong / weak 具体模型维护在 `~/.llmgateway/config.yaml`
- 推荐把 Architec 任务 tier 策略维护在 `~/.architec/config.yaml`
- 只有确实需要单项目覆盖时，再使用 `.architec/config.yaml`

### 4.4 其他默认配置

除了 LLM 配置外，安装脚本还会把下面两个默认配置初始化到 `~/.architec/`：

- `~/.architec/rubric.json`
- `~/.architec/scoring-policy.json`

当前运行时对这类配置的查找顺序是：

1. 项目内 `.architec/<name>`
2. 用户目录 `~/.architec/<name>`
3. 仓库内 `config/<name>`

### 4.5 配置检查

只验证配置，不跑分析：

```bash
architec --check .
```

注意：

- 这条命令仍然要求当前项目已经具备 `.hippocampus/` 输入
- 如果你只是想验证 LLM 配置，直接运行 `./install.sh` 即可，安装脚本内部已经包含独立的 LLM 预检查

如果还想顺便刷新 Hippo 输入后再检查：

```bash
architec --refresh-from-hippo --check .
```

## 5. Hippo 输入要求

如果不使用 `--refresh-from-hippo`，项目根目录下必须已经存在以下文件：

- `.hippocampus/architect-metrics.json`
- `.hippocampus/hippocampus-index.json`
- `.hippocampus/code-signatures.json`
- `.hippocampus/structure-prompt.md`

缺少任何一个，`architec` 都会直接报错退出。

## 6. 基本命令

### 6.1 查看帮助

```bash
architec --help
```

### 6.1.1 本地授权与版本门槛

当前本地 CLI 已接入浏览器授权与版本上报链路：

- `archi login` 会把本地 CLI 版本附带到浏览器授权 URL 和后续 `auth code exchange`
- `archi status --json` 与 `archi whoami --json` 会把当前 CLI 版本带到 portal 的状态查询
- 本地租约刷新也会携带 CLI 版本，便于 portal 强制最低版本

如果 portal 配置了最低支持版本，例如 `ARCHITEC_CLOUD_CLI_MIN_VERSION=0.1.0`：

- 旧版本 CLI 会在浏览器授权页被阻止
- 即使跳过页面，`exchange` 和 `refresh` 也会被 portal 拒绝
- CLI 错误输出会优先展示 GitHub Releases 升级地址，而不是只给一个泛化的认证失败提示
- `archi status --json` 和 `archi whoami --json` 会额外返回 `action_required`、升级链接和 `recommended_upgrade_command`
- 如果你要给 skill、脚本或外部包装器消费，优先读取稳定的 `upgrade` 对象：
  `required`、`minimum_version`、`install_script_url`、`command`

### 6.2 全量分析

对整个项目做一次完整架构分析：

```bash
architec .
```

说明：

- 默认模式就是全量分析
- 会要求 Hippo 输入齐全
- 会执行后端 LLM 预检查

### 6.3 目标驱动分析

如果你希望工具围绕某个架构目标给建议，可以传入 `--goal`：

```bash
architec --goal "analyze architecture stability" .
```

适用场景：

- 功能落点分析
- 架构稳定性评估
- 边界收敛建议

### 6.4 差异分析

分析当前改动相对于工作区或指定提交范围的架构影响：

```bash
architec --diff .
```

指定比较范围：

```bash
architec --diff --base main --head HEAD .
```

注意：

- `--base` 和 `--head` 必须和 `--diff` 一起使用
- 只写 `--base` 或 `--head` 而不加 `--diff` 会直接报错

### 6.5 刷新 Hippo 输入后分析

如果你希望先重新生成 Hippo 输入，再执行分析：

```bash
architec --refresh-from-hippo .
```

这个流程会按顺序执行：

```bash
hippo init --target <root>
hippo sig-extract --target <root>
hippo index --target <root> --no-llm
hippo structure-prompt --target <root> --profile map --no-llm-enhance
python collect_repo_metrics.py --root <root> --rubric <rubric>
```

## 7. 常用组合

### 7.1 刷新输入并校验配置

```bash
architec --refresh-from-hippo --check .
```

### 7.2 刷新输入并做全量分析

```bash
architec --refresh-from-hippo .
```

### 7.3 针对某个需求做差异分析

```bash
architec --diff --goal "stabilize payment module boundaries" .
```

## 8. 参数说明

当前 CLI 支持以下参数：

| 参数 | 说明 |
| --- | --- |
| `--goal` | 分析目标或意图 |
| `--diff` | 启用增量差异分析 |
| `--base` | 差异分析的起始 git 引用 |
| `--head` | 差异分析的结束 git 引用 |
| `--component` | 预留参数，当前未参与核心分析流程 |
| `--format` | 输出格式偏好，当前接受 `json/md/html/all`，但核心流程仍会统一生成主输出文件 |
| `--refresh-from-hippo` | 先刷新 Hippo 输入，再继续后续流程 |
| `--open-browser` | 预留参数，当前不会自动打开浏览器 |
| `--check` | 只做后端 LLM 配置检查，不执行分析 |
| `--out` | 额外把 JSON 结果写到指定路径 |
| `path` | 项目根目录，默认是当前目录 `.` |

## 9. 输出文件说明

执行分析后，核心输出位于 `.architec/`：

- `.architec/architec-analysis.json`
- `.architec/architec-summary.md`
- `.architec/architec-viz.html`
- `.architec/cache/`

说明：

- `architec-analysis.json` 是最完整的结构化结果
- `architec-summary.md` 是可读性更好的 Markdown 摘要
- `architec-viz.html` 是可视化页面
- `--out <path>` 不会替代默认输出，只会额外再写一份 JSON

## 10. 结果如何理解

分析结果里主要会包含这些部分：

- `meta`: 本次分析的模式、时间、路径、diff 范围
- `bundle`: Hippo 输入是否成功加载
- `summary`: LLM 生成的摘要与结论
- `scores`: 结构分、总体分、全量分、增量分
- `hotspots`: 风险热点文件或区域
- `components`: 组件级风险视图
- `change_analysis`: 差异分析结果，仅在 `--diff` 时出现
- `feature_analysis`: 目标驱动分析结果，仅在传入 `--goal` 时出现
- `recommendations`: 优先级建议
- `artifacts`: 输出文件路径

## 11. 常见问题

### 11.1 报错：bundle missing required Hippo artifacts

原因：

- `.hippocampus/` 输入不完整

处理方式：

```bash
architec --refresh-from-hippo .
```

或者手动补齐这些 Hippo 文件：

- `.hippocampus/architect-metrics.json`
- `.hippocampus/hippocampus-index.json`
- `.hippocampus/code-signatures.json`
- `.hippocampus/structure-prompt.md`

### 11.2 报错：no backend LLM candidate configured

原因：

- `~/.llmgateway/config.yaml` 缺 provider、API 路由或 strong / weak 模型配置
- `~/.architec/config.yaml` 缺任务 tier 映射或格式无效
- 或项目覆盖文件 `.architec/config.yaml` 格式无效

处理方式：

- 检查 `~/.llmgateway/config.yaml`
- 检查 `~/.architec/config.yaml`
- 如果项目里存在 `.architec/config.yaml`，也要一起检查
- 重点确认 `settings.strong_model` 和 `settings.weak_model` 已配置
- 检查 `architec_llm_main_api_key`
- 检查 `architec_llm_main_url`
- 重新执行 `architec --check .`

### 11.3 报错：missing api_key 或 missing base_url

原因：

- LLM 提供方配置缺字段

处理方式：

- 补齐环境变量
- 或补齐 `~/.llmgateway/config.yaml` 中 provider 的 `api_key` 和 `base_url`

### 11.4 报错：Hippo CLI not found

原因：

- 执行了 `--refresh-from-hippo`，但系统找不到 `hippo`

处理方式：

- 安装 Hippo CLI 并加入 `PATH`
- 或确保项目内存在 `hippocampus/src`

## 12. 当前实现边界

以下内容在参数层面存在，但当前实现仍是保留或弱生效状态：

- `--component`：预留
- `--open-browser`：当前只生成 HTML，不自动打开
- `--format`：当前核心流程仍统一写出 JSON、Markdown、HTML 三份主结果

因此，建议优先使用这几条稳定命令：

```bash
architec --check .
architec .
architec --diff .
architec --goal "..." .
architec --refresh-from-hippo .
```
