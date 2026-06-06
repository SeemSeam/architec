# Architec 使用手册

本文档面向第一次接入 `architec` 的使用者，覆盖安装、依赖、配置、运行方式、输出说明和常见问题。内容以当前代码实现为准。

## 1. 工具定位

`architec` 是一个只做分析、不做自动修复的架构评审 CLI。

它依赖 Hippos 先产出项目快照，再基于这些输入执行架构分析，并把结果写到项目根目录下的 `.architec/`。

输入目录：

- `.hippos/`

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
- Hippos 产物，或者可执行的 `hippos` 命令

如果你要使用 `--refresh-from-hippos`，则必须满足以下任一条件：

- `hippos` 已在 `PATH` 中
- 当前激活的 Python 环境里已经安装 `seemseam-hippos`，可通过 `python -m hippos.cli` 调用

不再支持把项目内或同级目录中的 `hippos/src` 当作运行时回退来源。真实安装和验收必须基于已发布安装物。

## 3. 安装

普通用户请只使用发布安装器：

```bash
curl -fsSL https://github.com/SeemSeam/architec/releases/latest/download/install_prod.sh -o install_prod.sh
bash install_prod.sh
```

更多高级功能请查看 `archi --help`。

这条命令本身就是跨平台入口：

- 安装器会自动识别当前系统类型与 CPU 架构
- Linux 和 macOS 用户都应优先使用同一条默认命令
- 真正的前提不是“换一条安装命令”，而是当前 release 中已经包含对应平台的编译包
- 例如：
  - Linux x64: `archi-v<version>-linux-x64`
  - macOS arm64: `archi-v<version>-darwin-arm64`
  - Windows x64: `archi-v<version>-win32-x64.exe`

当前发布安装器会先做一次本机环境检查，并下载 GitHub Release 中匹配当前平台的 standalone binary 和 checksum：

- `curl`
- `sha256sum` / `shasum` / `openssl` 之一，用于校验 checksum

发布安装完成后，安装器会继续处理用户级配置：

- 初始化 `~/.architec/config.yaml`
- 初始化 `~/.architec/rubric.json`
- 初始化 `~/.architec/scoring-policy.json`
- 如果 `~/.llmgateway/config.yaml` 不存在，则创建一个可编辑的 starter template，后续补齐配置即可
- 如果 `~/.llmgateway/config.yaml` 已存在，安装器永远不会覆盖已有 provider 凭据

如果通过 npm 安装：

```bash
npm install -g @seemseam/archi
```

npm package 只安装 `archi` dispatcher，不暴露 `hippos` 或 `llmgateway` 命令。
dispatcher 会在 npm install/postinstall 期间以及首次 `archi` 启动时检查
`~/.llmgateway/config.yaml`：缺失才创建 starter template，已有文件保持不变。

关于安装包体积，需要提前说明一点：

- 当前发布物不是纯源码压缩包，而是独立可运行的 standalone binary
- binary 内会包含 Architec、bundled Hippos、llmgateway 运行时依赖和必要原生动态库
- 因此发布包体积会明显大于普通脚本型 CLI，这是当前发布策略下的正常现象，不代表安装器异常
- 这样做的目的，是尽量减少用户本机环境差异带来的问题，让首次安装和后续运行更稳定
- 对普通用户来说，不需要手动准备一套完全匹配的 Python 运行时再去拼装 CLI

安装完成后可验证命令是否可用：

```bash
archi --help
```

也可以检查当前 CLI 版本，以及是否有新版本可更新：

```bash
archi --version
```

### 3.0.1 更新与卸载

当前 CLI 也支持直接自维护：

更新到最新发布版本：

```bash
archi update
```

`archi update` 会尽量先检查最新发布版本；无论当前是否已经是最新版本，都会重跑公开安装器，把当前安装刷新到最新公开构建。

卸载当前安装物：

```bash
archi uninstall
```

`archi uninstall` 默认只移除安装物，会：

- 删除 `archi` launcher 和安装目录
- 删除自动同步的 Architec skills

