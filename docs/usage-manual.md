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
- 当前激活的 Python 环境里已经安装 `hippocampus`，可通过 `python -m hippocampus.cli` 调用

不再支持把项目内或同级目录中的 `hippocampus/src` 当作运行时回退来源。真实安装和验收必须基于已发布安装物。

## 3. 安装

普通用户请只使用发布安装器：

```bash
curl -fsSL https://www.architec.top/downloads/latest/install_prod.sh -o install_prod.sh
bash install_prod.sh
```

更多高级功能请查看 `archi --help`。

这条命令本身就是跨平台入口：

- 安装器会自动识别当前系统类型与 CPU 架构
- Linux 和 macOS 用户都应优先使用同一条默认命令
- 真正的前提不是“换一条安装命令”，而是当前 release 中已经包含对应平台的编译包
- 例如：
  - Linux x86_64: `archi-linux-x86_64.tar.gz`
  - macOS arm64: `archi-macos-arm64.tar.gz`

当前发布安装器会先做一次本机环境检查，并尽量自动补齐这些系统依赖：

- `python3` 和 `pip`
- `curl`
- `git`
- `tar` 或 `unzip`

如果脚本检测到系统里缺这些依赖，会优先尝试通过常见包管理器自动安装：

- `apt-get`
- `dnf`
- `yum`
- `pacman`
- `apk`
- `brew`

如果自动安装失败，脚本会直接告诉用户下一步该手动安装什么。

当前发布安装器会自动安装以下两个开源依赖，并在安装时明确提醒用户来源：

- `hippocampus`
- `llmgateway`

优先顺序是：

- 先使用 release 中随安装器一起发布的 wheel
- 如果 release 没带 wheel，则回退到公开 Git 源

发布安装完成后，安装器会继续处理用户级配置：

- 初始化 `~/.architec/config.yaml`
- 初始化 `~/.architec/rubric.json`
- 初始化 `~/.architec/scoring-policy.json`
- 引导用户配置 `~/.llmgateway/config.yaml`

如果当前终端是交互式终端，安装器会询问是否现在配置 `llmgateway`，并提示输入：

- `provider_type`
- `api_style`
- `base_url`
- `api_key`
- `strong_model`
- `weak_model`

如果用户暂时不想输入 API 信息，也可以直接跳过。此时安装器会创建一个可编辑的
`~/.llmgateway/config.yaml` 模板，后续补齐配置即可。

关于安装包体积，需要提前说明一点：

- 当前发布包不是纯源码压缩包，而是独立可运行的编译分发包
- 发布包内会同时包含 `archi` 可执行文件、嵌入式 Python 运行时，以及首启所需的原生动态库
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

`archi uninstall` 当前默认就是深度卸载，会同时：

- 删除 `archi` launcher 和安装目录
- 删除自动同步的 Architec skills
- 删除本地 `~/.architec`、`~/.hippocampus`、`~/.llmgateway` 配置目录
- 尝试从当前 Python 环境卸载 `hippocampus` 和 `llmgateway`

如果你是在非交互脚本里调用，再加：

```bash
archi uninstall --yes
```

## 3.1 Skills

网站安装脚本会同步安装以下 4 个 skills：

- `archi-full`
- `archi-diff`
- `archi-goal`
- `archi-advice`

默认同步目录：

- Codex: `~/.codex/skills`
- Claude: `~/.claude/skills`

安装器优先使用 release 自带的 `architec-skills.tar.gz` 同步 skills；只有 release
资产不可用时，才会回退到源码仓库归档。

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

- 这条命令仍然要求当前项目已经具备 `.hippocampus/` 输入
- 如果你只是想验证 LLM 配置，重新执行网站安装命令即可，安装流程内部已经包含独立的 LLM 预检查

如果还想顺便刷新 Hippo 输入后再检查：

```bash
archi --refresh-from-hippo --check .
```

