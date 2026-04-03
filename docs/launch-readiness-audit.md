# Architec 上线准备审计

本文档基于当前仓库实际实现，对 `architec` 和 `architec-cloud` 距离“可公开上线、可收费、可运营”的状态做一次阻塞项审计。

配套运维执行步骤见：

- [docs/launch-ops-runbook.md](/home/bfly/workspace/architec/docs/launch-ops-runbook.md)

结论先行：

- 当前已经能跑通“注册 -> 登录 -> 浏览器授权 -> 本地 CLI 使用”的主链路
- 当前已经具备本地 Stripe 接入骨架，但仍默认是本地 stub / 开发态
- 当前**不适合直接公开商用上线**
- 当前更适合的阶段定义是：`本地验证版 / 内测版 / 小范围灰度`

如果目标是“公开收费上线”，下面这些事项需要按优先级补齐。

## 1. 当前可用能力

已经具备的能力：

- `archi login` 浏览器授权回调链路已经打通
- 本地会话、刷新令牌、签名租约、设备撤销已经具备基本形态
- 网站已经具备产品站、账户页、设备页、账单页、管理员页
- 站点视觉、文案、交互、基础危险操作确认已经比原始脚手架完整很多
- Stripe Checkout / Portal / Webhook 已有代码骨架，并且无密钥时自动回退 stub

这些是已经做出来的“产品骨架”，不是空白。

## 2. P0 必须完成

以下项目如果不完成，不建议对外公开收费。

### 2.1 生产身份系统仍未落地

当前证据：

- [architec-cloud/README.md](/home/bfly/workspace/architec/architec-cloud/README.md) 明确写了当前是 `local JSON-backed state for development`
- [architec-cloud/src/lib/db.ts](/home/bfly/workspace/architec/architec-cloud/src/lib/db.ts) 仍然使用 `.data/dev-db.json`
- [architec-cloud/src/app/api/auth/register/route.ts](/home/bfly/workspace/architec/architec-cloud/src/app/api/auth/register/route.ts) 和 [architec-cloud/src/app/api/auth/login/route.ts](/home/bfly/workspace/architec/architec-cloud/src/app/api/auth/login/route.ts) 仍是本地文件态账号系统

上线要求：

- 切换到真实数据库
- 切换到真实认证系统
- 至少具备可靠的 session 生命周期管理
- 账号、设备、订阅、审计都必须可持久化且可备份

建议：

- 直接落 Supabase Auth + Postgres
- 不要继续扩展本地 JSON 方案到生产

### 2.2 邮箱验证 / 密码重置 / 账户恢复没有真正实现

当前证据：

- [architec-cloud/src/app/api/auth/register/route.ts](/home/bfly/workspace/architec/architec-cloud/src/app/api/auth/register/route.ts) 直接把 `emailVerified` 设为 `true`
- 代码库中没有真实邮件发送、验证链接、密码重置邮件、SMTP 集成

上线要求：

- 注册后邮箱验证
- 忘记密码
- 重置密码
- 异常登录后的账户恢复路径

否则的问题：

- 容易被批量注册
- 账号找回不可运营
- 支持成本会直接落到人工

### 2.3 法律页已经有草案，但还没有完成正式法务审阅

当前证据：

- [architec-cloud/src/app/legal/privacy/page.tsx](/home/bfly/workspace/architec/architec-cloud/src/app/legal/privacy/page.tsx) 已经补成结构化隐私政策草案
- [architec-cloud/src/app/legal/terms/page.tsx](/home/bfly/workspace/architec/architec-cloud/src/app/legal/terms/page.tsx) 已经补成结构化服务条款草案
- 但当前文本仍是工程运营草案，不是按具体司法辖区审阅后的正式法律文本

上线要求：

- 隐私政策必须写实
- 服务条款必须写实
- 明确数据收集、设备记录、授权事件、计费、取消、退款、封禁、支持渠道
- 在正式收费前完成法务审阅并替换为正式版本

说明：