默认不会删除本地 `~/.architec`、`~/.hippos`、`~/.hippocampus` 或
`~/.llmgateway` 配置目录，避免误删 llmgateway provider 凭据。

如果你是在非交互脚本里调用，再加：

```bash
archi uninstall --yes
```

只有确认要清理本机配置时才使用：

```bash
archi uninstall --yes --purge-config
```

## 3.1 Skills

网站安装脚本会同步安装以下 skills：

- `archi-full`
- `archi-diff`

默认同步目录：

- Codex: `~/.codex/skills`
- Claude: `~/.claude/skills`

安装器优先使用 release 自带的 `architec-skills.tar.gz` 同步 skills；只有 release
资产不可用时，才会回退到源码仓库归档。

职责划分：

- `archi-full`
  全量架构检查，对应 `archi --full`
- `archi-diff`
  增量架构检查，对应 `archi`

推荐顺序：

1. 先用 `archi-full` 查看当前结构审查结果
2. 有活动改动时再用 `archi-diff`
3. 后续修复方向由人或 agent 基于 review 输出判断，`architec` 不做规划、不做门禁、不自动修复

误用边界：

- 不要用 `archi-diff` 代替全量基线分析
- 不要继续使用 `--goal`；该参数已从 parser 移除
- 不要继续使用旧的 `archi-goal` 或 `archi-advice` skills
- 不要把 review 输出当成放行门禁或自动修复计划

最小示例 prompt：

- `archi-full`
  "Analyze this repo's overall architecture and summarize the main structural problems."
- `archi-diff`
  "Review the current git diff from an architecture perspective."

建议输出模板：

- `archi-full`
  `Summary -> Concerns -> Evidence`
- `archi-diff`
  `Summary -> New Concerns -> Evidence`

## 3.2 修改后建议测试

当你使用 `archi` 的 orchestration / modify-test 流程时，输出里的 `test_plan`
现在会同时给出两类信息：

- `commands`
  可直接复制执行的测试命令字符串
- `command_specs`
  结构化元信息，包含 `language`、`runner`、`workspace`、`tests`

这意味着你不仅能看到“要跑什么命令”，还能直接知道这条命令属于哪种语言生态、在哪个工作目录下执行，以及它覆盖了哪些测试文件。

当前支持的测试 runner 识别包括：

- Python: `pytest`
- JavaScript / TypeScript: `vitest`、`jest`，否则回退到 package test
- Go: `go test`
- Rust: `cargo test`
- Java / Kotlin: `gradle` 或 `maven`
- C / C++ / Fortran: `ctest`、`fpm test`、`meson test`、`make test`
- C#: `dotnet test`
- Ruby: `rspec` 或 `ruby -Itest`
- PHP: `phpunit`
- Dart / Flutter: `dart test` 或 `flutter test`

典型输出示例：

```json
{
  "test_plan": {
    "selected_tests": [
      "frontend/tests/app.spec.ts",
      "native/tests/solver_test.f90"
    ],
    "commands": [
      "cd /repo/frontend && npx vitest run tests/app.spec.ts",
      "cd /repo/native && ctest --output-on-failure -R solver_test"
    ],
    "command_specs": [
      {
        "language": "javascript/typescript",
        "runner": "vitest",
        "workspace": "/repo/frontend",
        "command": "cd /repo/frontend && npx vitest run tests/app.spec.ts",
        "tests": ["tests/app.spec.ts"]
      },
      {
        "language": "c/cpp/fortran",
        "runner": "ctest",
        "workspace": "/repo/native",
        "command": "cd /repo/native && ctest --output-on-failure -R solver_test",
        "tests": ["tests/solver_test.f90"]
      }
    ]
  }
}
```

需要注意：

- `archi` 现在能更稳地识别多语言测试文件，但它仍然是在“建议最合理命令”，不是保证所有项目的测试入口都完全标准化
- 对于多工作区 monorepo、定制测试脚本、私有构建包装器，仍然建议人工复核生成命令
- `command_specs` 适合后续给 skill、脚本包装器或控制面板继续消费

