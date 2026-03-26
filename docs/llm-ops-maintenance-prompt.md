# Architec LLM 运维维护提示词

这份文档的目标不是给人类读长篇背景，而是给新的 LLM 会话快速注入上下文，让模型能直接进入 `Architec` 当前项目的维护、排障、发布和上线工作。

适用时间点：

- 当前仓库状态
- 当前线上域名与服务器状态
- 当前 CLI 授权链路状态

最后人工确认时间：

- `2026-03-26`

## 1. 使用方式

如果你要让新的 LLM 接手当前项目，建议把下面两部分一起提供：

1. 本文档全文
2. 当前仓库根目录路径

推荐启动语句：

```text
你现在接手 Architec 项目的持续维护。请先严格阅读 docs/llm-ops-maintenance-prompt.md，然后基于该文档作为当前事实来源执行。除非我明确要求，否则不要重做已验证通过的链路；优先延续现有部署、授权、发布和网站结构。
```

## 2. 项目一句话定义

`Architec` 是一个本地运行的 Python CLI 架构分析工具，用于给 `Codex / Claude / 终端工作流` 提供自动架构分析、管理与优化能力；`architec-cloud` 是它的注册、登录、设备授权、下载入口和控制面网站。

## 3. 当前仓库与角色边界

当前工作区现在拆成三个同级仓库：

- `/home/bfly/workspace/architec`
  负责 CLI、本地分析、授权会话、本地 skill 工作流
- `/home/bfly/workspace/architec-cloud`
  负责网站、注册、登录、设备授权、控制面页面、CLI 授权 API
- `/home/bfly/workspace/architec-release`
  负责 release 资产、安装器、打包与发布流程

发布与分发边界：

- 网站负责注册、登录、授权、下载入口、账户管理
- `architec-release` 负责构建和管理安装包、校验值、安装脚本
- 网站提供 `/downloads/latest/*` 对外分发入口

不要再把 `architec-cloud` 或 `architec-release` 当成 `architec` 仓库内的子目录。

## 4. 当前线上事实

正式域名：

- `https://www.architec.top`
- `https://architec.top`

当前生产主机：

- 主机 IP：`38.71.116.190`
- SSH 端口：`20208`
- 远端 systemd 服务名：`architec-cloud`
- 远端应用目录：`/srv/architec-cloud`
- 远端数据目录：`/var/lib/architec-cloud`

当前 DNS：

- `architec.top -> 38.71.116.190`
- `www.architec.top -> 38.71.116.190`

当前网站进程形态：

- `nginx` 对外提供 `80/443`
- `architec-cloud` 用 `next start` 监听 `127.0.0.1:3000`
- `nginx` 反代到 `127.0.0.1:3000`

重要兼容信息：

- 美服上的 `xray` 已经从 `443` 移到 `24443`
- 原因是给 HTTPS 网站让出 `443`
- 如果再碰代理/站点冲突，优先检查这个端口边界

## 5. 当前已经跑通的链路

以下链路已经实际验证通过：

1. 线上网站可访问
2. CLI 浏览器授权链路已跑通
3. `archi login -> 浏览器授权 -> 本地 127.0.0.1 回调 -> 本地 session 写入` 已跑通
4. `archi whoami --json` 已返回正常身份
5. `archi status --json` 已返回 `authenticated: true`
6. `/account` 页面此前报过前端异常，但已经通过“重启远端服务”解决

关键经验：

- 远端文件同步成功，不代表线上已更新
- 如果 `architec-cloud` 没重启，Next.js 可能还在跑旧代码
- 当前远端部署脚本已经改成默认自动重启服务

## 6. 当前授权模型

当前推荐且已启用的授权方式：

- 纯浏览器回调授权

当前 CLI 行为：

- `archi login` 默认直接走浏览器授权
- 不再提示用户手动输入激活码作为主路径
- 浏览器授权完成后，网站会把短期授权码回传到本地 `127.0.0.1` 回调服务

本地回调说明：

- CLI 会在本机启动一个本地 HTTP callback server
- 地址形如：`http://127.0.0.1:46319/callback`
- 这不是网站，是本地 CLI 临时开启的接码口

不要误判：

- 浏览器里看到 `127.0.0.1` 是正常设计
- 只要终端最后输出 `Architec login OK`，说明链路是成功的

## 7. 浏览器自动化测试的特殊坑

如果用浏览器自动化工具调试 `archi login`：

- 工具所在容器/沙箱里的 `127.0.0.1`，不一定等于当前主机的 `127.0.0.1`
- 所以浏览器自动化里直接点完授权，可能打不开本机回调页
- 这不代表真实用户链路失败

可靠验证方式：

- 对真实本机用户：直接用本地浏览器
- 对自动化工具：可以走半自动
  - 浏览器完成登录与授权
  - 再让本机 shell 命中本地回调 URL

## 8. 本机运行基线

当前机器上的真实验收路径应固定为：

- 先在开发仓改代码
- 再发布到服务器 / 公网安装入口
- 然后从服务器提供的安装脚本重新安装到本机
- 最后再做本机闭环测试

