# Architec 注册授权与商业化落地方案

本文档把 `architec` 从当前的本地 Python CLI + skill 工具，推进到“可注册、可登录、可授权、可收费、可运营”的产品形态。目标不是空谈思路，而是提供一条可以按阶段执行的实施路线。

当前仓库基于实际实现补了一份上线审计：

- [docs/launch-readiness-audit.md](/home/bfly/workspace/architec/docs/launch-readiness-audit.md)
- [launch-ops-runbook.md](/home/bfly/workspace/architec-cloud/docs/launch-ops-runbook.md)

基于当前工作区，已有一套本地可运行的首版实现：

- `architec-cloud/` 已提供注册、登录、账户页、下载页、设备页、管理页与 CLI 授权 API 原型
- 下载分发已切换到独立 GitHub Releases 仓库：`bfly123/architec-releases`
- 已产出并验证 Linux 编译包：`archi-linux-x86_64.tar.gz`
- 已提供公开安装脚本：`https://www.architec.top/downloads/latest/install_prod.sh`
- 网站当前角色是“控制面”，不承担安装包托管职责
- 本地验证已通过 `pnpm build` 与 `pnpm test:e2e`
- 当前还补了一条真实安装回归命令：`bash ../architec-release/tools/release_install_smoke.sh`
- 当前本地联调还支持由 `architec-cloud` 直接托管 `/downloads/latest/*`，避免本地测试时打 GitHub API rate limit

## 1. 当前状态与目标

### 1.1 当前状态

当前 `architec` 的运行模式是：

- 本地安装 Python 包
- 通过 `archi` 命令运行分析
- 通过网站安装器初始化用户级配置并同步 Codex / Claude skills
- 主要入口在 `src/architec/cli.py`
- 当前对外分发方式仍偏开发态，核心代码以 Python 源码形式暴露

当前仓库里与后续改造直接相关的入口包括：

- `pyproject.toml`
- `src/architec/cli.py`
- `src/architec/integration/resource_paths.py`
- `codex_skills/`
- `claude_skills/`

### 1.2 目标状态

目标产品形态应当是：

- 用户先访问网站注册账号
- 用户在网站完成登录、订阅和下载
- 用户本地安装 `archi`
- 用户执行 `archi login`
- `archi` 联网完成授权
- 授权通过后，用户才能在本地 Claude / Codex 中继续通过 skill 使用 `archi`
- 账号、设备、订阅、到期、封禁、版本约束都能在服务端控制

### 1.3 不现实的预期

必须明确：

- 只要核心能力完整运行在用户机器上，就不能做到绝对防破解
- 本地授权能做的是提高绕过成本，而不是从原理上完全阻止
- 如果以后需要更强保护，必须把部分高价值能力迁移到服务端

## 2. 总体策略

推荐路线不是直接把 `architec` 改成纯 SaaS，而是采用：

- 本地执行
- 联网授权
- 编译分发
- 服务端控制账号、订阅和设备

这条路线适合当前项目，因为：

- CLI 入口集中，适合加统一门禁
- skill 仍可以保留，不需要重做为网页产品
- 本地项目分析与 Hippo 集成链路可以继续复用
- 商业化改造可以与核心分析能力解耦

一句话总结：

`architec` 保持为本地分析工具，但必须先通过在线注册、登录和许可校验，才能继续使用。

## 3. 最终系统架构

建议拆为两个仓库：

### 3.1 本地客户端仓库

保留当前仓库 `architec`，负责：

- 本地分析能力
- CLI 命令
- skill 安装
- 本地授权缓存
- 编译和发布

### 3.2 云端服务仓库

新增 `architec-cloud` 仓库，负责：

- 注册站
- 登录与账号系统
- 订阅与支付
- 设备管理
- CLI 授权 API
- 授权租约签发
- 后台管理

当前工作区内已经加入一个本地可运行的 `architec-cloud/` 脚手架，用于提前验证：

