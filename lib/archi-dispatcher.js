"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const http = require("node:http");
const https = require("node:https");
const os = require("node:os");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { fileURLToPath } = require("node:url");

const PACKAGE_ROOT = path.resolve(__dirname, "..");
const PACKAGE_JSON = JSON.parse(
  fs.readFileSync(path.join(PACKAGE_ROOT, "package.json"), "utf8"),
);
const VERSION = PACKAGE_JSON.version;
const OWNER = "SeemSeam";
const REPO = "architec";
const SUPPORTED_TRIPLETS = new Set([
  "linux-x64",
  "linux-arm64",
  "darwin-x64",
  "darwin-arm64",
  "win32-x64",
]);

function fail(message) {
  throw new Error(message);
}

function platformTriplet(platform = process.platform, arch = process.arch) {
  const mappedArch = arch === "x64" || arch === "arm64" ? arch : "";
  if (!mappedArch) {
    fail(`unsupported CPU architecture: ${arch}`);
  }
  if (platform === "linux" || platform === "darwin") {
    return `${platform}-${mappedArch}`;
  }
  if (platform === "win32" && mappedArch === "x64") {
    return "win32-x64";
  }
  fail(`unsupported platform: ${platform}-${arch}`);
}

function assetNameFor(triplet, version = VERSION) {
  if (!SUPPORTED_TRIPLETS.has(triplet)) {
    fail(`unsupported binary target: ${triplet}`);
  }
  const extension = triplet.startsWith("win32-") ? ".exe" : "";
  return `archi-v${version}-${triplet}${extension}`;
}

function checksumFileName(version = VERSION) {
  return `archi-v${version}-checksums.txt`;
}

function defaultCacheBase() {
  if (process.platform === "win32") {
    return (
      process.env.LOCALAPPDATA ||
      path.join(os.homedir(), "AppData", "Local")
    );
  }
  if (process.platform === "darwin") {
    return path.join(os.homedir(), "Library", "Caches");
  }
  return process.env.XDG_CACHE_HOME || path.join(os.homedir(), ".cache");
}

function cacheRoot() {
  return (
    process.env.ARCHI_NPM_CACHE_DIR ||
    process.env.ARCHITEC_NPM_CACHE_DIR ||
    path.join(defaultCacheBase(), "architec", "npm")
  );
}

function llmGatewayConfigPath() {
  if (process.env.LLMGATEWAY_CONFIG) {
    return path.resolve(process.env.LLMGATEWAY_CONFIG);
  }
  const base =
    process.env.LLMGATEWAY_USER_CONFIG_DIR ||
    path.join(os.homedir(), ".llmgateway");
  return path.join(base, "config.yaml");
}

function starterLlmGatewayConfig() {
  return `# llmgateway config for Architec
# Installer rule: this file is created only when missing. Existing provider
# credentials are never overwritten by npm install, update, or archi startup.
#
# Fill the primary provider base_url and api_key below, or replace values with
# env references such as \${MY_LLM_API_KEY}. llmgateway supports ordered
# provider fallback through providers.
version: 1

providers:
  # Primary provider. Common api_style values: openai_chat, responses, anthropic, litellm.
  - provider_type: "openai"
    api_style: "openai_chat"
    base_url: ""  # e.g. https://your-llm-endpoint/v1
    api_key: ""
    headers: {}
    # headers example, if your provider requires extra HTTP headers:
    # headers:
    #   anthropic-version: "2023-06-01"
    model_map: {}
    # model_map example, if provider model IDs differ from Architec names:
    # model_map:
    #   gpt-5.4: openai/gpt-5.4
    #   gpt-5.4-mini: openai/gpt-5.4-mini

  # Optional fallback provider example.
  # Uncomment and fill this block to let llmgateway try a secondary API
  # source after primary transport failures.
  # - provider_type: openai
  #   api_style: openai_chat
  #   base_url: \${ARCHITEC_LLM_SECONDARY_BASE_URL}
  #   api_key: \${ARCHITEC_LLM_SECONDARY_API_KEY}
  #   headers: {}
  #   model_map:
  #     gpt-5.4: secondary-provider-strong-model
  #     gpt-5.4-mini: secondary-provider-fast-model

settings:
  fallback_model: "gpt-5.4-mini"
  strong_model: "gpt-5.4"
  weak_model: "gpt-5.4-mini"
  strong_reasoning_effort: "high"
  weak_reasoning_effort: "low"
  max_concurrent: 4
  retry_max: 2
  transport_retries: 2
  timeout: 120
`;
}

