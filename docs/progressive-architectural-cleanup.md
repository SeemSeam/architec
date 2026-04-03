# Architec 持续结构净化最终方案

本文档是 `archi + hippo` 持续结构净化能力线的最终收敛版本。

目标不是继续扩写一个抽象概念文档，而是把已经确认的设计决策、职责边界、数据契约和详细实施计划固定下来，作为后续开发的正式依据。

## 1. 方案目标

这条能力线要解决四个具体问题：

- 修复 `hippo` 增量更新后，`architect-metrics.json` 可能陈旧，进而导致 `archi` 热点分析漂移的问题。
- 让 `archi` 能稳定识别应该退场的旧结构，而不仅仅是继续输出热点和评分。
- 把清理对象从单纯源码扩展到旧脚本、旧 docs、失效 config、旧 prompt。
- 在不引入过重配置系统的前提下，支持 `archi` 和 `hippo` 独立于 `.gitignore` 的分析排除策略。

## 2. 当前结论

经过现有代码和实际 bundle 的核查，当前最关键的判断如下：

- `hippo incremental index` 本身对删除文件和删除模块已有基本处理。
- 当前更大的问题不在 index cache，而在 `architect-metrics.json` 的 freshness 契约缺失。
- `archi` 的热点历史分析直接消费 metrics findings，所以 stale metrics 会导致结果漂移。
- 因此第一优先级不是继续加评分维度，而是先补齐 Hippo bundle 和 Architec metrics 之间的一致性契约。

## 3. 已确认的核心决策

### 3.1 Archi 的默认刷新策略

正式决策：

- 默认采用 `auto on stale`

具体行为：

- `archi .`
  - 先检查 `.hippocampus/` 必需产物是否完整
  - 再检查 metrics 是否与当前 Hippo bundle 一致
  - 只有在 bundle 缺失或 stale 时才自动 refresh
- `archi --refresh-from-hippo .`
  - 强制 refresh

不采用以下策略：

- 不保持“只有缺文件才 refresh”的旧行为
- 不改成“每次执行都强制 refresh”

### 3.2 默认规则位置

正式决策：

- 默认规则集中在源码
- 项目侧只保留一个可选覆盖入口

含义：

- 不把默认规则做成 `.architec/rules.toml`
- 不让 `.architec/` 承担 repo 级长期规则配置职责
- 不先做多级配置查找

### 3.3 项目侧唯一可选规则文件

正式决策：

- repo 根规则文件采用 `.architecture-rules.toml`

设计目的：

- 让 `archi` 和 `hippo` 共用一份 repo 级排除策略
- 避免 `.archiignore` / `.hippoignore` 双文件分裂
- 保持项目配置面最小

### 3.4 不依赖 `.gitignore`

正式决策：

- 持续结构净化和架构分析排除规则不依赖 `.gitignore`

原因：

- `.gitignore` 的目标是版本控制噪音，不是分析语义边界
- cleanup 需要的扫描范围和 Git 忽略范围并不等价
- 文档第 5.5 / 5.6 需要覆盖 docs、scripts、prompts、configs 时，必须有独立语义

### 3.5 Hippo 和 Archi 的职责分离

正式决策：

- `hippo` 继续负责“结构输入”
- `archi cleanup` 负责“净化扫描”

含义：

- Hippo 仍然以源码导向的结构输入为主
- docs / config / prompt / script 不强行进入 Hippo 主热点输入
- `archi cleanup` 单独扩扫这些对象

### 3.6 主架构分析范围与 cleanup 扫描范围分离

正式决策：

- 主架构分析范围和 cleanup 扫描范围必须分离

具体区分：

- hotspot / component risk / topology 继续基于源码导向的 Hippo bundle
- cleanup inventory 扩扫：
  - `source`
  - `script`
  - `doc`
  - `config`
  - `prompt`

这样可以同时做到：

- 保持现有架构分析结果稳定
- 扩大对旧流程残留物的识别能力

## 4. 当前已落地内容

下列能力已完成并进入当前代码：