- 这项相比之前已经前进了一步，不再是空白页
- 但对外公开收费前，仍然不能把“工程草案”当成最终法律文本

### 2.4 客户端分发仍是开发态，代码暴露风险高

当前证据：

- [pyproject.toml](/home/bfly/workspace/architec/pyproject.toml) 仍是普通 Python 包入口
- [install.sh](/home/bfly/workspace/architec/install.sh) 仍偏开发机安装和技能写入脚本
- [architec-cloud/src/app/account/downloads/page.tsx](/home/bfly/workspace/architec/architec-cloud/src/app/account/downloads/page.tsx) 明确还是 `Placeholder artifact`

上线要求：

- 至少形成正式客户端发布物
- 最好是编译分发，而不是直接暴露完整 Python 源码
- 下载物需要版本号、校验值、最小支持版本策略

否则的问题：

- 用户拿到的仍是开发态源码
- 破解门槛过低
- 更新、回滚、渠道管理都不可控

### 2.5 公开下载渠道已有基础方案，但正式发布物与更新策略未完成

当前证据：

- [architec-cloud/src/app/download/page.tsx](/home/bfly/workspace/architec/architec-cloud/src/app/download/page.tsx) 已改为公开指向 GitHub Releases
- [architec-cloud/src/app/account/downloads/page.tsx](/home/bfly/workspace/architec/architec-cloud/src/app/account/downloads/page.tsx) 已明确“网站只做注册授权，下载留在 GitHub”
- 但仓库内仍没有看到正式每平台产物命名规范、checksum 页面、签名策略、自动更新策略

上线要求：

- GitHub Releases 上必须已经挂真实可安装产物
- 安装文档必须与真实产物一致
- 版本下载、变更记录、校验、平台区分明确
- 最好补签名与最小支持版本策略

### 2.6 缺少监控、异常采集、审计日志

当前证据：

- 代码库内没有 Sentry、异常事件上报、审计日志、报警配置
- 搜索结果没有真实 `sentry`、`telemetry`、`support` 集成

上线要求：

- 站点异常监控
- API 错误监控
- 关键授权事件审计
- 登录失败 / 撤销 / 订阅状态变化的可追溯日志

否则的问题：

- 用户报障时你无法定位
- 授权链路失败没有观测面
- 收费后支持体验会很差

### 2.7 缺少生产部署与备份方案

当前证据：

- 当前没有 `.github/workflows`，也没有可见的 CI/CD 流程
- `architec-cloud/README.md` 仍把生产部署描述成未来迁移目标

上线要求：

- 明确部署平台
- 环境变量管理
- 数据备份
- 回滚方案
- 域名、HTTPS、反向代理、故障恢复

没有这些，不建议公开收费。

## 3. P1 强烈建议完成

以下项目不是绝对阻塞，但会显著影响可运营性和风控能力。

### 3.1 登录与注册缺少反滥用能力

当前现状：

- [architec-cloud/src/lib/rate-limit.ts](/home/bfly/workspace/architec/architec-cloud/src/lib/rate-limit.ts) 已经为注册与登录加了基础限流
- 没有验证码
- 还没有共享存储型 rate limiting
- 还没有验证码、邮箱信誉、IP 风险、封禁名单等更强风控
- 管理后台高危动作仍缺少更严格的二次校验

建议：

- 把当前内存态限流升级为共享存储或边缘限流
- 邮箱验证前限制高频行为
- 管理后台的高危操作增加更强保护

### 3.2 Cloud 端自动化测试基本缺失

当前现状：

- 主仓库 Python 测试很多
- `architec-cloud` 已经补了一个本地 smoke 脚本：
  [architec-cloud/tools/local-smoke.sh](/home/bfly/workspace/architec/architec-cloud/tools/local-smoke.sh)
- 但仍缺少真正持续集成里的页面 / API / 浏览器级回归测试

建议：