- Next.js App Router 页面结构
- 认证与设备管理页面路由
- CLI 授权 API 路由形态
- 后续接入 Supabase / Stripe / Vercel 的目录边界

### 3.3 逻辑边界

本地客户端负责：

- 读取项目
- 执行本地分析
- 展示结果
- 请求授权服务
- 校验服务端签名租约

云端服务负责：

- 用户身份
- 订阅状态
- 设备数限制
- 授权签发
- 授权撤销
- 版本最小支持策略

## 4. 技术选型

为降低首版复杂度，推荐以下栈：

### 4.1 云端

- 前端与 API：`Next.js`
- 部署：`Vercel`
- 认证：`Supabase Auth`
- 数据库：`Supabase Postgres`
- 支付：`Stripe Billing`
- 邮件：`Resend` 或 `Postmark`
- 监控：`Sentry`
- DNS / 域名代理：`Cloudflare`

### 4.2 本地客户端

- 继续使用 Python 3.11
- 新增 `architec.auth` 授权模块
- 使用 `Nuitka` 编译生产版
- 开发态继续保留源码方式

### 4.3 不建议的首版做法

首版不建议：

- 自己从零写账号密码系统
- 自己从零实现支付系统
- 继续对付费用户分发 `pip install -e .`
- 把安全校验写进 `SKILL.md`
- 一开始就改成纯云端分析

## 5. 注册站实施方案

### 5.0 当前本地回归入口

为了避免“网站能打开，但真实安装链路没跑过”，当前工作区应固定保留下列回归命令：

```bash
bash ../architec-release/tools/release_install_smoke.sh
```

这条命令会自动完成：

- 启动本地 `architec-cloud`
- 运行网站公开页与注册登录 smoke
- 从本地 `architec-cloud` 提供的 `/downloads/latest` 下载真实发布包
- 模拟已登录用户调用 `/api/cli/authorize`
- 用真实安装出来的 `archi` 执行 `login`、`whoami --json`、`status --json`、`devices --json`、`logout`

上线前要求不是“有人手工点过一次”，而是这条链路可以稳定重复执行。

补充说明：

- `../architec-release/tools/install_prod.sh` 已支持 `--base-url`
- 本地 smoke 会自动把 `ARCHITEC_CLOUD_DOWNLOAD_BASE_URL` 指向 `http://127.0.0.1:3100/downloads/latest`
- 这样既保留真实安装包回归，又不依赖 GitHub Releases API 元数据查询

### 5.1 新建站点仓库

新建仓库：

- `architec-cloud`

初始化项目：

```bash
npx create-next-app@latest architec-cloud
```

推荐目录结构：

```text
architec-cloud/
  app/
    page.tsx
    login/page.tsx
    register/page.tsx
    pricing/page.tsx
    account/page.tsx
    account/billing/page.tsx
    account/devices/page.tsx
    account/downloads/page.tsx
    legal/privacy/page.tsx
    legal/terms/page.tsx
    api/
      cli/
        login/start/route.ts
        login/exchange/route.ts
        lease/refresh/route.ts
        status/route.ts
      billing/
        checkout/route.ts
        portal/route.ts
      webhooks/
        stripe/route.ts
  lib/
    supabase/
    auth/
    billing/
    cli/
    db/
  prisma-or-sql/
  public/
```

### 5.2 必做页面

首版至少做这些页面：

- `/`
- `/register`
- `/login`
- `/pricing`
- `/account`
- `/account/billing`
- `/account/devices`
- `/account/downloads`
- `/legal/privacy`
- `/legal/terms`

### 5.3 注册与登录

首版登录方式建议只做：

- 邮箱注册
- 邮箱密码登录
- 邮箱验证
- 忘记密码

不要首版就上：

- GitHub 登录
- Google 登录
- 企业 SSO

### 5.4 Supabase Auth 接入

实施步骤：