function ensureLlmGatewayConfig(options = {}) {
  if (
    process.env.ARCHI_NPM_SKIP_CONFIG === "1" ||
    process.env.ARCHITEC_NPM_SKIP_CONFIG === "1"
  ) {
    return { created: false, skipped: true, path: llmGatewayConfigPath() };
  }

  const configPath = llmGatewayConfigPath();
  if (fs.existsSync(configPath)) {
    return { created: false, path: configPath };
  }

  fs.mkdirSync(path.dirname(configPath), { recursive: true });
  let handle;
  try {
    handle = fs.openSync(configPath, "wx", 0o600);
    fs.writeFileSync(handle, starterLlmGatewayConfig(), "utf8");
  } catch (error) {
    if (error && error.code === "EEXIST") {
      return { created: false, path: configPath };
    }
    throw error;
  } finally {
    if (handle !== undefined) {
      fs.closeSync(handle);
    }
  }
  try {
    fs.chmodSync(configPath, 0o600);
  } catch {
    // Best effort on platforms/filesystems that do not support POSIX modes.
  }
  if (!options.quiet) {
    console.error(
      `archi npm dispatcher: created starter llmgateway config at ${configPath}`,
    );
  }
  return { created: true, path: configPath };
}

function releaseBaseUrl() {
  return (
    process.env.ARCHI_NPM_RELEASE_BASE_URL ||
    process.env.ARCHITEC_NPM_RELEASE_BASE_URL ||
    `https://github.com/${OWNER}/${REPO}/releases/download/v${VERSION}/`
  );
}

function joinUrl(base, name) {
  const normalized = base.endsWith("/") ? base : `${base}/`;
  return new URL(name, normalized).toString();
}

function sha256File(filePath) {
  return new Promise((resolve, reject) => {
    const hash = crypto.createHash("sha256");
    const stream = fs.createReadStream(filePath);
    stream.on("data", (chunk) => hash.update(chunk));
    stream.on("error", reject);
    stream.on("end", () => resolve(hash.digest("hex")));
  });
}

function request(url, redirects = 0) {
  return new Promise((resolve, reject) => {
    const parsed = new URL(url);
    const client = parsed.protocol === "http:" ? http : https;
    const req = client.get(
      parsed,
      {
        headers: {
          "User-Agent": `${PACKAGE_JSON.name}/${VERSION}`,
        },
      },
      (res) => {
        if (
          res.statusCode >= 300 &&
          res.statusCode < 400 &&
          res.headers.location
        ) {
          res.resume();
          if (redirects >= 5) {
            reject(new Error(`too many redirects while fetching ${url}`));
            return;
          }
          resolve(request(new URL(res.headers.location, url).toString(), redirects + 1));
          return;
        }
        if (res.statusCode !== 200) {
          res.resume();
          reject(new Error(`HTTP ${res.statusCode} while fetching ${url}`));
          return;
        }
        resolve(res);
      },
    );
    req.on("error", reject);
  });
}

async function readUrl(url) {
  const parsed = new URL(url);
  if (parsed.protocol === "file:") {
    return fs.promises.readFile(fileURLToPath(parsed));
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    fail(`unsupported URL protocol: ${parsed.protocol}`);
  }
  const res = await request(url);
  const chunks = [];
  for await (const chunk of res) {
    chunks.push(chunk);
  }
  return Buffer.concat(chunks);
}

async function downloadUrl(url, targetPath) {
  const parsed = new URL(url);
  if (parsed.protocol === "file:") {
    await fs.promises.copyFile(fileURLToPath(parsed), targetPath);
    return;
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    fail(`unsupported URL protocol: ${parsed.protocol}`);
  }
  const res = await request(url);
  await new Promise((resolve, reject) => {
    const stream = fs.createWriteStream(targetPath, { mode: 0o755 });
    res.pipe(stream);
    res.on("error", reject);
    stream.on("error", reject);
    stream.on("finish", resolve);
  });
}

