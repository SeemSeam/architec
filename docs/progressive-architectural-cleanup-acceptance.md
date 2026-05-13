# Architec 持续结构净化方案验收记录

> Historical / archived: 本文记录 advisory-review 迁移前的 cleanup、autofix、baseline、gate 真实验收，不代表当前 CLI。当前公开入口是 `archi code-review --full .`、`archi code-review --diff .`、`archi fix-advice --review <review.json>`、`archi status --snapshot` 和 `archi plan-review <plan.md>`；`--for <review.json>` 仍是 `fix-advice` 的兼容别名；legacy command parsers 和 wrapper public APIs 已退役。

本文档记录 [`docs/progressive-architectural-cleanup.md`](./progressive-architectural-cleanup.md) 当前阶段的正式验收结论、实测命令、关键产物和剩余工作。

## 1. 验收结论

阶段结论：

- 第一阶段验收通过
- 第二阶段 `baseline / gate` 验收通过
- Phase 2.4 `archive-candidate` 独立文件验收通过
- Phase 2.5 `LLM semantic judge` 验收通过
- Phase 2.6 `autofix` 验收通过
- Phase 2.7 `TTL / owner / expires_at` 验收通过

本次 historical 验收当时确认：

- Hippo `bundle-state` freshness 契约已落地
- Archi stale auto refresh 已落地并在真实仓库中验证
- `archi .` 已可在当前源码树与 `.hippocampus/file-manifest.json` 不一致，或已有源码文件更新晚于 bundle 生成时间时自动触发 refresh
- `.architecture-rules.toml` 共享规则模型已落地
- cleanup metadata 规则已落地，可注入 `owner / ttl_days / expires_at`
- cleanup scope / inventory / ledger / summary 已落地
- `archi cleanup` 已独立可用
- `archi .` 主报告已接入 cleanup 与 archive candidate 摘要
- `archi --goal` / `archi --diff` 已输出 retire plan
- `archi baseline` 已可固化结构基线
- `archi gate` 已可基于 baseline 做正式回归检查
- `archive-candidate` 已输出独立 JSON / Markdown 产物
- `semantic judge` 已输出独立 JSON / Markdown 产物，并接入主报告
- `autofix` 已输出独立 JSON / Markdown 产物，并提供 dry-run / apply 两种模式
- 文档、测试和真实 CLI 行为已经对齐

## 2. 验收范围

本次验收覆盖以下阶段：

- Phase 0.1: Archi stale auto refresh
- Phase 0.2: Hippo bundle-state 标准化
- Phase 0.3: Archi freshness 校验切换到 bundle-state
- Phase 1.1: `.architecture-rules.toml` 最小 repo 规则文件
- Phase 1.2: cleanup 默认规则与扫描范围
- Phase 1.3: cleanup inventory / ledger / summary
- Phase 1.4: cleanup 接入 Archi 主报告
- Phase 1.5: goal / diff retire plan
- Phase 2.1: baseline 基线固化
- Phase 2.2: gate 基线回归检查
- Phase 2.3: gate severity 细化
- Phase 2.4: archive-candidate 独立文件
- Phase 2.5: LLM semantic judge
- Phase 2.6: autofix
- Phase 2.7: TTL / owner / expires_at

明确仍不属于本次验收范围的后置能力：

- 多级规则查找

## 3. 真实仓库验收

验收日期：

- 2026-04-03

验收仓库：

- `/home/bfly/workspace/computeforcfd/混合网络/DeePoly_git`

本阶段使用当前源码执行的核心命令：