## 5. Hippo 输入要求

如果不使用 `--refresh-from-hippo`，项目根目录下必须已经存在以下文件：

- `.hippocampus/architect-metrics.json`
- `.hippocampus/hippocampus-index.json`
- `.hippocampus/code-signatures.json`
- `.hippocampus/structure-prompt.md`

缺少任何一个，`archi` 都会直接报错退出。

标准 Hippo bundle 现在还会额外包含：

- `.hippocampus/file-manifest.json`
- `.hippocampus/bundle-state.json`

其中 `.hippocampus/bundle-state.json` 是 freshness 标准元数据；如果它存在，`archi` 会优先用它判断 `architect-metrics.json` 是否 stale。
当前 `archi .` 还会做两层轻量动态感知：

- 把工作区里的当前源码文件集合与 `.hippocampus/file-manifest.json` 对比；如果检测到源码文件新增或删除导致两边不一致，会自动触发 `refresh-from-hippo`
- 检查当前源码文件的 `mtime` 是否晚于 bundle 生成时间；如果检测到已有源码文件被更新，也会自动触发 `refresh-from-hippo`

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

### 6.2 全量分析

对整个项目做一次完整架构分析：

```bash
archi .
```

说明：

- 默认模式就是全量分析
- 会要求 Hippo 输入齐全
- 会执行后端 LLM 预检查

### 6.3 目标驱动分析

如果你希望工具围绕某个架构目标给建议，可以传入 `--goal`：

```bash
archi --goal "analyze architecture stability" .
```

适用场景：

- 功能落点分析
- 架构稳定性评估
- 边界收敛建议

### 6.4 cleanup 扫描

如果你只想查看当前仓库里哪些旧结构、旧脚本、旧文档、旧配置或旧 prompt 已经应该退场，可以直接运行：

```bash
archi cleanup .
```

这个命令：

- 不依赖 Hippo 输入
- 不执行后端 LLM 预检查
- 会基于 cleanup inventory 额外派生 archive candidate 结果
- 如果 backend LLM 可用，会额外对 top cleanup candidates 运行 semantic judge；若 backend 不可用，命令会 fail-open，不阻塞 cleanup 输出
- 只写 cleanup / archive / semantic-judge 相关产物，不生成主分析 JSON / Markdown / HTML

当前 archive candidate 的含义是：

- 只覆盖适合“先归档、再决定是否删除”的非源码对象
- 当前主要来自 `obsolete_script`、`stale_doc`、`stale_config`、`stale_prompt`
- 会给出 `ready` / `review` tier，以及建议的 `archive/<path>` 归档路径

当前 semantic judge 的含义是：

- 它不是第二套扫描，而是对 top cleanup / archive candidates 的 LLM 语义复核
- 只复核有限数量的 top candidates，避免把 cleanup 变成大规模慢调用
- 当前会输出 `retire_now`、`archive_first`、`keep_active`、`review`
- `archi cleanup` 不要求你先通过 LLM preflight；如果 semantic judge 当前不可用，会写出 `unavailable` 或 `skipped` artifact

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

- `shared.cleanup_metadata` 和 `archi.cleanup_metadata` 都只作用于 `archi` cleanup 派生产物
- 支持 `path` 或 `glob` 作为匹配条件；可选再加 `kind`、`category`
- 后匹配到的规则会覆盖前面规则的同名字段
- `expires_at` 支持 ISO 日期或时间；写入 artifact 时会额外派生 `expired`
- 这些 metadata 会透传到 cleanup inventory、archive candidate、semantic judge 和 autofix plan

### 6.5 autofix

如果你希望基于 archive candidate 和 semantic judge 结果，导出一份可执行的安全修复计划，可以运行：

```bash
archi autofix .
```

默认行为是 dry-run：

- 不直接改动仓库文件
- 只生成 autofix plan / summary artifact
- 当前只把最安全的 `archive_first` 对象转成可执行动作