1. 创建 Supabase 项目
2. 打开 Email Auth
3. 配置站点域名和 redirect URL
4. 接入自定义 SMTP
5. 建立 `profiles` 表同步用户信息

注册站完成标准：

- 用户可注册
- 用户可验证邮箱
- 用户可登录
- 用户可重置密码
- 用户可进入账户页

## 6. 支付与订阅实施方案

### 6.1 Stripe 接入

当前更合适的首版定价模型是单一套餐，减少产品解释成本和配置复杂度。

建议套餐：

- `standard`
- 注册后自动获得 `7` 天免费试用
- 试用结束后切换为 `$2/月`
- 设备上限由服务端控制，首版可先固定为 `3` 台

当前本地联调阶段可继续保持：

- 注册后默认进入有效期内
- 结算价格先为 `0`
- Stripe 集成延后到正式上线前接入

### 6.2 Stripe 页面与 API

正式接 Stripe 前，你需要完成：

- `/pricing` 页面
- 创建 Checkout Session
- 创建 Billing Portal Session
- 处理 Stripe webhook
- 在本地数据库同步订阅状态

### 6.3 必做的 webhook

至少处理以下事件：

- `checkout.session.completed`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.paid`
- `invoice.payment_failed`

### 6.4 首版业务规则

建议：

- 付款成功后订阅生效
- 订阅过期后停止刷新授权租约
- 用户可在账户页打开 Stripe Customer Portal
- 退款和人工处理先走后台，不做过度自动化
- 在本地测试阶段允许 `trialing` / `active` 两种状态都能继续授权

## 7. 数据库模型

建议最小表结构如下。

### 7.1 用户与订阅

`profiles`

- `id`
- `email`
- `display_name`
- `role`
- `created_at`

`plans`

- `id`
- `code`
- `name`
- `seat_limit`
- `features_json`
- `active`

`subscriptions`

- `id`
- `user_id`
- `plan_id`
- `provider_customer_id`
- `provider_subscription_id`
- `status`
- `current_period_end`
- `cancel_at_period_end`
- `created_at`

### 7.2 CLI 设备与授权

`devices`

- `id`
- `user_id`
- `install_id`
- `device_name`
- `hostname`
- `os`
- `arch`
- `app_version`
- `first_seen_at`
- `last_seen_at`
- `revoked_at`

`cli_refresh_tokens`

- `id`
- `user_id`
- `device_id`
- `token_hash`
- `expires_at`
- `revoked_at`
- `last_used_at`
- `created_at`

`license_leases`

- `id`
- `user_id`
- `device_id`
- `lease_jti`
- `issued_at`
- `expires_at`
- `revoked_at`

`cli_login_sessions`

- `id`
- `user_id`
- `state`
- `code_challenge`
- `one_time_code_hash`
- `install_id`
- `expires_at`
- `used_at`

### 7.3 审计

`audit_logs`

- `id`
- `user_id`
- `action`
- `ip`
- `user_agent`
- `metadata_json`
- `created_at`

## 8. CLI 授权与登录流程

### 8.1 首版推荐流程

首版推荐采用：

- 浏览器登录
- 本地回调
- 服务端交换 token
- 本地保存 refresh token 与短期 license lease

不推荐首版直接让用户在 CLI 里输入邮箱密码。

### 8.2 `archi login` 目标体验

用户执行：

```bash
archi login
```

本地 CLI 执行以下步骤：

1. 生成 `state`
2. 生成 `code_verifier`
3. 生成或读取本地 `install_id`
4. 启动本地回调监听，例如 `127.0.0.1:46319`
5. 打开浏览器到 `https://app.architec.dev/cli/login`
6. 用户在网页完成登录
7. 网页回调到本地 CLI
8. CLI 调用服务端交换：
   - `refresh_token`
   - `license_lease`
9. CLI 把状态保存到本地

### 8.3 本地保存内容