- `architect-metrics.json` 写入 `bundle_fingerprint`
- `archi` 可以识别 stale metrics
- `archi` 默认策略已改为“缺失或 stale 才自动 refresh”
- stale bundle 不再静默进入分析流程
- Hippo 输出 `.hippocampus/bundle-state.json`
- repo 根 `.architecture-rules.toml` 已被 `hippo` / `archi` 共用
- cleanup scope / inventory / ledger / summary 已落地
- cleanup 已进入 `archi .` 主报告
- `archi cleanup` 已成为独立命令
- `archi --goal` / `archi --diff` 已输出 `retire_plan`
- `archive-candidate` 独立文件已落地

这部分对应的是本方案第一阶段的完整收敛态，而不再只是 `P0.1`。

## 5. 最终责任划分

### 5.1 Hippo 负责什么

- 生成稳定、一致、可追踪的结构输入产物
- 输出可校验 freshness 的 bundle 元数据
- 支持 repo 级最小排除规则
- 对删除文件后的 bundle 状态变化给出明确表达

### 5.2 Archi 负责什么

- 校验 Hippo bundle 是否可安全消费
- 在 stale 时自动触发刷新
- 做 cleanup 扩范围扫描
- 输出清理候选、证据和摘要
- 在 goal / diff 分析中显式输出 retire plan

## 6. 最终数据契约

### 6.1 Hippo bundle 标准产物

后续完整 bundle 应包含：

- `.hippocampus/hippocampus-index.json`
- `.hippocampus/code-signatures.json`
- `.hippocampus/file-manifest.json`
- `.hippocampus/structure-prompt.md`
- `.hippocampus/architect-metrics.json`
- `.hippocampus/bundle-state.json`

### 6.2 bundle-state.json

这是当前标准 freshness 元数据文件。

第一版字段保持最小：

- `generated_at`
- `bundle_fingerprint`
- `index_file_count`
- `manifest_file_count`
- `signature_file_count`

### 6.3 architect-metrics.json

metrics 必须带：

- `generated_at`
- `bundle_fingerprint`

这样 `archi` 才能明确判断：

- metrics 是否匹配当前 Hippo bundle

### 6.4 Archi cleanup 产物

第一版正式产物：

- `.architec/architec-cleanup-inventory.json`
- `.architec/architec-cleanup-ledger.json`
- `.architec/architec-cleanup-summary.md`
- `.architec/architec-archive-candidates.json`
- `.architec/architec-archive-summary.md`

## 7. 最终规则模型

### 7.1 默认规则来源

第一版规则来源按优先级固定为：

1. 源码默认规则
2. repo 根 `.architecture-rules.toml`

不做：

- `~/.architec` 用户级规则
- `.architec/rules.toml`
- 多级 merge

### 7.2 规则文件位置

唯一项目级规则文件：

- `.architecture-rules.toml`

### 7.3 第一版规则 schema

```toml
[shared]
ignore_paths = []
ignore_globs = []
ignore_extensions = []

[[shared.cleanup_metadata]]
path = ""
glob = ""
kind = ""
category = ""
owner = ""
ttl_days = 0
expires_at = ""

[hippo]
ignore_paths = []
ignore_globs = []
ignore_extensions = []

[archi]
ignore_paths = []
ignore_globs = []
ignore_extensions = []
cleanup_extra_kinds = ["doc", "config", "prompt", "script"]

[[archi.cleanup_metadata]]
path = ""
glob = ""
kind = ""
category = ""
owner = ""
ttl_days = 0
expires_at = ""
```

### 7.4 规则消费方式

- `hippo` 消费：`shared + hippo`
- `archi` 消费：`shared + archi`

### 7.5 当前仍不支持的规则

当前仍明确后置，不进入这条最小 metadata 能力线：

- `protected_symbols`
- `allowed_compat_layers`
- 多层 exception 体系
- 多级规则查找

## 8. cleanup 扫描范围与对象分类

### 8.1 cleanup 扫描范围

第一版 cleanup 可扫描：

- `source`
- `script`
- `doc`
- `config`
- `prompt`

默认不扫描：

- binary
- generated
- fixture
- runtime artifact

### 8.2 第一版候选类别

第一版只保留以下类别：

- `legacy_impl`
- `fallback_branch`
- `compat_layer`
- `obsolete_script`
- `stale_doc`
- `stale_config`
- `stale_prompt`

### 8.3 第一版候选字段

第一版 inventory 输出至少包含：

