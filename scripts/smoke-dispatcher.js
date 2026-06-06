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
        ARCHITEC_NPM_CACHE_DIR: path.join(tmp, "cache"),
        ARCHITEC_NPM_RELEASE_BASE_URL: pathToFileURL(`${releaseDir}${path.sep}`).href,
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
} finally {
  fs.rmSync(tmp, { recursive: true, force: true });
}