当前本机期望的运行来源是：

- `archi -> ~/.local/bin/archi`
- `hippo -> ~/.local/bin/hippo`
- `hippocampus / llmgateway -> ~/.local/lib/python*/site-packages`

这表示：

- 本机验收测试应基于“已发布安装物”
- 不应再通过开发工作区源码直接覆盖本机运行结果
- 不应把 `pip install -e` 作为 `archi / hippo / llmgateway` 的默认测试路径

只有在明确做源码级单元测试或局部调试时，才允许直接从源码环境运行；但那不算发布验收。

## 9. `llmgateway` / `hippocampus` / `archi` 维护原则

这三个组件现在统一遵守同一条规则：

- 先在各自开发仓修改源码
- 再发布到服务器可访问的安装入口
- 再从服务器安装到当前机器
- 最后才做真实使用测试

默认不要做这些事：

- 不要为了验收而执行 `python3 -m pip install -e .`
- 不要为了验收而直接从本地 checkout 安装 `hippocampus`
- 不要为了验收而直接从本地 checkout 安装 `llmgateway`

验收优先级：

1. 网站公开安装脚本 / 服务器安装入口
2. GitHub Releases 已发布产物
3. 本地源码运行仅用于开发调试，不作为验收结论

当前产品链路事实：

- 生产安装脚本会自动安装 `llmgateway` 和 `hippocampus`
- 公开安装入口以网站 `/downloads/latest/install_prod.sh` 为主
- 如网站镜像入口异常，可回退到 GitHub Releases，但验收结论仍应基于“已发布产物”

## 10. 当前最重要的命令

### 10.1 本机真实安装 / 重装

```bash
curl -fsSL https://www.architec.top/downloads/latest/install_prod.sh -o install_prod.sh
bash install_prod.sh
```

如果要验证刚发布的新版本，先重新下载安装，再继续下面的登录和功能测试。

### 10.2 CLI 本地登录测试

```bash
archi login
archi whoami --json
archi status --json
```

### 10.3 本地 release smoke

```bash
cd /home/bfly/workspace/architec-release
bash tools/release_install_smoke.sh
```

这条命令会尽量跑一条接近真实用户的闭环，并且应优先验证“发布安装物”而不是开发态源码。

### 10.4 网站本地 build

```bash
cd /home/bfly/workspace/architec-cloud
pnpm build
```

### 10.5 远端部署

当前推荐直接使用：

```bash
cd /home/bfly/workspace/architec-cloud
ARCHITEC_CLOUD_REMOTE='root@38.71.116.190' \
ARCHITEC_CLOUD_SSH_PORT=20208 \
bash tools/deploy_architec_cloud_remote.sh
```

当前脚本默认行为：

- 本地 build
- 同步到远端
- 远端 `pnpm install && pnpm build`
- 默认自动 `systemctl restart architec-cloud`
- 自动等待 `127.0.0.1:3000` 就绪
- 打印健康检查结果

如果明确不想自动重启：

```bash
cd /home/bfly/workspace/architec-cloud
ARCHITEC_CLOUD_REMOTE='root@38.71.116.190' \
ARCHITEC_CLOUD_SSH_PORT=20208 \
ARCHITEC_CLOUD_RESTART_SERVICE=0 \
bash tools/deploy_architec_cloud_remote.sh
```

### 10.6 远端人工检查

```bash
ssh -p 20208 root@38.71.116.190
systemctl status architec-cloud --no-pager
curl -I http://127.0.0.1:3000
curl -I https://www.architec.top
```

## 11. 当前关键文件

CLI 授权主逻辑：

- [src/architec/auth/commands.py](/home/bfly/workspace/architec/src/architec/auth/commands.py)
- [src/architec/cli.py](/home/bfly/workspace/architec/src/architec/cli.py)

网站账户页与控制面：

- [account/page.tsx](/home/bfly/workspace/architec-cloud/src/app/account/page.tsx)
- [account-dashboard-client.tsx](/home/bfly/workspace/architec-cloud/src/app/account/account-dashboard-client.tsx)
- [login/page.tsx](/home/bfly/workspace/architec-cloud/src/app/cli/login/page.tsx)
- [authorize/route.ts](/home/bfly/workspace/architec-cloud/src/app/api/cli/authorize/route.ts)

网站运行配置：

- [config.ts](/home/bfly/workspace/architec-cloud/src/lib/config.ts)
- [architec-cloud.service](/home/bfly/workspace/architec-cloud/deploy/systemd/architec-cloud.service)
- [deploy_architec_cloud_remote.sh](/home/bfly/workspace/architec-cloud/tools/deploy_architec_cloud_remote.sh)

发布与安装：

- [install_prod.sh](/home/bfly/workspace/architec-release/tools/install_prod.sh)
- [release-sop.md](/home/bfly/workspace/architec-release/docs/release-sop.md)
- [docs/github-releases.md](/home/bfly/workspace/architec/docs/github-releases.md)

## 12. 当前网站定位

当前网站逻辑已经收敛为：

- 首页：产品介绍 + 安装入口
- 登录页
- 注册页
- 使用说明页
- 账户页
- 设备页
- CLI 授权页