- `path`
- `kind`
- `category`
- `confidence`
- `evidence`
- `replacement`
- `review_required`

## 9. 详细实施计划

下面的计划是正式执行顺序。

### Phase 0.1 已完成：Archi stale auto refresh

目标：

- 让 `archi` 在 bundle stale 时自动 refresh，而不是继续静默分析

当前状态：

- 已落地

已实现内容：

- `architect-metrics.json` 写入 `bundle_fingerprint`
- `archi` 在 bundle 缺失或 stale 时自动 refresh
- stale metrics 不再直接进入热点分析

### Phase 0.2 已完成：Hippo bundle-state 标准化

目标：

- 把 freshness 契约正式下沉到 Hippo 产物

修改范围：

- `hippo` CLI 更新链路
- `hippo` bundle state 写出模块

具体修改：

- 新增 `.hippocampus/bundle-state.json`
- `update` / `refresh` / `generate` / `index` 成功后写出 bundle-state
- `bundle_fingerprint` 由以下产物计算：
  - `hippocampus-index.json`
  - `code-signatures.json`
  - `file-manifest.json`

验收标准：

- 每次 Hippo 刷新后 bundle-state 一定存在
- 删除文件或新增文件后 fingerprint 正确变化

当前状态：

- 已落地

### Phase 0.3 已完成：Archi freshness 校验切换到 bundle-state

目标：

- 用正式契约而不是临时推断来判 stale

具体修改：

- `archi` 优先读取 `.hippocampus/bundle-state.json`
- 以 bundle-state 的 `bundle_fingerprint` 为标准
- metrics fingerprint 不匹配时自动 refresh
- 当前源码树若相对 `.hippocampus/file-manifest.json` 出现新增/删除，或已有源码文件的 `mtime` 晚于 bundle 生成时间，也会判 stale 并自动 refresh

兼容策略：

- 若旧 bundle 尚无 bundle-state，可暂时 fallback 到现算 fingerprint
- 但文档和测试应把 bundle-state 视为标准路径

验收标准：

- 新旧 bundle 都能给出正确 refresh 决策

当前状态：

- 已落地

### Phase 1.1 已完成：最小 repo 规则文件落地

目标：

- 让 `archi` / `hippo` 具备独立于 `.gitignore` 的最小排除能力

具体修改：

- 新增规则加载模块
- repo 根读取 `.architecture-rules.toml`
- `hippo` 消费 `shared + hippo`
- `archi` 消费 `shared + archi`

验收标准：

- 无规则文件时，行为基本不变
- `hippo` 和 `archi` 的排除策略相互独立

当前状态：

- 已落地

### Phase 1.2 已完成：cleanup 默认规则与扫描范围落地

目标：

- 把 cleanup 扫描边界做成真实代码，而不是继续停留在文档里

具体修改：

- 新增 cleanup 默认规则模块
- 新增 cleanup scope 分类模块
- 定义 `source/script/doc/config/prompt` 的 cleanup 分类逻辑

验收标准：

- 旧脚本、旧 docs、失效 config、旧 prompt 可进入 cleanup 扫描
- 不影响现有 hotspot 结果

当前状态：

- 已落地

### Phase 1.3 已完成：cleanup inventory / ledger / summary 落地

目标：

- 先把“该删什么”做成稳定产物

具体修改：

- 新增 cleanup inventory 构建模块
- 新增 ledger 写出
- 新增 summary markdown 写出

产物：

- `.architec/architec-cleanup-inventory.json`
- `.architec/architec-cleanup-ledger.json`
- `.architec/architec-cleanup-summary.md`

验收标准：

- 第一版无需 LLM 也能稳定输出可读候选

当前状态：

- 已落地

### Phase 1.4 已完成：cleanup 接入 Archi 主报告

目标：

- 让 cleanup 成为 `archi .` 的正式输出之一

具体修改：

- 在总报告中增加 cleanup section
- summary 中展示最重要的 cleanup 候选

明确要求：

- cleanup 候选不直接并入现有 hotspot 排名
- 不新增新的总分维度

当前状态：

- 已落地

### Phase 1.5 已完成：goal / diff retire plan

目标：

- 让 cleanup 从事后报告变成设计时约束

具体修改：

