type RateLimitEntry = {
  hits: number[];
};

type RateLimitStore = Map<string, RateLimitEntry>;

type RateLimitOptions = {
  scope: string;
  key: string;
  limit: number;
  windowMs: number;
  now?: number;
};

type RateLimitResult = {
  allowed: boolean;
  limit: number;
  remaining: number;
  retryAfterSeconds: number;
  resetAt: string;
};

type EnvLimitOptions = {
  defaultValue: number;
  min?: number;
};

declare global {
  var __architecRateLimitStore: RateLimitStore | undefined;
}

function store(): RateLimitStore {
  if (!globalThis.__architecRateLimitStore) {
    globalThis.__architecRateLimitStore = new Map<string, RateLimitEntry>();
  }
  return globalThis.__architecRateLimitStore;
}

function normalizeKey(value: string): string {
  return value.trim().toLowerCase() || "anonymous";
}

export function requestIp(request: Request): string {
  const forwarded = request.headers.get("x-forwarded-for") || "";
  const firstForwarded = forwarded
    .split(",")
    .map((item) => item.trim())
    .find(Boolean);
  return firstForwarded || request.headers.get("x-real-ip") || "unknown";
}

export function envRateLimit(name: string, { defaultValue, min = 1 }: EnvLimitOptions): number {
  const raw = Number(process.env[name] || "");
  if (!Number.isFinite(raw)) {
    return defaultValue;
  }
  return Math.max(min, Math.floor(raw));
}

export function consumeRateLimit({
  scope,
  key,
  limit,
  windowMs,
  now = Date.now()
}: RateLimitOptions): RateLimitResult {
  const normalizedLimit = Math.max(1, Math.floor(limit));
  const normalizedWindowMs = Math.max(1000, Math.floor(windowMs));
  const bucketKey = `${scope}:${normalizeKey(key)}`;
  const bucket = store().get(bucketKey) || { hits: [] };
  const windowStart = now - normalizedWindowMs;
  bucket.hits = bucket.hits.filter((item) => item > windowStart);

  if (bucket.hits.length >= normalizedLimit) {
    const earliestHit = bucket.hits[0] || now;
    store().set(bucketKey, bucket);
    return {
      allowed: false,
      limit: normalizedLimit,
      remaining: 0,
      retryAfterSeconds: Math.max(1, Math.ceil((earliestHit + normalizedWindowMs - now) / 1000)),
      resetAt: new Date(earliestHit + normalizedWindowMs).toISOString()
    };
  }

  bucket.hits.push(now);
  store().set(bucketKey, bucket);
  return {
    allowed: true,
    limit: normalizedLimit,
    remaining: Math.max(0, normalizedLimit - bucket.hits.length),
    retryAfterSeconds: 0,
    resetAt: new Date(now + normalizedWindowMs).toISOString()
  };
}
