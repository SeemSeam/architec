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
  const binaryPath = await ensureBinary();
  return runBinary(binaryPath, args);
}

module.exports = {
  VERSION,
  assetNameFor,
  checksumFileName,
  ensureBinary,
  main,
  parseChecksums,
  platformTriplet,
};