function parseChecksums(text) {
  const checksums = new Map();
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) {
      continue;
    }
    const parts = trimmed.split(/\s+/);
    if (parts.length < 2) {
      continue;
    }
    if (/^[a-fA-F0-9]{64}$/.test(parts[0])) {
      checksums.set(parts[1].replace(/^\*/, ""), parts[0].toLowerCase());
    } else if (/^[a-fA-F0-9]{64}$/.test(parts[1])) {
      checksums.set(parts[0].replace(/^\*/, ""), parts[1].toLowerCase());
    }
  }
  return checksums;
}

async function expectedChecksum(assetName) {
  const checksumUrl =
    process.env.ARCHI_NPM_CHECKSUM_URL ||
    process.env.ARCHITEC_NPM_CHECKSUM_URL ||
    joinUrl(releaseBaseUrl(), checksumFileName());
  const checksumText = (await readUrl(checksumUrl)).toString("utf8");
  const checksums = parseChecksums(checksumText);
  const expected = checksums.get(assetName);
  if (!expected) {
    fail(`checksum for ${assetName} was not found in ${checksumUrl}`);
  }
  return expected;
}

function markerMatches(markerPath, assetName, expected) {
  try {
    const marker = JSON.parse(fs.readFileSync(markerPath, "utf8"));
    return (
      marker.version === VERSION &&
      marker.assetName === assetName &&
      marker.sha256 === expected
    );
  } catch {
    return false;
  }
}

async function ensureBinary() {
  const configuredBinary =
    process.env.ARCHI_NPM_BINARY_PATH ||
    process.env.ARCHITEC_NPM_BINARY_PATH;
  if (configuredBinary) {
    const resolved = path.resolve(configuredBinary);
    if (!fs.existsSync(resolved)) {
      fail(`configured archi binary path does not exist: ${resolved}`);
    }
    return resolved;
  }

  const triplet = platformTriplet();
  const assetName = assetNameFor(triplet);
  const targetDir = path.join(cacheRoot(), VERSION, triplet);
  const targetPath = path.join(targetDir, process.platform === "win32" ? "archi.exe" : "archi");
  const markerPath = path.join(targetDir, "download.json");
  const expected = await expectedChecksum(assetName);

  if (fs.existsSync(targetPath) && markerMatches(markerPath, assetName, expected)) {
    return targetPath;
  }

  await fs.promises.mkdir(targetDir, { recursive: true });
  if (fs.existsSync(targetPath)) {
    const actual = await sha256File(targetPath);
    if (actual === expected) {
      await fs.promises.chmod(targetPath, 0o755);
      await fs.promises.writeFile(
        markerPath,
        `${JSON.stringify({ version: VERSION, assetName, sha256: expected }, null, 2)}\n`,
      );
      return targetPath;
    }
  }

  const tempPath = path.join(targetDir, `${assetName}.${process.pid}.download`);
  await downloadUrl(joinUrl(releaseBaseUrl(), assetName), tempPath);
  const actual = await sha256File(tempPath);
  if (actual !== expected) {
    await fs.promises.rm(tempPath, { force: true });
    fail(`checksum mismatch for ${assetName}: expected ${expected}, got ${actual}`);
  }
  await fs.promises.chmod(tempPath, 0o755);
  await fs.promises.rename(tempPath, targetPath);
  await fs.promises.writeFile(
    markerPath,
    `${JSON.stringify({ version: VERSION, assetName, sha256: expected }, null, 2)}\n`,
  );
  return targetPath;
}

function runBinary(binaryPath, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(binaryPath, args, {
      stdio: "inherit",
      env: process.env,
    });
    child.on("error", reject);
    child.on("exit", (code) => resolve(code === null ? 1 : code));
  });
}

async function main(args = process.argv.slice(2)) {
  try {
    ensureLlmGatewayConfig();
  } catch (error) {
    console.error(
      `archi npm dispatcher: warning: could not create starter llmgateway config: ${error.message}`,
    );
  }
  const binaryPath = await ensureBinary();
  return runBinary(binaryPath, args);
}

module.exports = {
  VERSION,
  assetNameFor,
  checksumFileName,
  ensureLlmGatewayConfig,
  ensureBinary,
  llmGatewayConfigPath,
  main,
  parseChecksums,
  platformTriplet,
  starterLlmGatewayConfig,
};
