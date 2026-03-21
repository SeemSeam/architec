# GitHub Releases 操作说明

当前发布策略：

- 网站只负责注册、登录、座位控制、浏览器授权
- GitHub 只负责发布安装包和校验文件
- 当前发布仓库建议使用：`bfly123/architec-releases`

## 1. 本地构建产物

在源码仓库根目录执行：

```bash
python3 tools/build_release.py
```

默认会生成：

- `dist/architec-<version>-py3-none-any.whl`
- `dist/architec-<version>.tar.gz`
- `dist/SHA256SUMS.txt`
- `dist/RELEASE_NOTES.md`

如果要同时生成“隐藏源码优先”的编译发布物，执行：

```bash
python3 tools/build_release.py --with-nuitka
```

这会额外产出：

- `dist/archi-linux-x86_64.tar.gz`

命名规则已经统一为：

- `archi-<os>-<arch>.tar.gz`
- `archi-<os>-<arch>.zip`

当前约定：

- Linux / macOS 使用 `.tar.gz`
- Windows 使用 `.zip`
- `os` 使用 `linux` / `macos` / `windows`
- `arch` 使用 `x86_64` / `arm64`

## 2. 首次创建发布仓库

```bash
gh repo create bfly123/architec-releases --public --description "Release artifacts for Architec" --clone=false
```

说明：

- 这个仓库可以只存放 release 资产和简短说明
- 不需要把完整源码仓库公开推上去

## 3. 创建一个 release

```bash
VERSION="$(python3 - <<'PY'
import tomllib
from pathlib import Path

payload = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
print(payload["project"]["version"])
PY
)"

TAG="v${VERSION}"

gh release create "${TAG}" \
  "dist/architec-${VERSION}-py3-none-any.whl" \
  "dist/architec-${VERSION}.tar.gz" \
  "dist/archi-linux-x86_64.tar.gz" \
  "dist/SHA256SUMS.txt" \
  "tools/install_prod.sh" \
  --repo bfly123/architec-releases \
  --title "Architec ${TAG}" \
  --notes-file dist/RELEASE_NOTES.md
```

如果 release 已存在，覆盖上传：

```bash
VERSION="$(python3 - <<'PY'
import tomllib
from pathlib import Path

payload = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
print(payload["project"]["version"])
PY
)"

TAG="v${VERSION}"

gh release upload "${TAG}" \
  "dist/architec-${VERSION}-py3-none-any.whl" \
  "dist/architec-${VERSION}.tar.gz" \
  "dist/archi-linux-x86_64.tar.gz" \
  "dist/SHA256SUMS.txt" \
  "tools/install_prod.sh" \
  --clobber \
  --repo bfly123/architec-releases
```

如果你要直接从当前源码仓库一键发布：

```bash
ARCHITEC_VERSION_TAG="${TAG}" \
bash tools/publish_release.sh
```

`tools/publish_release.sh` 现在会自动：

- 从 `pyproject.toml` 读取版本号
- 构建 wheel、sdist、Linux 编译包
- 校验资产是否齐全
- 自动上传 `dist/` 下所有 `archi-*.tar.gz` 和 `archi-*.zip` 编译产物
- 创建或覆盖 GitHub release
- 用 `dist/RELEASE_NOTES.md` 更新 release body

## 3.1 自动发布

仓库已提供：

- `.github/workflows/publish-release.yml`
- `.github/workflows/validate-release-matrix.yml`
- `tools/publish_release.sh`

当前 workflow 结构：

- `validate-release-matrix`：只做多平台编译验证，不发布 release
- `build-compiled`：矩阵构建编译产物
- `publish`：汇总下载各平台产物，生成 wheel / sdist / checksums，然后统一发布到 GitHub Releases

当前矩阵目标：

- `linux-x86_64`
- `macos-arm64`
- `windows-x86_64`

推荐使用顺序：

1. 先触发 `validate-release-matrix`
2. 确认三平台 runner 都能产出编译包
3. 再触发 `publish-release`

前置条件：

- 把当前源码仓库推到你自己的 GitHub 仓库
- 在源码仓库里配置 secret：`ARCHITEC_RELEASES_TOKEN`
- 这个 token 需要对 `bfly123/architec-releases` 具备写入 release 的权限

触发方式：

- 推送 tag，例如 `v0.1.1`
- 或手动运行 workflow dispatch

## 3.2 本地验证

