# 目录命名裁决 LLM 方案

本文档定义 `architec` 中“目录命名裁决”能力的目标、边界、输入、输出和提示词约束。目标不是让大模型随机起目录名，而是让它像有经验的架构师一样，基于 Hippo 提供的项目词表、职责摘要和结构证据，给出稳定、可解释、可治理的目录命名裁决。

## 1. 为什么需要专门的命名裁决能力

当前项目的一个典型问题是源码文件平铺在包根目录，模块边界更多依赖文件名前缀，而不是通过文件夹边界明确表达。此时，架构师不应只说“建议拆目录”，还应回答：

- 哪些文件天然属于同一子域
- 这些子域应如何命名
- 为什么这个名字比其他名字更合适
- 这个命名是否符合项目既有风格
- 是否应该沿用现有术语，还是引入更稳定的新术语

这类问题非常适合由 LLM 参与，但必须建立在强约束之上。

## 2. 能力定位

目录命名裁决 LLM 的职责是：

- 对一组候选文件做语义归类
- 基于项目词表给出推荐目录名
- 判断命名是否符合项目当前架构风格
- 拒绝模糊、过泛、容易漂移的目录名
- 给出命名理由、备选方案和置信度

它的非目标是：

- 不直接修改文件系统
- 不决定最终迁移顺序
- 不凭主观偏好创造新术语
- 不脱离项目词表和结构证据随意命名

## 3. 设计原则

### 3.1 证据优先

所有命名判断都应来自显式证据，而不是模型印象。证据应包括：

- Hippo 的 `structure-prompt`
- 文件名和文件族
- 主符号名
- 组件职责摘要
- 依赖邻居
- 现有组件名和目录名

### 3.2 继承现有词表

优先使用项目已存在的稳定术语，而不是发明新名字。只有当现有词表明显混乱、含糊或误导时，才允许提出新命名。

### 3.3 命名稳定性优先于术语华丽

裁决目标应是“稳定、可扩展、可预测”，而不是“听起来高级”。

### 3.4 与项目风格一致

如果项目同层目录主要按能力域命名，则不应引入按技术实现命名的目录；反之亦然。命名裁决必须考虑全局一致性。

### 3.5 保守裁决

当证据不足时，应返回低置信度，并建议人工确认，而不是给出看似漂亮但不可靠的目录名。

## 4. 程序化输入建议

目录命名裁决不应直接接收原始仓库全文，而应消费程序化整理后的结构输入。建议新增一个中间输入对象，例如：

```json
{
  "workspace": "architec",
  "group_id": "backend_llm_family",
  "candidate_files": [
    "src/architec/backend_llm/config.py",
    "src/architec/backend_llm/flow.py",
    "src/architec/backend_llm/gateway.py"
  ],
  "evidence_terms": [
    "backend",
    "llm",
    "runtime",
    "gateway",
    "config"
  ],
  "responsibility_summary": "Backend LLM configuration, runtime selection, gateway execution and parse flow.",
  "primary_symbols": [
    "BackendLLMConfig",
    "complete_json",
    "build_runtime_spec"
  ],
  "layer_role": "integration",
  "peer_directories": [
    "analysis",
    "scoring",
    "reporting"
  ],
  "naming_style": {
    "top_level_pattern": "capability_domain",
    "prefer_short_nouns": true,
    "avoid_generic_names": true
  }
}
```

## 5. Hippo 和 `architec` 可复用的词表来源

当前项目中已有适合复用的词表和语义来源：

- `.hippocampus/structure-prompt.md`
- 组件描述中的 `responsibility_summary`
- 组件描述中的 `layer_role`
- 组件描述中的 `descriptor_terms`
- `primary_symbols`
- 文件路径和文件族前缀

其中，`descriptor_terms` 机制已经在过滤泛词，例如 `core`、`common`、`utils`、`helper`。这很适合直接作为命名裁决前置清洗。

## 6. LLM 提示词系统应该包含什么

为了让大模型能稳定做“命名裁决”，提示词系统至少应拆成两层：

### 6.1 共同系统提示词

负责定义角色和裁决原则：