建议保存在：

- `~/.architec/auth/device.json`
- `~/.architec/auth/session.json`
- `~/.architec/auth/lease.json`

更安全的做法是：

- 优先使用系统 keychain 保存 refresh token
- 文件里只保存非敏感元数据

### 8.4 `license_lease` 内容

授权租约建议包含：

- `sub`
- `plan`
- `device_id`
- `install_id`
- `features`
- `exp`
- `nbf`
- `iss`
- `aud`
- `token_version`
- `app_version_min`

租约应由服务端使用私钥签名，本地只持有公钥验签。

### 8.5 有效期建议

首版建议：

- `license_lease` 有效期：24 小时
- 宽限离线时间：72 小时
- `refresh_token` 有效期：30 天

### 8.6 续租规则

每次执行分析前：

1. 读取本地租约
2. 验证签名与过期时间
3. 若租约临近过期，尝试联网刷新
4. 若刷新失败但仍在离线宽限内，允许执行
5. 若已过期且无法刷新，拒绝执行

## 9. 本地代码改造方案

### 9.1 新增模块

建议在当前仓库新增：

```text
src/architec/auth/
  __init__.py
  client.py
  commands.py
  device.py
  guard.py
  lease.py
  store.py
```

职责建议：

- `client.py`
  负责请求云端授权 API
- `commands.py`
  实现 `login/logout/status/whoami/devices`
- `device.py`
  管理本地设备标识
- `guard.py`
  在 CLI 执行前做授权校验
- `lease.py`
  负责租约解析与验签
- `store.py`
  负责本地状态持久化

### 9.2 CLI 命令扩展

建议新增命令：

- `archi login`
- `archi logout`
- `archi status`
- `archi whoami`
- `archi devices`
- `archi doctor`
- `archi skill install codex`
- `archi skill install claude`

### 9.3 门禁位置

授权门禁要加在 `src/architec/cli.py` 的统一入口前，而不是分散到分析模块里。

原则：

- `login/logout/status/whoami` 不要求已授权
- 实际分析命令必须授权通过
- 如果需要支持试用版，则在 `guard.py` 统一处理试用策略

### 9.4 配置路径

建议继续复用现有用户配置目录：

- `~/.architec/`

但把授权状态明确放到：

- `~/.architec/auth/`

不要把授权状态写到项目内 `.architec/`，因为授权是用户级，不是项目级。

## 10. Skill 改造方案

### 10.1 Skill 的定位

skill 只是使用入口，不是安全边界。

不能指望通过修改 `SKILL.md` 来防止绕过。

### 10.2 Skill 的调整方式

首版只需要做两件事：

- skill 继续调用 `archi ...`
- 文案中提示未授权时先执行 `archi login`

### 10.3 Skill 安装建议

当前网站安装器会直接安装 skill。生产版建议改成：

- 开发态：本地源码调试继续使用 `python3 -m pip install -e .`
- 生产态：改为 `archi skill install codex`
- 生产态：改为 `archi skill install claude`

这样更利于：

- 版本升级
- 平台差异处理
- 用户按需安装

## 11. 分发与封装方案

### 11.1 开发态与生产态分离

需要明确分两种安装方式。

开发态：

- 保留源码开发方式
- 可以继续使用 `python3 -m pip install -e .`

生产态：

- 不再分发源码安装方式
- 不再要求用户进入仓库执行本地安装脚本
- 分发编译后的安装包或二进制包

### 11.2 编译方案

首版推荐使用 `Nuitka` 编译生产版。

原因：

- 对当前 Python CLI 侵入较小
- 比纯 wheel / zipapp 更难直接读出源码
- 构建链路可渐进接入

### 11.3 发布产物

当前已落地的首版发布产物：

- `archi-linux-x86_64.tar.gz`
- `install_prod.sh`
- `SHA256SUMS.txt`

下一阶段再补：