如果你确认要执行这些安全动作，再运行：

```bash
archi autofix --apply .
```

当前 autofix v1 的边界是：

- 只自动处理 `archive_first` 且带 `archive_path_hint` 的非源码对象
- 当前执行动作只有 `archive_move`
- `retire_now` 仍然只进计划，不会自动删改源码
- 如果 semantic judge 不可用，autofix 会 fail-open，但通常不会生成可执行动作

### 6.6 差异分析

分析当前改动相对于工作区或指定提交范围的架构影响：

```bash
archi --diff .
```

指定比较范围：

```bash
archi --diff --base main --head HEAD .
```

注意：

- `--base` 和 `--head` 必须和 `--diff` 一起使用
- 只写 `--base` 或 `--head` 而不加 `--diff` 会直接报错

### 6.7 固化 baseline

如果你希望把当前仓库的主分析结果固化为后续对比基线，可以运行：

```bash
archi baseline .
```

这个命令会：

- 走完整的 `archi .` 主分析链路
- 保留正常的主分析输出
- 额外写出 baseline 专用产物

baseline 产物包括：

- `.architec/architec-baseline.json`
- `.architec/architec-baseline-summary.md`

其中会冻结这些稳定字段：

- scores 快照
- cleanup 汇总
- top hotspots
- top risk components
- topology 摘要
- goal / diff retire plan 的计数快照

### 6.8 基于 baseline 执行 gate

如果你已经固化过 baseline，并希望检查当前仓库是否出现结构回退，可以运行：

```bash
archi gate .
```

这个命令会：

- 读取 `.architec/architec-baseline.json`
- 重新执行当前仓库的完整主分析
- 对比 baseline 与当前结果
- 生成 gate 专用产物

当前 gate 默认检查：

- `overall` 不低于 baseline
- `structure` 不低于 baseline
- `full` 不低于 baseline
- cleanup 候选总数不高于 baseline
- cleanup review-required 总数不高于 baseline
- cleanup 各 category 计数不高于 baseline

当前 gate severity 规则：

- `fallback_branch` / `legacy_impl` / `compat_layer` 回退记为 `block`
- `obsolete_script` / `stale_doc` / `stale_config` / `stale_prompt` 回退记为 `warn`
- score 回退仍然记为 `block`
- cleanup 总数回退当前记为 `warn`

gate 产物包括：

- `.architec/architec-gate.json`
- `.architec/architec-gate-summary.md`

### 6.9 刷新 Hippo 输入后分析

如果你希望先重新生成 Hippo 输入，再执行分析：

```bash
archi --refresh-from-hippo .
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
archi --refresh-from-hippo --check .
```

### 7.2 刷新输入并做全量分析

```bash
archi --refresh-from-hippo .
```

### 7.3 针对某个需求做差异分析

```bash
archi --diff --goal "stabilize payment module boundaries" .
```

### 7.4 只执行 cleanup 扫描

```bash
archi cleanup .
```

### 7.5 生成 autofix 计划

```bash
archi autofix .
```

### 7.6 执行安全 autofix

```bash
archi autofix --apply .
```

### 7.7 固化当前 baseline

```bash
archi baseline .
```

### 7.8 对当前结果执行 gate