## 4. LLM 配置

`architec` 的分析依赖后端 LLM。默认推荐通过安装脚本完成首次配置。

### 4.1 方式一：安装脚本自动生成全局配置

安装脚本默认会把配置写到：

- `~/.llmgateway/config.yaml`
- `~/.architec/config.yaml`

前者负责 provider / api_key / base_url / max_concurrent，以及 strong / weak 两档具体模型和推理强度；后者只负责 Architec 各任务映射到 `strong` 或 `weak` tier。

安装器只会在 `~/.llmgateway/config.yaml` 缺失时创建 starter template；已有文件不会被 install/update 覆盖，即使传入了环境变量或 `--configure-llm`。starter template 包含主 provider、headers / model_map 示例、strong / weak / fallback 模型、并发和超时设置，以及注释形式的备用 provider 示例。备用 API 源是否实际生效取决于 llmgateway 当前 schema；当前 llmgateway 支持 `providers` 有序链，未取消注释的示例不会参与运行。

如果你希望临时改目录，可以使用 `ARCHITEC_USER_CONFIG_DIR`。

### 4.2 方式二：环境变量输入给安装脚本

最小输入方式：

```bash
export architec_llm_main_api_key=your_api_key
export architec_llm_main_url=https://your-llm-endpoint
```

然后执行：

```bash
archi --check .
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
archi --check .
```

注意：

- 这条命令仍然要求当前项目已经具备 `.hippos/` 输入
- 如果你只是想验证 LLM 配置，重新执行网站安装命令即可，安装流程内部已经包含独立的 LLM 预检查

如果还想顺便刷新 Hippos 输入后再检查：

```bash
archi --refresh-from-hippos --check .
```

## 5. Hippos 输入要求

如果不使用 `--refresh-from-hippos`，项目根目录下必须已经存在以下文件：

- `.hippos/architect-metrics.json`
- `.hippos/hippos-index.json`
- `.hippos/code-signatures.json`
- `.hippos/structure-prompt.md`

缺少任何一个，`archi` 都会直接报错退出。

标准 Hippos bundle 现在还会额外包含：

- `.hippos/file-manifest.json`
- `.hippos/bundle-state.json`

其中 `.hippos/bundle-state.json` 是 freshness 标准元数据；如果它存在，`archi` 会优先用它判断 `architect-metrics.json` 是否 stale。
当前 `archi .` 还会做两层轻量动态感知：

- 把工作区里的当前源码文件集合与 `.hippos/file-manifest.json` 对比；如果检测到源码文件新增或删除导致两边不一致，会自动触发 `refresh-from-hippos`
- 检查当前源码文件的 `mtime` 是否晚于 bundle 生成时间；如果检测到已有源码文件被更新，也会自动触发 `refresh-from-hippos`

## 6. 基本命令

### 6.1 查看帮助

```bash
archi --help
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

### 6.2 全量代码审查

对整个项目做一次建议型代码结构审查：

```bash
archi .
```

等价的显式新入口：

```bash
archi code-review --full .
```

说明：

- 默认顶层模式就是全量 code-review
- 会要求 Hippos 输入齐全
- 会执行后端 LLM 预检查
- 如果使用 `--out <path>`，写出的 JSON 是 CodeReviewResult，不再是旧 analysis result

### 6.3 方案审查

如果你希望审查某个目标、重构方向或实施方案，先写成 Markdown plan：

````markdown
# Plan

## Intent
Stabilize service boundaries.

## Changes
```yaml
changes:
  - action: update
    path: src/service/boundary.py
    intent: clarify service ownership
