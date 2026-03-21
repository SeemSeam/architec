import { cliMinVersion } from "@/lib/config";

type ParsedVersion = {
  raw: string;
  normalized: string;
  parts: [number, number, number];
};

export type CliVersionGate = {
  clientVersion: string | null;
  minimumVersion: string | null;
  invalidClientVersion: boolean;
  invalidMinimumVersion: boolean;
  upgradeRequired: boolean;
  detail: string | null;
};

const VERSION_RE = /^v?(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:[-+][0-9A-Za-z.-]+)?$/;

function parseVersion(value: string): ParsedVersion | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const match = VERSION_RE.exec(trimmed);
  if (!match) {
    return null;
  }
  const major = Number(match[1] || "0");
  const minor = Number(match[2] || "0");
  const patch = Number(match[3] || "0");
  return {
    raw: trimmed,
    normalized: `${major}.${minor}.${patch}`,
    parts: [major, minor, patch]
  };
}

function compareVersions(left: ParsedVersion, right: ParsedVersion): number {
  for (let index = 0; index < left.parts.length; index += 1) {
    if (left.parts[index] > right.parts[index]) {
      return 1;
    }
    if (left.parts[index] < right.parts[index]) {
      return -1;
    }
  }
  return 0;
}

export function getCliVersionGate(clientVersion: string | null | undefined): CliVersionGate {
  const parsedMinimum = parseVersion(cliMinVersion);
  const trimmedClientVersion = (clientVersion || "").trim();
  const parsedClient = parseVersion(trimmedClientVersion);

  if (cliMinVersion && !parsedMinimum) {
    return {
      clientVersion: parsedClient?.normalized || (trimmedClientVersion || null),
      minimumVersion: cliMinVersion,
      invalidClientVersion: false,
      invalidMinimumVersion: true,
      upgradeRequired: false,
      detail: `Invalid ARCHITEC_CLOUD_CLI_MIN_VERSION: ${cliMinVersion}`
    };
  }

  if (!trimmedClientVersion) {
    return {
      clientVersion: null,
      minimumVersion: parsedMinimum?.normalized || null,
      invalidClientVersion: false,
      invalidMinimumVersion: false,
      upgradeRequired: false,
      detail: null
    };
  }

  if (!parsedClient) {
    return {
      clientVersion: trimmedClientVersion,
      minimumVersion: parsedMinimum?.normalized || null,
      invalidClientVersion: true,
      invalidMinimumVersion: false,
      upgradeRequired: false,
      detail: `Invalid app version: ${trimmedClientVersion}`
    };
  }

  if (parsedMinimum && compareVersions(parsedClient, parsedMinimum) < 0) {
    return {
      clientVersion: parsedClient.normalized,
      minimumVersion: parsedMinimum.normalized,
      invalidClientVersion: false,
      invalidMinimumVersion: false,
      upgradeRequired: true,
      detail: `CLI ${parsedClient.normalized} is below minimum supported version ${parsedMinimum.normalized}. Upgrade required.`
    };
  }

  return {
    clientVersion: parsedClient.normalized,
    minimumVersion: parsedMinimum?.normalized || null,
    invalidClientVersion: false,
    invalidMinimumVersion: false,
    upgradeRequired: false,
    detail: null
  };
}