- `archi --goal "<goal>" .` 增加 `retire_plan`
- `archi --diff .` 增加：
  - 本次改动引入了哪些临时结构
  - 本次改动应同步退场哪些旧结构

第一版 retire plan 结构：

- `add`
- `retire`
- `validation`

## 10. 明确后置的内容

以下能力不应阻塞当前版本：

- 多级规则查找

其中 `baseline`、`gate`、`archive-candidate` 独立文件、`LLM semantic judge`、`autofix` 和 `TTL / owner / expires_at` 已经从后置项转为已落地能力。
剩余内容仍必须建立在 freshness、规则文件、cleanup inventory、baseline / gate 稳定之后再评估。

## 11. 测试计划

### 11.1 Hippo 侧测试

- bundle-state 写出测试
- 删除文件后 fingerprint 变化测试
- `.architecture-rules.toml` 对 Hippo 输入过滤生效测试

### 11.2 Archi 侧测试

- stale metrics 自动 refresh 测试
- bundle-state 优先路径测试
- cleanup scope 分类测试
- cleanup inventory / ledger / summary 输出测试

### 11.3 联动测试

- 删除源码文件 -> `hippo update` -> `archi .`
- 修改 docs/config/prompt -> `archi cleanup` 有候选，但主 hotspot 不误变

当前验证结果：

- 已在临时 git 仓库中验证 `删除源码文件 -> hippo update` 会让 `architect-metrics.json` 相对 `bundle-state.json` 进入 stale 状态
- 已在真实 CLI 链路中验证 `archi .` 会检测到上述 stale 并自动触发 refresh
- 已补充 `architec` 侧测试，验证当前源码树相对 `file-manifest.json` 的新增/删除，以及已有源码文件更新，都会直接让 `archi .` 判定 bundle stale
- 已在真实 CLI 链路中验证 `archi cleanup` 对 docs/config/prompt 变更产出 `stale_doc` / `stale_config` / `stale_prompt`
- 已验证 cleanup 扫描不会改动 Hippo bundle fingerprint，且 `HippoSnapshot.first_party_paths()` 仍只包含源码路径
- 已在真实仓库 `DeePoly_git` 上验证 `archi cleanup` 与 `archi .` 都会写出 archive candidate JSON / Markdown
- 已在真实仓库 `DeePoly_git` 上验证 `archi cleanup` 与 `archi .` 都会写出 semantic judge JSON / Markdown，且主报告会展示 `Semantic Judge` section
- 已在真实仓库 `DeePoly_git` 上验证 `archi autofix` dry-run 会写出 autofix plan / summary，但不会实际改动仓库
- 同一真实仓库当前 archive candidate 统计为：
  - `candidate_total=14`
  - `ready_total=7`
  - `review_total=7`
  - `by_category: stale_config=7, stale_doc=7`
- 同一真实仓库当前 semantic judge 统计为：
  - `status=ok`
  - `candidate_pool_total=10`
  - `reviewed_total=10`
  - `by_decision: archive_first=2, review=8`
- 同一真实仓库当前 autofix dry-run 统计为：
  - `status=planned`
  - `action_total=2`
  - `applied_total=0`
  - `by_action: archive_move=2`
- 同一真实仓库当前 cleanup metadata 统计为：
  - `owner_total=0`
  - `ttl_total=0`
  - `expires_total=0`
  - `expired_total=0`
- `architec` 全量测试已通过：`198 passed in 0.26s`
- `hippocampus` 全量测试已通过：`473 passed, 20 skipped in 24.98s`

## 12. 完成标准

这条能力线进入第一阶段完成态后，应满足：

- `archi .` 对缺失或 stale bundle 自动 refresh
- `.hippocampus` 具备正式 freshness 元数据
- repo 根 `.architecture-rules.toml` 可生效
- `archi cleanup` 可覆盖 `script/doc/config/prompt`
- cleanup 候选可带 `owner / ttl_days / expires_at`
- `.architec/` 输出 cleanup inventory / ledger / summary
- `.architec/` 输出 archive candidates / summary
- `.architec/` 输出 semantic judge JSON / summary
- `.architec/` 输出 autofix plan / summary
- `archi --goal` 和 `archi --diff` 能输出 retire plan
- 文档描述与实际 CLI 行为一致

当前状态：