dependencies:
  - source: src/api/**
    imports:
      - app.service.facade
```
````

然后运行：

```bash
archi plan-review plan.md
```

`--goal` 已从 parser 移除。请把目标、重构方向或实施方案写成 Markdown plan，并运行 `archi plan-review <plan.md>`。

### 6.4 cleanup / archive signals

`archi cleanup` parser 已移除，当前不再作为 live workflow 使用。cleanup 与 archive 信息已进入全量 code-review 的 advisory signals 和 file-level concerns。

如果你只想查看当前仓库里哪些旧结构、旧脚本、旧文档、旧配置或旧 prompt 需要关注，请运行全量建议型代码审查：

```bash
archi code-review --full . --out review.json
```

全量 code-review 会复用旧完整分析链路中的 cleanup / archive / semantic judge 数据，并在 JSON 中呈现：

- `signals[]` 中的 `cleanup`：候选数、review-required 数、owner / TTL / expires_at metadata 计数和 category 分布
- `signals[]` 中的 `archive`：archive candidate 数、ready / review tier 计数和 category 分布
- `signals[]` 中的 `semantic_judge`：语义复核状态、reviewed count 和 decision 分布
- `concerns[]` 中的 file-level cleanup concern：从 cleanup top candidates 和 archive top candidates 下沉到 `location.path`

当前 archive candidate 的含义是：

- 只覆盖适合“先归档、再决定是否删除”的非源码对象
- 当前主要来自 `obsolete_script`、`stale_doc`、`stale_config`、`stale_prompt`
- 会给出 `ready` / `review` tier，以及建议的 `archive/<path>` 归档路径

当前 semantic judge 的含义是：

- 它不是第二套扫描，而是对 top cleanup / archive candidates 的 LLM 语义复核
- 只复核有限数量的 top candidates，避免把 cleanup 变成大规模慢调用
- 当前会输出 `retire_now`、`archive_first`、`keep_active`、`review`
- 如果 semantic judge 当前不可用，对应 signal 会显示 `unavailable` 或 `skipped`

如果你希望给 cleanup candidate 补充责任人与时限 metadata，可以在 repo 根 `.architecture-rules.toml` 中增加：

```toml
[[shared.cleanup_metadata]]
glob = "docs/legacy/**"
owner = "docs-team"
ttl_days = 30

[[archi.cleanup_metadata]]
path = "docs/legacy/guide.md"
category = "stale_doc"
expires_at = "2026-05-01"
```

当前规则行为是：

- `shared.cleanup_metadata` 和 `archi.cleanup_metadata` 都只作用于 cleanup 派生数据
- 支持 `path` 或 `glob` 作为匹配条件；可选再加 `kind`、`category`
- 后匹配到的规则会覆盖前面规则的同名字段
- `expires_at` 支持 ISO 日期或时间；写入 artifact 时会额外派生 `expired`
- 这些 metadata 会透传到 cleanup inventory、archive candidate、semantic judge；historical / direct legacy API 生成的 autofix plan 也会保留这些字段

### 6.5 autofix（legacy parser removed）

`archi autofix` parser 已移除，不属于 advisory-review 的公开主流程。当前 CLI 不再输出 dry-run 计划，也不会执行自动修改。

替代流程是先保存一次 code-review JSON，再生成修复建议：

```bash
archi code-review --full . --out review.json
archi fix-advice --review review.json
```

Historical note: 旧版本曾基于 archive candidate 和 semantic judge 生成 `.architec/architec-autofix-plan.json` / `.architec/architec-autofix-summary.md`，并包含 archive-move 动作模型。该 CLI 工作流已下线；cleanup 子包 wrapper API 也已退役，低层 plan / artifact helper 仍保留。

### 6.6 差异代码审查

审查当前改动相对于工作区或指定提交范围的结构影响：

```bash
archi --diff .
```

等价的显式新入口：

```bash
archi code-review --diff .
```

如果已经保存了方案审查结果，可以把它作为增量一致性观察输入：

```bash
archi plan-review plan.md --out plan.json
archi code-review --diff --plan-review plan.json .
archi code-review --since main --plan-review plan.json .
```

`--plan-review` 读取 saved plan-review JSON，并把 `understood_plan.changes[].path` 与本次 changed files 对齐；如果 `understood_plan.dependencies[]` 使用结构化 import expectation，也会检查 selected changed Python files 是否观察到这些 import edges。输出的 `plan-diff-consistency` concerns 只表示偏离观察，不表示代码或方案哪一方正确。

指定比较范围：

```bash
archi --diff --base main --head HEAD .
```

注意：

- `--base` 和 `--head` 必须和 `--diff` 一起使用
- 只写 `--base` 或 `--head` 而不加 `--diff` 会直接报错
- 如果使用 `--out <path>`，写出的 JSON 是 `review_type: "diff"` 的 CodeReviewResult
- CodeReviewResult 的 `concern_id` 是基于 concern facts 生成的引用标识，不代表展示顺序
- diff/since code-review 使用基础 LLM preflight，不额外要求 `architect_component_scoring`
- `code-review --since <ref>` 遇到不可解析 ref/range 时返回结构化降级结果，不回退到全量审查
- `--plan-review <plan.json>` 只可用于 diff/since consistency observations；full review 不读取 plan-review JSON

### 6.7 状态快照（替代 legacy baseline）

`archi baseline` parser 已移除，当前不再作为 live workflow 使用。

如果你需要记录当前 advisory 状态，请使用：

```bash
archi status --snapshot
```

Historical note: 旧版本曾写出 `.architec/architec-baseline.json` / `.architec/architec-baseline-summary.md`，用于保存旧 analysis result 的 scores、cleanup、hotspot、topology 等快照。该 CLI 工作流已下线；`run_baseline` root public API 也已退役。

### 6.8 差异审查（替代 legacy gate）

`archi gate` parser 已移除，当前不再作为 live workflow 使用。advisory-review 不提供合并放行裁决。

如果你需要在 CI 或本地检查当前改动的架构影响，请保存 advisory diff review JSON：

```bash
archi code-review --diff . --out review.json
```

这个 JSON 是给人或 agent 阅读的建议型审查输出，不是 merge decision。

Historical note: 旧版本曾读取 `.architec/architec-baseline.json`，并写出 `.architec/architec-gate.json` / `.architec/architec-gate-summary.md`。该 CLI 工作流已下线；`run_gate` root public API 也已退役。

### 6.9 刷新 Hippos 输入后分析

如果你希望先重新生成 Hippos 输入，再执行分析：

```bash
archi --refresh-from-hippos .
```

这个流程会按顺序执行：

```bash
hippos init --target <root>
hippos sig-extract --target <root>
hippos index --target <root> --no-llm
hippos structure-prompt --target <root> --profile map --no-llm-enhance
python collect_repo_metrics.py --root <root> --rubric <rubric>
```

## 7. 常用组合

### 7.1 刷新输入并校验配置

```bash
archi --refresh-from-hippos --check .
```

### 7.2 刷新输入并做全量代码审查

```bash
archi --refresh-from-hippos .
```

### 7.3 先审查方案，再审查差异

```bash
archi plan-review plan.md --out plan.json
archi code-review --diff --plan-review plan.json .
```

### 7.4 查看 cleanup / archive signals

```bash
archi code-review --full . --out review.json
```

`archi cleanup` parser 已移除；请使用 `archi code-review --full .` 查看 cleanup/archive signals。

### 7.5 生成修复建议（替代 legacy autofix）

```bash
archi code-review --full . --out review.json
archi fix-advice --review review.json
```

如果 review JSON 不存在、不是合法 JSON，或顶层不是 object，`fix-advice` 会返回 CLI 错误；合法 review 但没有 concerns 时会输出空 suggestions。
`--for review.json` 仍作为兼容别名保留。

### 7.6 `archi autofix` parser 已移除

请使用 `archi fix-advice --review <review.json>` 生成修复建议。`--for <review.json>` 仍兼容旧脚本。

### 7.7 记录当前状态快照

```bash
archi status --snapshot
```

`archi baseline` parser 已移除；请使用 `archi status --snapshot`。

`status --trend` / `status --snapshot` 读取最近 100 条 review events。状态分数来自最近一次 full code-review event；diff / since 事件只参与趋势计数和 weakening components 观察。`fix-advice` 不写 review event。

### 7.8 保存当前 diff 的 advisory review

```bash
archi code-review --diff . --out review.json
```

`archi gate` parser 已移除；请使用 advisory `archi code-review --diff .` output。`review.json` 是建议型审查结果，不是 merge decision。

## 8. 参数说明

当前 CLI 支持以下参数：

| 参数 | 说明 |
| --- | --- |
| `--diff` | 启用增量差异分析 |
| `--base` | 差异分析的起始 git 引用 |
| `--head` | 差异分析的结束 git 引用 |
| `--plan-review` | saved plan-review JSON；仅用于 diff/since 的路径和结构化 import expectation 一致性观察 |
| `--component` | 预留参数，当前未参与核心分析流程 |
| `--format` | 输出格式偏好，当前接受 `json/md/html/all`，但核心流程仍会统一生成主输出文件 |
| `--refresh-from-hippos` | 先刷新 Hippos 输入，再继续后续流程 |
| `--open-browser` | 预留参数，当前不会自动打开浏览器 |
| `--check` | 只做后端 LLM 配置检查，不执行分析 |
| `--out` | 额外把 JSON 结果写到指定路径 |
| `path` | 项目根目录，默认是当前目录 `.` |

另外还支持这些单独命令：

- `archi plan-review <plan.md>`
  审查方案 Markdown，输出 understood plan、concerns、suggested adjustments 和 fingerprint
- `archi code-review --full|--diff|--since <ref> [path]`
  显式执行全量、当前 diff 或 since-ref 的建议型代码审查；diff/since 可加 `--plan-review <plan.json>`

## 9. 输出文件说明

执行当前公开审查或状态命令后，输出位于 `.architec/`：

- `.architec/architec-analysis.json`
- `.architec/architec-summary.md`
- `.architec/architec-viz.html`
- `.architec/cache/`

Full code-review may also write cleanup/archive/semantic-judge analysis artifacts because it reuses the full analysis path:

- `.architec/architec-cleanup-inventory.json`
- `.architec/architec-cleanup-ledger.json`
- `.architec/architec-cleanup-summary.md`
- `.architec/architec-archive-candidates.json`
- `.architec/architec-archive-summary.md`
- `.architec/architec-semantic-judge.json`
- `.architec/architec-semantic-judge-summary.md`

Historical / legacy compatibility artifacts may still exist from older runs, but current advisory CLI entries and retired wrapper public APIs do not write them:

- `.architec/architec-autofix-plan.json`
- `.architec/architec-autofix-summary.md`
- `.architec/architec-baseline.json`
- `.architec/architec-baseline-summary.md`
- `.architec/architec-gate.json`
- `.architec/architec-gate-summary.md`

说明：

- `architec-analysis.json` 是最完整的结构化结果
- `architec-summary.md` 是可读性更好的 Markdown 摘要
- `architec-viz.html` 是可视化页面
- `architec-cleanup-inventory.json` 是 cleanup 候选明细
- `architec-cleanup-ledger.json` 是 cleanup 汇总计数
- `architec-cleanup-summary.md` 是 cleanup 可读摘要
- `architec-archive-candidates.json` 是从 cleanup inventory 派生出的归档候选明细
- `architec-archive-summary.md` 是 archive candidate 的可读摘要
- `architec-semantic-judge.json` 是 LLM 对 top cleanup/archive candidates 的语义复核结果
- `architec-semantic-judge-summary.md` 是 semantic judge 的可读摘要
- `architec-autofix-plan.json` 是 historical autofix 动作计划，当前 advisory CLI 不再写出
- `architec-autofix-summary.md` 是 historical autofix 可读摘要，当前 advisory CLI 不再写出
- `architec-baseline.json` 是 historical baseline 快照，当前 advisory CLI 不再写出
- `architec-baseline-summary.md` 是 historical baseline 可读摘要，当前 advisory CLI 不再写出
- `architec-gate.json` 是 historical gate evaluation 结果，当前 advisory CLI 不再写出
- `architec-gate-summary.md` 是 historical gate 可读摘要，当前 advisory CLI 不再写出
- `--out <path>` 不会替代默认输出，只会额外再写一份 JSON
- 顶层 `archi .` / `archi --diff .` 当前写出的 `--out` JSON 是 CodeReviewResult，而不是旧 analysis result

## 10. 结果如何理解

顶层 `archi .`、`archi --diff .` 和显式 `archi code-review ...` 的 JSON 结果主要包含这些部分：

- `mode`: 固定为 `code_review`
- `review_type`: `full`、`diff` 或 `since`
- `scores`: 复用底层分析得出的分数摘要
- `summary`: 本次审查摘要
- `findings`: 当前保留的发现列表
- `signals`: cleanup、archive、semantic_judge、hotspot、topology 等信号摘要
- `evidence`: 从 concerns 下沉出的证据视图
- `concerns`: 建议关注的问题，包含 kind、level、confidence、location、evidence 和 next_steps_hint
- `artifacts`: 相关输出文件路径

旧 analysis result 仍可能出现在内部分析链路或历史产物中，主要包含这些部分：

- `meta`: 本次分析的模式、时间、路径、diff 范围
- `bundle`: Hippos 输入是否成功加载
- `summary`: LLM 生成的摘要与结论
- `scores`: 结构分、总体分、全量分、增量分
- `hotspots`: 风险热点文件或区域
- `components`: 组件级风险视图
- `cleanup`: cleanup 候选汇总，旧 analysis result 中会带上
- `archive_candidates`: 从 cleanup inventory 派生出的归档候选，只覆盖 `doc` / `config` / `prompt` / `script` 等非源码对象，并带 `ready` / `review`、`archive_path_hint`，以及可选的 `owner` / `ttl_days` / `expires_at`
- `semantic_judge`: 对 top cleanup/archive candidates 的 LLM 语义复核，当前会输出 `retire_now`、`archive_first`、`keep_active`、`review`，以及简短理由；若上游已有 cleanup metadata，会一并透传
- `autofix`: historical 字段；当前 advisory CLI 和 cleanup 子包 retired wrapper API 不再生成
- `baseline`: historical 字段；当前 advisory CLI 和 retired root public API 不再生成
- `gate`: historical 字段；当前 advisory CLI 和 retired root public API 不再生成
- `change_analysis`: 差异分析结果，仅在 `--diff` 时出现，其中包含 `retire_plan`
- `feature_analysis`: 旧目标驱动分析结果；公开 `--goal` parser 已移除，不再通过顶层命令生成
- `recommendations`: 优先级建议
- `artifacts`: 输出文件路径

## 11. 常见问题

### 11.1 报错：bundle missing required Hippos artifacts

原因：

- `.hippos/` 输入不完整

处理方式：

```bash
archi --refresh-from-hippos .
```

或者手动补齐这些 Hippos 文件：

- `.hippos/architect-metrics.json`
- `.hippos/hippos-index.json`
- `.hippos/code-signatures.json`
- `.hippos/structure-prompt.md`

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
- 重新执行 `archi --check .`

### 11.3 报错：missing api_key 或 missing base_url

原因：

- LLM 提供方配置缺字段

处理方式：

- 补齐环境变量
- 或补齐 `~/.llmgateway/config.yaml` 中 provider 的 `api_key` 和 `base_url`

### 11.4 报错：Hippos CLI not found

原因：

- 执行了 `--refresh-from-hippos`，但系统找不到 `hippos`

处理方式：

- 重新执行 GitHub Release 安装器，确保 standalone `archi` binary 内部 bundled Hippos 可用
- 或确认当前 Python 环境里已安装 `seemseam-hippos`

## 12. 当前实现边界

以下内容在参数层面存在，但当前实现仍是保留或弱生效状态：

- `--component`：预留
- `--open-browser`：当前只生成 HTML，不自动打开
- `--format`：当前核心流程仍统一写出 JSON、Markdown、HTML 三份主结果

因此，建议优先使用这几条稳定命令：

```bash
archi --check .
archi .
archi code-review --full .
archi code-review --diff .
archi plan-review plan.md
archi --diff .
archi --refresh-from-hippos .
```