```bash
PYTHONPATH=src python3 -m architec cleanup /home/bfly/workspace/computeforcfd/混合网络/DeePoly_git
PYTHONPATH=src python3 -m architec autofix /home/bfly/workspace/computeforcfd/混合网络/DeePoly_git
PYTHONPATH=src python3 -m architec --skip-auth /home/bfly/workspace/computeforcfd/混合网络/DeePoly_git
PYTHONPATH=src python3 -m architec baseline --skip-auth --out /tmp/deepoly_archi_baseline_result.json /home/bfly/workspace/computeforcfd/混合网络/DeePoly_git
PYTHONPATH=src python3 -m architec gate --skip-auth --out /tmp/deepoly_archi_gate_result.json /home/bfly/workspace/computeforcfd/混合网络/DeePoly_git
```

此前在同一真实仓库上已完成的命令：

```bash
archi --check .
archi --diff --out /tmp/deepoly_archi_diff.json .
archi --goal "stabilize nonlinear PDE solver boundaries and retire legacy visualization and stale configs" --out /tmp/deepoly_archi_goal.json .
```

验收结果：

- `archi cleanup` 成功输出 cleanup inventory / ledger / summary，并额外输出 archive candidate 与 semantic judge JSON / Markdown
- `archi autofix` dry-run 成功输出 autofix plan / summary，且未直接改动真实仓库
- `archi --skip-auth <repo>` 成功输出主分析 JSON / Markdown / HTML，CLI summary 中包含 archive candidate 与 semantic judge 摘要
- `archi baseline` 成功输出 baseline JSON / Markdown
- `archi gate` 成功读取 baseline 并输出 gate JSON / Markdown
- 真实 gate 结果为 `pass`
- 在 gate severity 细化后，额外完成一次真实 warn-path smoke：临时收紧 `warn` 级 baseline 后，`archi gate` 返回 `warn`
- 额外完成一次真实 fail-path smoke：临时抬高 baseline 后，`archi gate` 返回 `fail`
- warn / fail smoke 完成后均已恢复原 baseline，并再次验证 `archi gate` 回到 `pass`
- `archi --check`、`archi --diff`、`archi --goal` 的真实链路此前已经完成，并保留了对应导出结果

## 4. 关键验收产物

真实仓库内产物：

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

附加导出产物：

- `/tmp/deepoly_archi_diff.json`
- `/tmp/deepoly_archi_goal.json`
- `/tmp/deepoly_archi_baseline_result.json`
- `/tmp/deepoly_archi_gate_result.json`
- `/tmp/deepoly_archi_gate_warn_result.json`
- `/tmp/deepoly_archi_gate_fail_result.json`
- `/tmp/deepoly_archi_gate_postwarn_restore_result.json`
- `/tmp/deepoly_archi_gate_postrestore_result.json`

## 5. 验收摘要

### 5.1 cleanup 结果

真实仓库 cleanup 摘要如下：

- 候选总数：`30`
- review required：`30`
- metadata：`owner_total=0`、`ttl_total=0`、`expires_total=0`、`expired_total=0`
- 分类统计：`fallback_branch=13`、`legacy_impl=3`、`stale_config=7`、`stale_doc=7`

这说明 cleanup 已经不再只看源码，而是可以稳定识别旧 docs 和失效 config，同时没有把这些对象强行并入 Hippo 的源码结构输入。
同一真实仓库当前没有配置 cleanup metadata 规则，因此 `owner / ttl_days / expires_at` 计数保持为 `0`，验证了该能力对未配置仓库是兼容增量而非破坏性变更。

### 5.2 archive-candidate 结果

真实仓库 archive candidate 摘要如下：

- 候选总数：`14`
- ready：`7`
- review：`7`
- 分类统计：`stale_config=7`、`stale_doc=7`

这说明 archive candidate 已经作为 cleanup inventory 的派生层稳定落地，并能把“适合先归档”的非源码对象进一步分成 `ready` 与 `review`。

### 5.3 semantic judge 结果

真实仓库 semantic judge 摘要如下：

- status：`ok`
- candidate pool total：`10`
- reviewed total：`10`
- decisions：`archive_first=2`、`review=8`

semantic judge 真实摘要显示：