- 把 smoke 脚本接进 CI
- 增加登录、注册、CLI 授权、设备撤销、账单跳转的自动回归
- 后续补 Playwright 或等价浏览器测试

### 3.3 客户端本地凭证存储还可以更稳

当前证据：

- [src/architec/auth/store.py](/home/bfly/workspace/architec/src/architec/auth/store.py) 已经对 `~/.architec/auth` 目录和本地凭据文件做了权限收紧
- [src/architec/auth/device.py](/home/bfly/workspace/architec/src/architec/auth/device.py) 与 [src/architec/auth/lease.py](/home/bfly/workspace/architec/src/architec/auth/lease.py) 也同步收紧了设备和公钥文件权限

建议：

- 更进一步可以考虑系统钥匙串 / OS 凭证仓
- 明确 refresh token 本地生命周期与清理策略

说明：

- 这不是公开上线前绝对阻塞
- 但对高价值用户会被问到

### 3.4 客户端默认认证地址仍是本地开发值

当前证据：

- [src/architec/auth/client.py](/home/bfly/workspace/architec/src/architec/auth/client.py) 默认 `DEFAULT_AUTH_BASE_URL = "http://127.0.0.1:8787"`

建议：

- 正式发布版必须写成生产域名
- 或者明确通过安装脚本注入生产地址
- 避免用户安装后仍指向开发默认值

### 3.5 支持与运营入口缺失

当前现状：

- [architec-cloud/src/app/support/page.tsx](/home/bfly/workspace/architec/architec-cloud/src/app/support/page.tsx) 已经补了支持说明页
- [architec-cloud/src/app/status/page.tsx](/home/bfly/workspace/architec/architec-cloud/src/app/status/page.tsx) 已经补了状态披露页
- 但仍没有真实支持邮箱、工单系统、公告发布流程和 SLA

建议：

- 最少提供真实支持邮箱
- 最好把状态页接到真实监控或公告机制
- 管理后台保留最小支持操作手册

## 4. P2 可以后置

这些项目可以在公开早期版本后逐步补齐，但越早越好。

### 4.1 下载物签名与校验页

建议：

- 每个平台产物提供 checksum
- 后续补签名校验与安装指南

### 4.2 版本最小支持策略

建议：

- 服务端拒绝过旧客户端
- 下载页提示用户升级

### 4.3 更细的设备运营能力

建议：

- 最近活跃时间筛选
- 撤销原因记录
- 审计日志导出

### 4.4 管理后台角色细分

当前现状：

- 目前只有 `isAdmin`

建议：

- 后续区分客服、运营、超级管理员

## 5. 如果你现在就想上线，现实可行的分阶段方案

### 阶段 A：封闭内测

可接受条件：

- 当前云端仍可部分开发态
- Stripe 可以先不开
- 分发给极少量可信用户

必须补：

- 最基础部署与备份
- 真实支持邮箱
- 本地 smoke 校验纳入每次发版流程

### 阶段 B：公开免费试用

必须补：

- 真实 Auth / DB
- 邮箱验证与找回
- 正式下载物
- 监控与错误上报
- 法律文本正式审阅版

### 阶段 C：公开收费上线

必须补：

- Stripe 真接入
- 订阅生命周期联调完成
- 支付失败 / 取消 / 退款规则明确
- 账单支持流程明确
- 客户端分发和更新链路成型

## 6. 建议的执行顺序

推荐顺序：

1. 把云端身份系统切到真实 Auth + DB
2. 补邮箱验证、密码重置、账户恢复
3. 做正式客户端下载与版本分发
4. 补监控、日志、备份、支持邮箱与公告机制
5. 完成法律文本正式审阅
6. 再打开真实 Stripe 收费
7. 最后补更强的下载保护、版本约束、风控增强

## 7. 当前一句话判断

当前项目已经接近“产品化原型完成”，但还没有达到“可公开收费上线”。

最关键的不是继续堆页面，而是把下面四件事从开发态切成生产态：

- 身份系统
- 法律与运营
- 客户端分发
- 监控与部署
