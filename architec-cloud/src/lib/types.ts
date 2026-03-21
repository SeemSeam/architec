export type PlanCode = "standard";

export type CloudUser = {
  id: string;
  email: string;
  passwordHash: string;
  plan: PlanCode;
  seatLimit: number;
  licenseActive: boolean;
  emailVerified: boolean;
  isAdmin: boolean;
  createdAt: string;
  stripeCustomerId: string | null;
  stripeSubscriptionId: string | null;
  stripeSubscriptionStatus: string | null;
};

export type CloudSession = {
  id: string;
  userId: string;
  createdAt: string;
  expiresAt: string;
};

export type CloudDevice = {
  id: string;
  userId: string;
  installId: string;
  deviceName: string;
  createdAt: string;
  lastSeenAt: string;
  revokedAt: string | null;
};

export type CliAuthCode = {
  code: string;
  userId: string;
  installId: string;
  deviceName: string;
  redirectUri: string;
  createdAt: string;
  expiresAt: string;
  usedAt: string | null;
};

export type RefreshTokenRecord = {
  id: string;
  userId: string;
  deviceId: string;
  tokenHash: string;
  createdAt: string;
  expiresAt: string;
  lastUsedAt: string;
  revokedAt: string | null;
};

export type DevDb = {
  users: CloudUser[];
  sessions: CloudSession[];
  devices: CloudDevice[];
  authCodes: CliAuthCode[];
  refreshTokens: RefreshTokenRecord[];
};