- 当前 top cleanup/archive candidates 里，只有少量对象适合直接进入 `archive_first`
- benchmark case config、运行中任务追踪类文档等对象，即使被 heuristic 标成 stale，也会被保守打回 `review`
- semantic judge 已经不是另一个大范围扫描，而是建立在 cleanup / archive 之上的有限语义复核层

### 5.4 autofix 结果

真实仓库 autofix dry-run 摘要如下：

- status：`planned`
- action total：`2`
- applied total：`0`
- by action：`archive_move=2`

当前 top autofix 动作包括：

- `cases/nonlinear_pde_cases/time_pde_cases/README.md` -> `archive/cases/nonlinear_pde_cases/time_pde_cases/README.md`
- `deepoly.egg-info/SOURCES.txt` -> `archive/deepoly.egg-info/SOURCES.txt`

这说明 autofix v1 已经能够把 semantic judge 中最安全的 `archive_first` 结论转成明确动作，但默认仍保持 dry-run，不直接修改真实仓库。

### 5.5 主分析结果

真实仓库 `archi .` / `archi --goal` 输出显示：

- overall：`80.42`
- governance_overall：`78.0`
- structure：`82.84`
- full：`78.0`

热点和风险组件主要集中在：

- `src:problem_solvers`
- `src:spotter_runtime`

该结果说明：

- freshness 契约修复后，主分析链路可稳定完成
- cleanup、archive candidate 与 semantic judge 已进入主报告，但没有污染既有 hotspot 排名和评分模型

### 5.6 goal retire plan 结果

`/tmp/deepoly_archi_goal.json` 中已产生 `feature_analysis.retire_plan`：

- planned add：`2`
- planned retire：`5`
- validation checks：`3`

目标侧新增关注组件：

- `src:problem_solvers`
- `src:algebraic_solver`

目标侧已标出应同步退场的旧结构，包括：

- `src/problem_solvers/nonlinear_pde_solver/fixiteration_pde_solver/utils/visualize.py`
- `src/problem_solvers/nonlinear_pde_solver/pseudotime_pde_solver/pseudotime_solver_state_mixin.py`
- `src/problem_solvers/nonlinear_pde_solver/pseudotime_pde_solver/utils/pseudotime_config_loading_mixin.py`
- `src/problem_solvers/nonlinear_pde_solver/pseudotime_pde_solver/utils/pseudotime_visualize_flow_mixin.py`
- `src/problem_solvers/nonlinear_pde_solver/time_pde_solver/core/fitter.py`

### 5.7 diff retire plan 结果

`/tmp/deepoly_archi_diff.json` 中已产生 `change_analysis.retire_plan`：

- temporary add：`1`
- matched retire：`5`
- validation checks：`3`

这说明 diff 模式已经可以不只报告“这次改了什么”，还可以显式指出：

- 本次改动引入了哪些临时结构
- 本次改动应同步退场哪些旧结构

### 5.8 baseline 结果

真实仓库 baseline 摘要如下：

- overall：`80.42`
- governance_overall：`78.0`
- structure：`82.84`
- full：`78.0`
- cleanup candidate total：`29`
- cleanup categories：`fallback_branch=12`、`legacy_impl=3`、`stale_config=7`、`stale_doc=7`

这说明 baseline 已经可以把当前主分析、cleanup 和 topology 摘要冻结为单独基线，而不依赖人工保存一次 `archi .` 的终端输出。

注意：

- baseline / gate 章节记录的是本轮 semantic judge 落地前已完成的真实 baseline snapshot 验收结果
- 本次 semantic judge smoke 时，同一仓库的 cleanup 统计已更新到 `30` / `13`
- 这表明真实仓库内容在持续变化，但不影响 semantic judge 这一新增能力线的独立验收

### 5.9 gate 结果

真实仓库 gate 摘要如下：

- status：`pass`
- check total：`9`
- failure total：`0`

本次通过的 gate 检查包括：

