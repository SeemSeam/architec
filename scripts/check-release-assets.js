"use strict";

const https = require("node:https");
const { URL } = require("node:url");
const {
  VERSION,
  assetNameFor,
  checksumFileName,
  parseChecksums,
} = require("../lib/archi-dispatcher");

const OWNER = "SeemSeam";
const REPO = "architec";
const DEFAULT_REQUIRED_TRIPLETS = [
  "linux-x64",
  "darwin-x64",
  "darwin-arm64",
  "win32-x64",
];

function requiredTriplets() {
  const raw =
    process.env.ARCHI_NPM_REQUIRED_TRIPLETS ||
    process.env.ARCHITEC_NPM_REQUIRED_TRIPLETS ||
    "";
  if (!raw.trim()) {
    return DEFAULT_REQUIRED_TRIPLETS;
  }
  return raw.split(",").map((value) => value.trim()).filter(Boolean);
}

function requestJson(url) {
  return request(url).then((body) => JSON.parse(body.toString("utf8")));
}

function request(url) {
  return new Promise((resolve, reject) => {
    const headers = {
      Accept: "application/vnd.github+json",
      "User-Agent": `@seemseam/archi/${VERSION}`,
    };
    if (process.env.GITHUB_TOKEN) {
      headers.Authorization = `Bearer ${process.env.GITHUB_TOKEN}`;
    }
    https
      .get(new URL(url), { headers }, (res) => {
        if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
          res.resume();
          resolve(request(new URL(res.headers.location, url).toString()));
          return;
        }
        if (res.statusCode !== 200) {
          res.resume();
          reject(new Error(`HTTP ${res.statusCode} while fetching ${url}`));
          return;
        }
        const chunks = [];
        res.on("data", (chunk) => chunks.push(chunk));
        res.on("end", () => resolve(Buffer.concat(chunks)));
      })
      .on("error", reject);
  });
}

async function main() {
  const release = await requestJson(
    `https://api.github.com/repos/${OWNER}/${REPO}/releases/tags/v${VERSION}`,
  );
  if (release.draft) {
    throw new Error(`GitHub Release v${VERSION} is still a draft`);
  }

  const assetByName = new Map((release.assets || []).map((asset) => [asset.name, asset]));
  const checksumsName = checksumFileName();
  const checksumsAsset = assetByName.get(checksumsName);
  if (!checksumsAsset) {
    throw new Error(`missing GitHub Release checksum asset: ${checksumsName}`);
  }

  const checksums = parseChecksums(
    (await request(checksumsAsset.browser_download_url)).toString("utf8"),
  );
  const missing = [];
  for (const triplet of requiredTriplets()) {
    const assetName = assetNameFor(triplet);
    if (!assetByName.has(assetName)) {
      missing.push(assetName);
      continue;
    }
    if (!checksums.has(assetName)) {
      missing.push(`${assetName} checksum`);
    }
  }

  if (missing.length) {
    throw new Error(`missing required release assets: ${missing.join(", ")}`);
  }
  console.log(`GitHub Release v${VERSION} has required npm binary assets.`);
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
