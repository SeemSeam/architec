# npm Release Notes

`@seemseam/archi` is the primary binary dispatcher for the Architec CLI. It is not a
Node.js rewrite and it must not bundle the Python source trees for `architec`,
`seemseam_hippos`, or `seemseam_llmgateway`.

## Package Identity

- primary npm package: `@seemseam/archi`
- compatibility npm package: `@seemseam/architec`
- CLI command: `archi`
- npm version: must match the released Architec version on PyPI and the
  GitHub tag, for example `<version>` and `v<version>`
- source package: PyPI `architec`
- binary source: GitHub Release standalone `archi` assets

The unscoped npm package `architec` is owned by someone else and is not used.
The scoped package syntax is `@seemseam/archi`; `seemseam@archi` is not a valid
npm package name for this project.

`@seemseam/architec` remains available only as a compatibility shim. New users
should install:

```bash
npm install -g @seemseam/archi
```

## Dispatcher Strategy

The npm package contains a small Node.js dispatcher. On first run it:

1. maps the current OS/CPU to a release asset name;
2. downloads `archi-v<version>-checksums.txt` from the matching GitHub Release;
3. downloads the matching `archi-v<version>-<platform>` binary;
4. verifies the SHA-256 checksum before caching the binary;
5. executes the cached binary on later runs.

The npm package intentionally exposes only the `archi` bin. The standalone
binary must bundle Hippos for internal refresh operations; llmgateway is used as
a library dependency and is not exposed as a separate npm command. Users who
need to run the Hippos CLI directly should install `seemseam-hippos` from PyPI.

Default release URL:

```text
https://github.com/SeemSeam/architec/releases/download/v<version>/
```

The first npm release gate requires these assets for the selected platform
matrix:

```text
archi-v<version>-linux-x64
archi-v<version>-darwin-x64
archi-v<version>-darwin-arm64
archi-v<version>-win32-x64.exe
archi-v<version>-checksums.txt
```

`linux-arm64` is supported by the dispatcher if an asset exists, but it is not
part of the default first-release gate until a real Linux arm64 build runner and
smoke test are selected.

## Local Verification

```bash
npm test
npm run pack:dry-run
ARCHITEC_NPM_REQUIRED_TRIPLETS=linux-x64 npm run release-assets:check
```

The dispatcher smoke test uses a local file URL fixture and does not contact
GitHub. `release-assets:check` contacts GitHub and fails until the matching
GitHub Release binary assets and checksum file exist.

## Trusted Publishing

Configure npm Trusted Publishing for the existing package:

```text
Provider: GitHub Actions
Organization or user: SeemSeam
Repository: architec
Workflow filename: npm.yml
Environment name: <blank>
Allowed actions: npm publish
```

Configure the same Trusted Publisher fields for both `@seemseam/archi` and
`@seemseam/architec`. The workflow input selects which package is published:

- `package=archi` publishes the primary root package.
- `package=architec-shim` publishes `npm/architec-shim`.

The workflow must exist at `.github/workflows/npm.yml`, use a GitHub-hosted
runner, use Node 24 with npm 11.5.1 or newer, set `permissions:
id-token: write`, and publish without `NODE_AUTH_TOKEN`.

## Release Order

1. Publish `architec` to PyPI.
2. Build standalone `archi` binaries from the released PyPI package set.
3. Upload binaries and `archi-v<version>-checksums.txt` to the matching GitHub
   Release.
4. Verify `npm test`, `npm pack --dry-run`, and `release-assets:check`.
5. Publish `@seemseam/archi@<version>` through npm Trusted Publishing.
6. Publish `@seemseam/architec@<version>` as a compatibility shim after
   `@seemseam/archi@<version>` is visible on npm.
7. Deprecate old `@seemseam/architec` versions with a migration message after
   the shim is verified.