- `overall score`
- `structure score`
- `full score`
- `cleanup candidate total`
- `cleanup review-required total`
- `cleanup category fallback_branch`
- `cleanup category legacy_impl`
- `cleanup category stale_config`
- `cleanup category stale_doc`

这说明 gate 已经不是“再跑一次分析”，而是确实完成了当前结果相对 baseline 的结构门禁判断。

### 5.10 gate warn-path smoke 结果

在 gate severity 细化后，本次还执行了一次真实 warn smoke：

- 先备份真实 baseline
- 保持 score、`fallback_branch`、`legacy_impl` 等 block 级阈值不变
- 仅把 `candidate_total` / `review_required_total` 从 `29` 收紧到 `28`
- 同时把 `stale_doc` 从 `7` 收紧到 `6`
- 在该临时 baseline 上执行 `archi gate`

结果如下：

- status：`warn`
- failure total：`0`
- warning total：`3`

warning 项与预期一致，覆盖了：

- `cleanup candidate total`
- `cleanup review-required total`
- `cleanup category stale_doc`

随后已恢复真实 baseline，并再次执行 `archi gate`，结果重新回到：

- status：`pass`
- failure total：`0`
- warning total：`0`

这说明 gate 的 `warn` 路径已经在真实仓库上验证通过。

### 5.11 gate fail-path smoke 结果

为了验证 gate 的失败路径，本次还执行了一次真实 smoke：

- 先备份真实 baseline
- 临时把 baseline 中的 `overall` / `structure` / `full` 抬高到 `95.0`
- 同时把 cleanup 总数和 category 计数压到 `0`
- 在该临时 baseline 上执行 `archi gate`

结果如下：

- status：`fail`
- check total：`9`
- failure total：`9`

失败项与预期一致，覆盖了：

- `overall score`
- `structure score`
- `full score`
- `cleanup candidate total`
- `cleanup review-required total`
- `cleanup category fallback_branch`
- `cleanup category legacy_impl`
- `cleanup category stale_config`
- `cleanup category stale_doc`

随后已恢复真实 baseline，并再次执行 `archi gate`，结果重新回到：

- status：`pass`
- failure total：`0`

这说明当前 gate 不只具备成功路径，也已经在真实仓库上验证了 `warn`、`fail` 和恢复路径。

## 6. 测试证据

### 6.1 Architec

在 `/home/bfly/workspace/architec` 执行：

```bash
PYTHONPATH=src python3 -m pytest -q tests
```

结果：

- `198 passed in 0.26s`

### 6.2 Hippocampus 定向测试

在 `/home/bfly/workspace/hippocampus` 执行：

```bash
PYTHONPATH=src python3 -m pytest -q \
  tests/test_bundle_state.py \
  tests/test_cli_core_commands.py \
  tests/test_source_filter.py \
  tests/test_sig_extract.py \
  tests/test_tree_gen.py
```

结果：

- `36 passed in 3.90s`

这组测试覆盖了本轮方案直接影响的 freshness、CLI、source filter 和 bundle 生成路径。

### 6.3 Hippocampus 全量测试

在 `/home/bfly/workspace/hippocampus` 执行：

```bash
PYTHONPATH=src python3 -m pytest -q tests
```

结果：

- `473 passed, 20 skipped in 24.98s`

## 7. 剩余工作判断

当前已完成的正式能力包括：

- freshness 契约
- cleanup inventory / ledger / summary
- 主报告 cleanup 集成
- goal / diff retire plan
- baseline
- gate
- archive-candidate 独立文件
- LLM semantic judge
- autofix
- TTL / owner / expires_at

因此主方案当前剩余的后续项已经收敛为：

- 多级规则查找

当前不建议优先做：

- 更复杂的规则体系
- 多级规则查找

因为这些能力都会建立在当前 freshness、cleanup、archive、baseline、gate 五层产物稳定可复用的前提上。
