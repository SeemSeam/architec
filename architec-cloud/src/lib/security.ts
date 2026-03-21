import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";

import { dataDir, leaseKid } from "@/lib/config";

const KEYS_DIR = path.join(dataDir, "keys");
const PRIVATE_KEY_PATH = path.join(KEYS_DIR, "lease-private.pem");
const PUBLIC_KEY_PATH = path.join(KEYS_DIR, "lease-public.pem");

export function nowIso(): string {
  return new Date().toISOString();
}

export function afterSeconds(seconds: number): string {
  return new Date(Date.now() + seconds * 1000).toISOString();
}

export function randomToken(bytes = 24): string {
  return crypto.randomBytes(bytes).toString("base64url");
}

export function sha256Text(value: string): string {
  return crypto.createHash("sha256").update(value, "utf8").digest("hex");
}

export async function hashPassword(password: string): Promise<string> {
  const salt = crypto.randomBytes(16);
  const digest = await new Promise<Buffer>((resolve, reject) => {
    crypto.scrypt(password, salt, 64, (err, key) => {
      if (err) {
        reject(err);
        return;
      }
      resolve(key as Buffer);
    });
  });
  return `${salt.toString("base64")}$${digest.toString("base64")}`;
}

export async function verifyPassword(password: string, encoded: string): Promise<boolean> {
  const [saltB64, digestB64] = encoded.split("$", 2);
  if (!saltB64 || !digestB64) {
    return false;
  }
  const salt = Buffer.from(saltB64, "base64");
  const expected = Buffer.from(digestB64, "base64");
  const actual = await new Promise<Buffer>((resolve, reject) => {
    crypto.scrypt(password, salt, 64, (err, key) => {
      if (err) {
        reject(err);
        return;
      }
      resolve(key as Buffer);
    });
  });
  return crypto.timingSafeEqual(actual, expected);
}

export async function ensureLeaseKeys(): Promise<void> {
  await fs.mkdir(KEYS_DIR, { recursive: true });
  try {
    await fs.access(PRIVATE_KEY_PATH);
    await fs.access(PUBLIC_KEY_PATH);
    return;
  } catch {
    const { privateKey, publicKey } = crypto.generateKeyPairSync("ed25519");
    await fs.writeFile(
      PRIVATE_KEY_PATH,
      privateKey.export({ type: "pkcs8", format: "pem" }),
      "utf8",
    );
    await fs.writeFile(
      PUBLIC_KEY_PATH,
      publicKey.export({ type: "spki", format: "pem" }),
      "utf8",
    );
  }
}

export async function publicKeyPem(): Promise<string> {
  await ensureLeaseKeys();
  return fs.readFile(PUBLIC_KEY_PATH, "utf8");
}

export async function signLeaseBody(payload: Record<string, unknown>): Promise<string> {
  await ensureLeaseKeys();
  const privateKey = await fs.readFile(PRIVATE_KEY_PATH, "utf8");
  const blob = Buffer.from(JSON.stringify(payload, Object.keys(payload).sort()), "utf8");
  return crypto.sign(null, blob, privateKey).toString("base64url");
}

export function buildLeaseBase(user: {
  id: string;
  email: string;
  plan: string;
  seatLimit: number;
  licenseActive: boolean;
}, deviceId: string, installId: string) {
  return {
    iss: "architec-cloud-dev",
    aud: "architec-cli",
    kid: leaseKid,
    sub: user.id,
    email: user.email,
    plan: user.plan,
    seat_limit: user.seatLimit,
    device_id: deviceId,
    install_id: installId,
    license_active: user.licenseActive,
    issued_at: nowIso(),
    expires_at: afterSeconds(60 * 60 * 24)
  };
}