- 你是目录命名裁判，不是自由命名器
- 必须基于输入证据做判断
- 优先复用项目稳定词表
- 避免模糊目录名和过泛目录名
- 输出必须严格结构化
- 证据不足时必须降低置信度

### 6.2 任务提示词

负责定义这一次要完成的具体任务：

- 判断一组文件是否应收敛为单一目录
- 给出推荐目录名和备选名
- 拒绝不合格名字
- 说明命名理由
- 说明与项目整体风格的一致性
- 给出置信度和人工复核建议

## 7. 必须约束的命名规则

LLM 裁决必须受到程序化规则约束，至少包括：

- 禁止使用过泛目录名：
  - `core`
  - `common`
  - `misc`
  - `utils`
  - `helpers`
  - `shared`

- 禁止使用临时性目录名：
  - `new`
  - `next`
  - `tmp`
  - `phase1`
  - `phase2`

- 不鼓励把实现机制当顶层能力域：
  - `json`
  - `yaml`
  - `http`
  - `runtime_tools`

- 优先使用短名、名词化、单数形式的能力域词

- 如果已有高频术语足以表达子域，应优先沿用，而不是造新词

## 8. 输出 schema 建议

建议命名裁决任务输出严格 JSON：

```json
{
  "group_id": "backend_llm_family",
  "decision": "accept|needs_review|reject",
  "recommended_name": "backend",
  "alternatives": ["llm_backend"],
  "rejected_names": ["core", "common", "utils"],
  "reason": "This group is primarily backend LLM integration and runtime behavior, not generic shared infrastructure.",
  "style_fit": {
    "status": "fits|mixed|conflicts",
    "reason": "Matches capability-domain naming used by peer folders."
  },
  "evidence": {
    "terms": ["backend", "llm", "gateway", "flow", "config"],
    "files": [
      "src/architec/backend_llm/config.py",
      "src/architec/backend_llm/flow.py"
    ],
    "symbols": ["BackendLLMConfig", "complete_json"]
  },
  "confidence": 0.91,
  "human_review_note": "If future non-LLM provider integrations are added, confirm whether backend remains the right umbrella."
}
```

## 9. 推荐的裁决流程

建议采用以下流程：

1. 程序先聚合文件族  
   例如按前缀、依赖关系、职责摘要形成候选组。

2. 程序先做词表清洗  
   去掉 `core/common/utils/helper` 这类弱语义词。

3. LLM 做命名裁决  
   给出推荐名、备选名、拒绝名、理由、风格一致性判断。

4. 程序做二次校验  
   检查是否命中禁用词、是否与现有目录冲突、是否违反全局风格。

5. 写入结构审查结果  
   进入 `.architec/naming-review.json` 或整体 review 报告。

## 10. 为什么要使用双层约束

只靠程序规则的问题：

- 语义不够强
- 很难在不同项目里判断哪个名字更贴切
- 很难做风格和职责的综合权衡

只靠 LLM 的问题：

- 不稳定
- 容易“起得好听但不实用”
- 不利于长期治理

因此最佳做法是：

- 程序负责边界、词表、禁用词和风格规则
- LLM 负责语义裁决和命名解释

## 11. 与现有 `architec` 配置的集成方式

当前仓库已经支持：

- `common_system_prompt`
- `task_prompt_prefixes`
- 按 `task` 路由不同提示词前缀

因此可以新增一个任务，例如：

- `architect_folder_naming`

并在配置中为该任务绑定专门提示词。

## 12. 成功标准

当目录命名裁决能力达到以下效果时，说明设计有效：

- 相同文件族多次分析时能给出稳定命名
- 输出的名称与项目词表一致，而不是随机发明
- 很少出现 `core/common/utils` 这类模糊名
- 能解释为什么某个名字更符合当前项目风格
- 在证据不足时能主动降置信度并要求人工确认

## 13. 结论

目录命名可以交给大模型做裁决，但前提是它被提示词系统和程序化证据严格约束。真正合理的实现方式不是“让模型起名字”，而是“让模型基于 Hippo 词表和项目结构做架构命名判断”。
