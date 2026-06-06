"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { spawnSync } = require("node:child_process");
const { pathToFileURL } = require("node:url");
const {
  VERSION,
  assetNameFor,
  checksumFileName,
  platformTriplet,
} = require("../lib/archi-dispatcher");

function sha256(filePath) {
  return crypto.createHash("sha256").update(fs.readFileSync(filePath)).digest("hex");
}

function fail(message, result) {
  console.error(message);
  if (result) {
    if (result.stdout) {
      console.error(result.stdout);
    }
    if (result.stderr) {
      console.error(result.stderr);
    }
  }
  process.exit(1);
}

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "architec-npm-smoke-"));
try {
  const releaseDir = path.join(tmp, "release");
  const llmgatewayDir = path.join(tmp, "home", ".llmgateway");
  const llmgatewayConfig = path.join(llmgatewayDir, "config.yaml");
  fs.mkdirSync(releaseDir, { recursive: true });
  const triplet = platformTriplet();
  const assetName = assetNameFor(triplet);
  const assetPath = path.join(releaseDir, assetName);
  fs.writeFileSync(
    assetPath,
    `#!/usr/bin/env node\nconsole.log("archi ${VERSION}")\n`,
    { mode: 0o755 },
  );
  fs.writeFileSync(
    path.join(releaseDir, checksumFileName()),
    `${sha256(assetPath)}  ${assetName}\n`,
  );

  const result = spawnSync(
    process.execPath,
    [path.join(__dirname, "..", "bin", "archi.js"), "--version"],
    {
      encoding: "utf8",
      env: {
        ...process.env,
        ARCHI_NPM_CACHE_DIR: path.join(tmp, "cache"),
        ARCHI_NPM_RELEASE_BASE_URL: pathToFileURL(`${releaseDir}${path.sep}`).href,
        LLMGATEWAY_USER_CONFIG_DIR: llmgatewayDir,
      },
    },
  );

  if (result.status !== 0) {
    fail("dispatcher smoke test failed", result);
  }
  const output = String(result.stdout || "").trim();
  if (output !== `archi ${VERSION}`) {
    fail(`unexpected dispatcher output: ${output}`, result);
  }
  if (!fs.existsSync(llmgatewayConfig)) {
    fail("dispatcher did not create starter llmgateway config");
  }
  const starter = fs.readFileSync(llmgatewayConfig, "utf8");
  for (const needle of [
    "providers:",
    "provider_type:",
    "api_style:",
    "base_url:",
    "api_key:",
    "headers:",
    "model_map:",
    "Optional fallback provider example",
    "ARCHITEC_LLM_SECONDARY_BASE_URL",
    "fallback_model:",
    "strong_model:",
    "weak_model:",
    "strong_reasoning_effort:",
    "weak_reasoning_effort:",
    "max_concurrent:",
    "retry_max:",
    "transport_retries:",
    "timeout:",
  ]) {
    if (!starter.includes(needle)) {
      fail(`starter llmgateway config missing ${needle}`);
    }
  }

  const sentinel = "sentinel: keep-this-file-byte-for-byte\n";
  fs.writeFileSync(llmgatewayConfig, sentinel);
  const preserveResult = spawnSync(
    process.execPath,
    [path.join(__dirname, "..", "bin", "archi.js"), "--version"],
    {
      encoding: "utf8",
      env: {
        ...process.env,
        ARCHI_NPM_CACHE_DIR: path.join(tmp, "cache"),
        ARCHI_NPM_RELEASE_BASE_URL: pathToFileURL(`${releaseDir}${path.sep}`).href,
        LLMGATEWAY_USER_CONFIG_DIR: llmgatewayDir,
      },
    },
  );
  if (preserveResult.status !== 0) {
    fail("dispatcher preserve-config smoke test failed", preserveResult);
  }
  if (fs.readFileSync(llmgatewayConfig, "utf8") !== sentinel) {
    fail("dispatcher changed an existing llmgateway config");
  }

  fs.rmSync(llmgatewayDir, { recursive: true, force: true });
  const postinstallResult = spawnSync(
    process.execPath,
    [path.join(__dirname, "postinstall.js")],
    {
      encoding: "utf8",
      env: {
        ...process.env,
        LLMGATEWAY_USER_CONFIG_DIR: llmgatewayDir,
      },
    },
  );
  if (postinstallResult.status !== 0) {
    fail("postinstall config smoke test failed", postinstallResult);
  }
  const postinstallStderr = String(postinstallResult.stderr || "");
  if (
    !postinstallStderr.includes("project: https://github.com/SeemSeam/architec") ||
    !postinstallStderr.includes("more info: https://github.com/SeemSeam/architec#readme")
  ) {
    fail("postinstall did not print GitHub project/more-info links", postinstallResult);
  }
  if (!fs.existsSync(llmgatewayConfig)) {
    fail("postinstall did not create starter llmgateway config");
  }
} finally {
  fs.rmSync(tmp, { recursive: true, force: true });
}