当前网站不承担这些职责：

- 不托管源码
- 不做复杂 SaaS 后台
- 不做大规模公网多实例架构

当前更准确的定位是：

- 控制面网站
- 注册/登录/授权中心
- 下载入口与安装说明站

## 13. 当前已知限制

当前 `architec-cloud` 仍然是单实例 JSON 状态版：

- 用户、会话、设备、授权码、refresh token 存在 JSON 文件
- 适合内测、小流量、灰度
- 不适合现在就多实例横向扩容

当前仍未完成的正式生产化项：

- 正式数据库
- 正式认证系统
- 邮件验证/找回密码
- 审计日志
- 自动备份
- Stripe 实盘

所以当前最合理策略仍是：

- 先作为小规模控制面稳定运行
- 不要假装已经是完整的正式 SaaS

## 14. 安全边界

不要把以下内容写进仓库或提示词：

- SSH 密码
- 私钥
- API key
- `.env.production` 的真实敏感值
- 用户个人密钥材料

可以写进提示词的内容：

- 服务器 IP
- SSH 端口
- 服务名
- 目录路径
- 域名
- 部署命令
- 非敏感运维流程

如果 LLM 需要真正上线操作，应让操作者在运行时提供：

- 当前可用 SSH 凭据
- 当前生产环境变量
- 当前签名密钥材料

## 15. LLM 接手时的推荐工作顺序

新的 LLM 会话接手时，推荐固定按这个顺序：

1. 阅读本文件
2. 确认当前工作区路径是 `/home/bfly/workspace/architec`
3. 确认是否在处理：
   - CLI
   - 网站
   - 远端部署
   - 发布
4. 如果涉及线上改动，先检查：
   - 域名是否仍指向 `38.71.116.190`
   - `architec-cloud` 服务是否在跑
   - `/account` 和 `/cli/login` 是否正常
5. 如果涉及 `archi / hippo / llmgateway` 的可用性，优先确认：
   - 当前机器是否已通过服务器安装而不是源码直装
   - 当前命令是否来自 `~/.local/bin`
   - 当前包是否来自已发布产物
6. 如果涉及 CLI 授权，优先验证：
   - `archi login`
   - `archi whoami --json`
   - `archi status --json`
7. 如果涉及网站发布，优先使用远端部署脚本，而不是手工 rsync 后忘记重启

## 16. 可直接复制给 LLM 的提示词

下面这段可以直接复制到新的 LLM 会话。

```text
你现在接手 Architec 项目的持续维护。请以 /home/bfly/workspace/architec 为工作区，并先完整阅读 docs/llm-ops-maintenance-prompt.md，把它视为当前项目事实来源。

工作边界：
- 你维护的是两个部分：本地 CLI（src/architec）和控制面网站（architec-cloud）
- 当前正式域名是 https://www.architec.top
- 当前生产主机是 38.71.116.190:20208
- 远端应用目录是 /srv/architec-cloud
- 远端数据目录是 /var/lib/architec-cloud
- 远端 systemd 服务名是 architec-cloud
- 网站通过 nginx -> 127.0.0.1:3000 反代
- xray 已从 443 挪到 24443，避免和 HTTPS 冲突

当前已知真实状态：
- archi login 的浏览器自动回调链路已经跑通
- archi whoami --json 和 archi status --json 已验证成功
- /account 页面曾因远端服务未重启而显示旧版本和前端异常，但现在已恢复
- 远端部署脚本 tools/deploy_architec_cloud_remote.sh 已改成默认自动重启服务

执行原则：
- 除非我明确要求，否则不要推翻现有授权模型
- 目前默认授权模型是纯浏览器回调，不再把激活码输入作为主流程
- 不要把密码、私钥、API key 写进仓库
- 如果你改了 architec-cloud 前端或服务端代码，部署后必须确保远端服务重启
- 对 `archi / hippo / llmgateway` 的验收，不要直接从开发源码安装到本机；必须先发布到服务器安装入口，再从服务器安装到本机测试

当你开始工作时：
1. 先判断我是在让你处理 CLI、本地测试、网站、部署还是发布
2. 如果是线上问题，先检查当前服务状态和页面是否是新版本
3. 如果是授权问题，优先复现 archi login -> whoami -> status 闭环
4. 如果是部署问题，优先使用现成脚本，不要手工同步后遗漏重启

在没有明确新目标前，你的默认关注点是：
- 保持 CLI 授权链路稳定
- 保持网站登录/注册/账户页稳定
- 保持发布和部署流程可重复
- 保持“开发源码 -> 发布到服务器 -> 从服务器安装到本机 -> 再测试”的路径不被破坏
```

## 17. 文档维护规则

后续只要下面任一事项变化，就应更新这份文档：

- 线上服务器
- 域名
- 部署命令
- 授权链路
- 发布流程
- 依赖安装逻辑
- 本机验收安装路径
- 网站结构
- 重要已知坑

不要把它写成理想方案文档；这份文档只记录“当前真实可用状态”和“LLM 接手时必须知道的事实”。