```bash
archi gate .
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

另外还支持单独命令：

- `archi cleanup [path]`
  只执行 cleanup 扫描，输出 cleanup inventory / ledger / summary、archive candidate JSON / Markdown，以及 semantic judge JSON / Markdown
- `archi autofix [path]`
  生成 autofix plan / summary；加 `--apply` 时执行安全 archive move
- `archi baseline [path]`
  运行完整主分析并额外输出 baseline JSON / Markdown
- `archi gate [path]`
  基于已存在 baseline 执行结构回归检查，并输出 gate JSON / Markdown

## 9. 输出文件说明

执行分析后，核心输出位于 `.architec/`：

- `.architec/architec-analysis.json`
- `.architec/architec-summary.md`
- `.architec/architec-viz.html`
- `.architec/architec-cleanup-inventory.json`
- `.architec/architec-cleanup-ledger.json`
- `.architec/architec-cleanup-summary.md`
- `.architec/architec-archive-candidates.json`
- `.architec/architec-archive-summary.md`
- `.architec/architec-semantic-judge.json`
- `.architec/architec-semantic-judge-summary.md`
- `.architec/architec-autofix-plan.json`
- `.architec/architec-autofix-summary.md`
- `.architec/architec-baseline.json`
- `.architec/architec-baseline-summary.md`
- `.architec/architec-gate.json`
- `.architec/architec-gate-summary.md`
- `.architec/cache/`

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
- `architec-autofix-plan.json` 是当前可安全执行的 autofix 动作计划
- `architec-autofix-summary.md` 是 autofix 的可读摘要
- `architec-baseline.json` 是后续回归检查可复用的结构基线快照
- `architec-baseline-summary.md` 是 baseline 的可读摘要
- `architec-gate.json` 是当前结果相对 baseline 的结构门禁检查结果
- `architec-gate-summary.md` 是 gate 的可读摘要
- `--out <path>` 不会替代默认输出，只会额外再写一份 JSON

## 10. 结果如何理解

分析结果里主要会包含这些部分：

- `meta`: 本次分析的模式、时间、路径、diff 范围
- `bundle`: Hippo 输入是否成功加载
- `summary`: LLM 生成的摘要与结论
- `scores`: 结构分、总体分、全量分、增量分
- `hotspots`: 风险热点文件或区域
- `components`: 组件级风险视图
- `cleanup`: cleanup 候选汇总，`archi .` / `archi --goal` / `archi --diff` 都会带上
- `archive_candidates`: 从 cleanup inventory 派生出的归档候选，只覆盖 `doc` / `config` / `prompt` / `script` 等非源码对象，并带 `ready` / `review`、`archive_path_hint`，以及可选的 `owner` / `ttl_days` / `expires_at`
- `semantic_judge`: 对 top cleanup/archive candidates 的 LLM 语义复核，当前会输出 `retire_now`、`archive_first`、`keep_active`、`review`，以及简短理由；若上游已有 cleanup metadata，会一并透传
- `autofix`: 基于 semantic judge 派生出的安全动作计划，当前只自动处理 `archive_move`，并保留上游 metadata 便于人工验收
- `baseline`: 仅在 `archi baseline` 返回结果里额外出现，用于描述固化后的基线快照
- `gate`: 仅在 `archi gate` 返回结果里额外出现，用于描述当前结果相对 baseline 的通过/失败情况
- `change_analysis`: 差异分析结果，仅在 `--diff` 时出现，其中包含 `retire_plan`
- `feature_analysis`: 目标驱动分析结果，仅在传入 `--goal` 时出现，其中包含 `retire_plan`
- `recommendations`: 优先级建议
- `artifacts`: 输出文件路径

## 11. 常见问题

### 11.1 报错：bundle missing required Hippo artifacts

原因：

- `.hippocampus/` 输入不完整

处理方式：

```bash
archi --refresh-from-hippo .
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
- 重新执行 `archi --check .`

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

- 重新执行网站安装器，确保已安装发布版 `hippo`
- 或确认当前 Python 环境里已安装 `hippocampus`

## 12. 当前实现边界

以下内容在参数层面存在，但当前实现仍是保留或弱生效状态：

- `--component`：预留
- `--open-browser`：当前只生成 HTML，不自动打开
- `--format`：当前核心流程仍统一写出 JSON、Markdown、HTML 三份主结果

因此，建议优先使用这几条稳定命令：

```bash
archi --check .
archi .
archi cleanup .
archi --diff .
archi --goal "..." .
archi --refresh-from-hippo .
```