- 以上条目均已在代码、测试和 CLI 文档中落地
- 剩余外部风险仅在 backend LLM provider 可用性，不属于本方案的结构契约范围
- 正式验收记录见 [`docs/progressive-architectural-cleanup-acceptance.md`](./progressive-architectural-cleanup-acceptance.md)

## 13. Phase 2.1 已完成：baseline 基线固化

目标：

- 把当前 cleanup / hotspot / topology 结果固化成可追踪基线，为后续 `gate` 提供稳定输入

具体修改：

- 新增 `archi baseline [path]` 命令
- 复用 `archi .` 主分析链路生成正式 baseline
- 新增 baseline 专用产物：
  - `.architec/architec-baseline.json`
  - `.architec/architec-baseline-summary.md`
- baseline 中冻结以下字段：
  - scores
  - cleanup 汇总
  - top hotspots
  - top risk components
  - topology 摘要
  - goal / diff retire plan 计数

验收标准：

- `archi baseline .` 会生成 baseline JSON / Markdown
- baseline 不引入新的分析输入，只复用现有稳定报告
- baseline 可为后续 gate 提供独立输入，而不是重新解析 Markdown

当前状态：

- 已落地

## 14. Phase 2.2 已完成：gate 基线回归检查

目标：

- 在 baseline 稳定后，把结构回退和 cleanup 回退变成正式门禁，而不是继续依赖人工目测

具体修改：

- 新增 `archi gate [path]` 命令
- gate 读取 `.architec/architec-baseline.json`
- gate 复用完整主分析链路，而不是走单独的弱化扫描
- 新增 gate 专用产物：
  - `.architec/architec-gate.json`
  - `.architec/architec-gate-summary.md`
- 当前 gate 默认检查：
  - `overall` 不低于 baseline
  - `structure` 不低于 baseline
  - `full` 不低于 baseline
  - cleanup 总候选数不高于 baseline
  - cleanup review-required 总数不高于 baseline
  - cleanup category 计数不高于 baseline

验收标准：

- 无 baseline 时给出明确错误并提示先执行 `archi baseline`
- 有 baseline 时，`archi gate .` 可输出 pass / fail 结论
- gate 直接消费 baseline JSON，而不是重新解析 Markdown

当前状态：

- 已落地

## 15. Phase 2.3 已完成：gate severity 细化

目标：

- 把 gate 从“所有 cleanup 回退都直接 fail”细化为按类别区分 `warn` / `block`

具体修改：

- gate 检查结果新增 `warning_total` 和 `warnings`
- gate 状态从二元 `pass/fail` 扩展为：
  - `pass`
  - `warn`
  - `fail`
- 默认 severity 规则：
  - `fallback_branch` / `legacy_impl` / `compat_layer` -> `block`
  - `obsolete_script` / `stale_doc` / `stale_config` / `stale_prompt` -> `warn`
  - score 回退 -> `block`
  - cleanup 总数回退 -> `warn`

验收标准：

- docs/config/prompt 类 cleanup 回退时，gate 可输出 `warn`
- fallback/legacy/compat 类 cleanup 回退时，gate 仍输出 `fail`
- gate summary 与 JSON 都能体现 severity

当前状态：

- 已落地

## 16. Phase 2.4 已完成：archive-candidate 独立文件

目标：

- 在 cleanup inventory 稳定后，补出“适合先归档”的独立 artifact，而不是让使用方只看 cleanup 候选自行判断

具体修改：

- 新增 `.architec/architec-archive-candidates.json`
- 新增 `.architec/architec-archive-summary.md`
- archive candidate 由 cleanup inventory 派生，不引入第二套扫描
- 第一版仅覆盖适合“archive first”的非源码对象：
  - `obsolete_script`
  - `stale_doc`
  - `stale_config`
  - `stale_prompt`
- 第一版输出：
  - `archive_tier`
  - `archive_reason`
  - `archive_path_hint`
- `archi cleanup`、`archi .`、Markdown summary、HTML viz、CLI summary 都会展示 archive candidate 摘要

验收标准：

- 不新增扫描链路也能稳定导出 archive artifact
- 主报告 JSON / Markdown / HTML 与 CLI summary 都能看到 archive candidate 结果
- 在真实仓库上能稳定区分 `ready` / `review`

当前状态：

- 已落地

