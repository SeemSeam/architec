import fs from "node:fs/promises";
import path from "node:path";

import { defaultPlanCode, defaultSeatLimit } from "@/lib/billing";
import { dbFile } from "@/lib/config";
import type {
  CliAuthCode,
  CloudDevice,
  CloudSession,
  CloudUser,
  DevDb,
  RefreshTokenRecord
} from "@/lib/types";

const emptyDb: DevDb = {
  users: [],
  sessions: [],
  devices: [],
  authCodes: [],
  refreshTokens: []
};

async function ensureDb(): Promise<void> {
  await fs.mkdir(path.dirname(dbFile), { recursive: true });
  try {
    await fs.access(dbFile);
  } catch {
    await fs.writeFile(dbFile, JSON.stringify(emptyDb, null, 2), "utf8");
  }
}

function normalizeDb(db: DevDb): boolean {
  let changed = false;
  for (const user of db.users) {
    if (user.plan !== defaultPlanCode) {
      user.plan = defaultPlanCode;
      changed = true;
    }
    if (!Number.isFinite(user.seatLimit) || user.seatLimit < 1) {
      user.seatLimit = defaultSeatLimit;
      changed = true;
    }
    if (typeof user.stripeCustomerId === "undefined") {
      user.stripeCustomerId = null;
      changed = true;
    }
    if (typeof user.stripeSubscriptionId === "undefined") {
      user.stripeSubscriptionId = null;
      changed = true;
    }
    if (typeof user.stripeSubscriptionStatus === "undefined") {
      user.stripeSubscriptionStatus = null;
      changed = true;
    }
  }
  return changed;
}

export async function readDb(): Promise<DevDb> {
  await ensureDb();
  const text = await fs.readFile(dbFile, "utf8");
  const db = JSON.parse(text) as DevDb;
  if (normalizeDb(db)) {
    await fs.writeFile(dbFile, JSON.stringify(db, null, 2), "utf8");
  }
  return db;
}

export async function writeDb(db: DevDb): Promise<void> {
  await ensureDb();
  await fs.writeFile(dbFile, JSON.stringify(db, null, 2), "utf8");
}

export async function withDb<T>(fn: (db: DevDb) => Promise<T> | T): Promise<T> {
  const db = await readDb();
  const result = await fn(db);
  await writeDb(db);
  return result;
}

export function findUserByEmail(db: DevDb, email: string): CloudUser | undefined {
  return db.users.find((item) => item.email === email);
}

export function findUserById(db: DevDb, userId: string): CloudUser | undefined {
  return db.users.find((item) => item.id === userId);
}

export function findSession(db: DevDb, sessionId: string): CloudSession | undefined {
  return db.sessions.find((item) => item.id === sessionId);
}

export function findDeviceByInstallId(db: DevDb, userId: string, installId: string): CloudDevice | undefined {
  return db.devices.find((item) => item.userId === userId && item.installId === installId);
}

export function activeDevices(db: DevDb, userId: string): CloudDevice[] {
  return db.devices.filter((item) => item.userId === userId && !item.revokedAt);
}

export function findAuthCode(db: DevDb, code: string): CliAuthCode | undefined {
  return db.authCodes.find((item) => item.code === code);
}

export function findRefreshToken(db: DevDb, tokenHash: string): RefreshTokenRecord | undefined {
  return db.refreshTokens.find((item) => item.tokenHash === tokenHash);
}