- `archi-macos-arm64.tar.gz`
- `archi-windows-x86_64.zip`

### 11.4 安装体验

生产用户的安装流程应为：

1. 登录网站
2. 打开下载页
3. 下载对应平台安装包
4. 安装 `archi`
5. 执行 `archi login`
6. 执行 `archi skill install codex` 或 `archi skill install claude`
7. 开始使用

### 11.5 原生启动器

如果后续需要更强防护，可以做第二阶段：

- 用 Rust / Go / C 写一个 `archi` 原生启动器
- 启动器负责授权校验
- Python 内核作为编译模块加载

这不是首版必需，但应作为后续增强方向。

## 12. 安全与防绕过策略

### 12.1 必须接受的事实

不能承诺：

- 绝对不可破解
- 绝对无法逆向
- 绝对无法 patch

能做到的是：

- 提高普通用户绕过成本
- 防止明文配置伪造授权
- 控制账号、订阅和设备

### 12.2 必做策略

- 所有授权接口走 HTTPS
- `auth_code` 一次性使用
- `refresh_token` 数据库存 hash
- `license_lease` 服务端签名
- 本地只验签，不信任本地明文开关
- 对 CLI API 做速率限制
- 支持服务端吊销 token 与设备
- 支持 `app_version_min`

当前本地控制面已经加入一个可配置的最小版本门槛：

- 环境变量：`ARCHITEC_CLOUD_CLI_MIN_VERSION`
- 浏览器授权页会显示客户端版本与最低版本
- `/api/cli/login/exchange` 会拒绝低于最低版本的 CLI
- `/api/cli/lease/refresh` 会拒绝旧版本继续续租
- `/api/cli/status` 会返回 `upgrade_required`、`cli_min_version` 与 GitHub Releases 升级地址

### 12.3 更强保护的方向

后续如需增强，可逐步增加：

- 原生启动器
- 关键逻辑编译模块化
- 关键 prompt 与策略配置远端下发
- 部分高价值分析逻辑迁移到服务端

## 13. 运营面建设

要达到“可运营”状态，除了代码，还必须补齐这些。

### 13.1 域名与环境

建议：

- 官网与控制台：`app.architec.dev`
- API 域名：`api.architec.dev`
- 下载入口优先直接指向 GitHub Releases

如果以后需要统一品牌域名，可以增加：

- `downloads.architec.dev` 作为跳转页或重定向入口

但 MVP 不需要自己托管下载文件。

环境建议：

- `dev`
- `staging`
- `prod`

### 13.2 法务页面

必须准备：

- `Terms of Service`
- `Privacy Policy`
- `Refund Policy`

### 13.3 支持渠道

至少提供：

- `support@...`
- 账户问题处理流程
- 设备解绑处理流程
- 退款申请处理流程

### 13.4 监控与日志

建议接入：

- Sentry
- 请求日志
- CLI 授权失败日志
- Stripe webhook 错误日志
- 登录行为审计日志

### 13.5 管理后台能力

至少要有：

- 按邮箱搜索用户
- 查看订阅状态
- 查看设备列表
- 撤销设备
- 撤销 refresh token
- 手动封禁账号
- 查看授权与支付审计记录

## 14. 分阶段实施计划

### Phase 0：基础决策，2 到 3 天

产出：

- 域名
- 套餐定义
- seat 规则
- 离线宽限规则
- 目标用户地域
- 是否允许试用

完成标准：

- 商业规则明确
- 技术路线冻结

### Phase 1：注册站与认证，1 周

任务：

- 建立 `architec-cloud`
- 接 Supabase Auth
- 完成注册、登录、邮箱验证、重置密码
- 完成 `/account`
- 接自定义 SMTP

完成标准：

- 用户能独立注册和登录

### Phase 2：订阅与支付，1 周

任务：

- 接 Stripe
- 做套餐页
- 做 Checkout 和 Customer Portal
- 同步 webhook 到数据库