## 17. Phase 2.5 已完成：LLM semantic judge

目标：

- 在 heuristic cleanup / archive candidate 稳定后，补一层有限范围的语义复核，避免直接把 heuristic 命中当成最终处置结论

具体修改：

- 新增 `.architec/architec-semantic-judge.json`
- 新增 `.architec/architec-semantic-judge-summary.md`
- semantic judge 消费 top cleanup / archive candidates，而不是新开扫描链路
- 当前 judge 决策输出：
  - `retire_now`
  - `archive_first`
  - `keep_active`
  - `review`
- `archi cleanup` 走 fail-open：
  - 不要求 backend LLM preflight
  - backend 不可用时也不会阻塞 cleanup 主链路
- `archi .` 主报告、Markdown summary、HTML viz、CLI summary 都会展示 semantic judge 摘要

验收标准：

- semantic judge 不破坏现有 cleanup / analysis CLI 路径
- backend 可用时能输出稳定 judgment artifact
- backend 不可用时仍能 fail-open 并保留 cleanup / archive 产物
- 主报告 JSON / Markdown / HTML 与 CLI summary 都能看到 semantic judge 结果

当前状态：

- 已落地

## 18. Phase 2.6 已完成：autofix

目标：

- 在 semantic judge 稳定后，把其中最安全、最明确的一小部分处置结论转成可执行动作，而不是永远停留在报告层

具体修改：

- 新增 `archi autofix [path]`
- 新增 `archi autofix --apply [path]`
- 新增 `.architec/architec-autofix-plan.json`
- 新增 `.architec/architec-autofix-summary.md`
- autofix v1 默认 dry-run，不直接修改仓库
- 当前只把 semantic judge 中满足以下条件的对象转成动作：
  - `decision = archive_first`
  - 非源码对象
  - 带合法 `archive_path_hint`
- 当前唯一执行动作：
  - `archive_move`
- `retire_now` 暂时仍是人工动作，不进入自动删改

验收标准：

- `archi autofix` 默认只生成计划，不修改仓库
- `archi autofix --apply` 只执行安全 archive move，不覆盖现有目标文件
- backend 不可用时仍能 fail-open，但不会误执行高风险动作
- CLI summary 与 artifact 都能清晰反映 `planned / applied / blocked / skipped`

当前状态：

- 已落地

## 19. Phase 2.7 已完成：TTL / owner / expires_at

目标：

- 在 cleanup / archive / semantic judge / autofix 已稳定后，为候选对象补上最小责任与时限 metadata，而不引入第二套复杂规则体系

具体修改：

- `.architecture-rules.toml` 新增：
  - `[[shared.cleanup_metadata]]`
  - `[[archi.cleanup_metadata]]`
- 当前 metadata rule 支持字段：
  - `path`
  - `glob`
  - `kind`
  - `category`
  - `owner`
  - `ttl_days`
  - `expires_at`
- metadata 只作用于 cleanup 派生产物：
  - cleanup inventory / ledger / summary
  - archive candidate JSON / Markdown
  - semantic judge JSON / Markdown
  - autofix plan / summary
- `expires_at` 当前支持 ISO date / datetime，并派生：
  - `expired`

验收标准：

- repo 规则文件可为 cleanup candidate 补充 `owner / ttl_days / expires_at`
- metadata 不改变原有 cleanup / archive / semantic / autofix 的主判定逻辑
- top candidate / judgment / action 输出能稳定透传这些字段
- 无 metadata 规则的真实仓库路径保持兼容，不影响现有 CLI 行为

当前状态：

- 已落地

## 20. 结论

这条方案的核心不是“继续增加一个评分项”，而是先把两个基础能力做稳：

- Hippo 输出必须是可校验、可追踪、可判 stale 的结构输入
- Archi 必须在主架构分析之外，稳定指出哪些旧结构已经应该退场

当前这条能力线已经完成：

- freshness 契约
- cleanup inventory / ledger / summary
- `goal / diff retire_plan`
- `baseline`
- `gate`
- `archive-candidate` 独立文件
- `LLM semantic judge`
- `autofix`
- `TTL / owner / expires_at`

按本方案当前剩余的后续项，只剩 `多级规则查找` 这类更重的配置能力，已不再属于本轮最小闭环。