建议每次发版前至少跑以下命令：

```bash
bash -n tools/publish_release.sh
python3 tools/build_release.py --with-nuitka

cd architec-cloud
pnpm build
pnpm test:e2e
```

当前这套验证已经在本地跑通过：

- `bash -n tools/publish_release.sh`
- `pnpm build`
- `pnpm test:e2e`

安装器验证也已经补齐：

- `bash -n tools/install_prod.sh`
- `bash tools/install_prod.sh --help`
- `bash tools/install_prod.sh --version v0.2.0`
- 安装完成后验证 `/tmp/.../archi --help` 与 `/tmp/.../archi login --help`

## 4. 网站配置

注册站需要指向发布仓库，而不是源码仓库：

```env
ARCHITEC_CLOUD_GITHUB_REPO_URL=https://github.com/bfly123/architec-releases
ARCHITEC_CLOUD_GITHUB_RELEASES_URL=https://github.com/bfly123/architec-releases/releases
ARCHITEC_CLOUD_GITHUB_LATEST_RELEASE_URL=https://github.com/bfly123/architec-releases/releases/latest
ARCHITEC_CLOUD_GITHUB_LATEST_LINUX_X64_URL=https://github.com/bfly123/architec-releases/releases/latest/download/archi-linux-x86_64.tar.gz
ARCHITEC_CLOUD_GITHUB_LATEST_INSTALL_SCRIPT_URL=https://github.com/bfly123/architec-releases/releases/latest/download/install_prod.sh
ARCHITEC_CLOUD_GITHUB_LATEST_CHECKSUMS_URL=https://github.com/bfly123/architec-releases/releases/latest/download/SHA256SUMS.txt
ARCHITEC_CLOUD_CLI_MIN_VERSION=0.2.0
```

下载页当前推荐顺序：

- `Download Linux Build`
- `Download Install Script`
- `Open GitHub Releases`

## 4.1 安装脚本行为

`tools/install_prod.sh` 当前支持：

- `--version <tag|latest>`
- `--repo <owner/name>`
- `--install-base <path>`
- `--bin-dir <path>`
- `--os <name>`
- `--arch <name>`
- `--asset-name <name>`
- `--skip-checksum`

默认行为：

- 自动解析目标 release tag
- 自动把当前平台标准化到 `linux` / `macos` / `windows` 与 `x86_64` / `arm64`
- 自动选择 `tar.gz` 或 `zip` 资产名
- 自动下载编译包和 `SHA256SUMS.txt`
- 默认执行 SHA256 校验
- 校验通过后再解压与创建 `archi` 软链接

推荐安装方式：

```bash
curl -fsSL https://github.com/bfly123/architec-releases/releases/latest/download/install_prod.sh -o install_prod.sh
bash install_prod.sh
```

指定版本安装：

```bash
bash install_prod.sh --version v0.2.0
```

如果你明确要跳过校验：

```bash
bash install_prod.sh --skip-checksum
```

不建议默认跳过 checksum。

当前实际能力边界：

- 安装器已经支持未来的多平台命名和解压逻辑
- 当前 GitHub workflow 仍只在 `ubuntu-latest` 上构建 Linux 编译包
- macOS / Windows 产物仍需要分别在对应 runner 上补齐

网站职责边界：

- 负责注册、登录、试用、seat、设备授权、撤销
- 负责控制最低支持 CLI 版本
- 不负责托管安装包
- 下载文件统一交给 GitHub Releases

## 5. 当前限制

当前 wheel 和 sdist 仍然包含 Python 代码，因此：

- 已经具备 GitHub Releases 分发能力
- 只有编译产物才能明显提高源码暴露门槛

当前建议下载优先级：

1. `archi-linux-x86_64.tar.gz`
2. `architec-<version>-py3-none-any.whl`
3. `architec-<version>.tar.gz`

当前 Linux 编译包说明：

- 已验证 `archi --help` 与 `archi login --help` 可启动
- 已包含 `config/` 与 `prompts/` 运行资源
- 当前显式排除了 `litellm` 路径，避免把 `torch` / `matplotlib` / Qt 生态打进发布包
- 因此编译版更适合直接 HTTP provider 路由，不适合作为 `litellm` 全量兼容包

如果要继续提高破解成本，下一步应切到：

- macOS / Windows 也补齐 Nuitka 或等价编译产物
- 每平台独立打包
- 签名与 checksum 页面
- 最低版本策略