完成标准：

- 订阅状态能正确反映到用户账号

### Phase 3：CLI 授权链路，1 到 1.5 周

任务：

- 新增 `architec.auth`
- 实现 `archi login/logout/status`
- 实现租约签发与刷新
- 在 CLI 主入口加入授权门禁

完成标准：

- 未授权用户无法执行分析
- 已授权用户可正常执行分析

### Phase 4：生产分发，1 周

任务：

- 加 Nuitka 构建
- 产出多平台包
- 建下载页
- 写生产安装文档

完成标准：

- 付费用户能在不接触源码的前提下安装使用

### Phase 5：Skill 与升级，3 到 5 天

任务：

- skill 安装改由 CLI 管理
- 更新 skill 文案
- 增加版本检查与最低版本策略

完成标准：

- 授权后的用户可在 Codex / Claude 中正常调用 skill

### Phase 6：运营与后台，1 周

任务：

- 管理后台
- 支持邮箱
- 监控
- 法务页面
- 审计日志
- 封禁与解绑能力

完成标准：

- 出现真实用户问题时可运维、可追踪、可处理

## 15. 仓库级改造清单

### 15.1 当前仓库 `architec`

建议新增：

- `docs/commercial-rollout-plan.md`
- `src/architec/auth/`

建议调整：

- `src/architec/cli.py`
- `README.md`
- `codex_skills/*/SKILL.md`
- `claude_skills/*/SKILL.md`

发布相关脚本现在应由独立仓库 `architec-release` 维护：

- `../architec-release/tools/build_release.py`
- `../architec-release/tools/build_nuitka.sh`
- `../architec-release/tools/install_prod.sh`

### 15.2 新仓库 `architec-cloud`

需要创建：

- 注册站
- 认证 API
- 订阅 API
- 授权 API
- 管理后台

## 16. MVP 验收标准

满足以下条件才算进入可试运营状态：

- 用户能注册并验证邮箱
- 用户能完成订阅支付
- 用户能下载生产安装包
- 用户能执行 `archi login`
- 本地 `archi` 未授权时被拦截
- 本地 `archi` 已授权时可正常执行分析
- 用户能查看并解绑设备
- 订阅过期后无法继续刷新租约
- 管理员能封禁账号和撤销设备
- 出现错误时有日志和告警

### 16.1 当前已完成项

按当前工作区实现，下面这些已经有本地可验证结果：

- 用户能注册并登录进入账户页
- 用户能打开账户下载页并看到 GitHub Releases 直链
- 用户能执行浏览器授权链路的本地端到端测试
- 管理员能禁用账号、降低 seat 上限、撤销设备
- Linux 编译包和安装脚本已经可以从 GitHub Releases 下载并安装

仍未完成的主要是正式生产依赖接入：

- 邮箱验证与忘记密码的真实邮件链路
- Stripe 正式订阅与 webhook
- 生产数据库与审计日志
- macOS / Windows 编译发布物

## 17. 风险与决策点

### 17.1 最大风险

- 仍有用户尝试逆向和 patch
- 国内外网络环境可能影响授权可用性
- 支付失败和邮件到达率会影响转化
- 多平台打包会带来构建复杂度

### 17.2 关键决策点

上线前必须明确：

- 用户主要分布地区
- 是否允许离线使用
- 免费试用是否开放
- 设备数是否可自助释放
- 是否需要企业版 seat 管理

## 18. 建议的首版结论

对当前 `architec`，首版应采用以下最终方案：

- 保留本地 CLI 形态，不改为纯 SaaS
- 新建 `architec-cloud` 做注册、登录、支付和授权
- `archi` 新增浏览器登录与本地租约校验
- skill 继续调用 `archi`，不承担安全职责
- 生产版通过编译产物分发，不再直接分发可编辑源码

这是当前成本、可控性、用户体验和商业化速度之间最平衡的方案。
