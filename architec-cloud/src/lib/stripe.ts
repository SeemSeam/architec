import Stripe from "stripe";

import { trialDays } from "@/lib/billing";
import {
  absoluteAppUrl,
  stripePriceIdMonthly,
  stripePublishableKey,
  stripeSecretKey,
  stripeWebhookSecret
} from "@/lib/config";
import { withDb } from "@/lib/db";
import type { CloudUser } from "@/lib/types";

let stripeClient: Stripe | null = null;

export const stripeEnabled = Boolean(stripeSecretKey && stripePriceIdMonthly);
export const stripeWebhookEnabled = Boolean(stripeSecretKey && stripeWebhookSecret);

export function stripeModeLabel(): string {
  return stripeEnabled ? "live integration ready" : "local stub mode";
}

export function getStripe(): Stripe {
  if (!stripeSecretKey) {
    throw new Error("STRIPE_SECRET_KEY_MISSING");
  }
  if (!stripeClient) {
    stripeClient = new Stripe(stripeSecretKey);
  }
  return stripeClient;
}

export function licenseActiveForStripeStatus(status: string | null | undefined): boolean {
  return status === "trialing" || status === "active" || status === "past_due";
}

export function stripeSubscriptionLabel(status: string | null | undefined): string {
  if (!status) {
    return stripeEnabled ? "not synced yet" : "stub mode";
  }
  return status.replaceAll("_", " ");
}

export function stripeStatusTone(status: string | null | undefined): "ok" | "danger" | "" {
  if (!status) {
    return "";
  }
  if (licenseActiveForStripeStatus(status)) {
    return "ok";
  }
  return "danger";
}

export function stripeReadinessChecks(): Array<{
  key: string;
  label: string;
  ready: boolean;
  detail: string;
}> {
  return [
    {
      key: "secret",
      label: "Secret key",
      ready: Boolean(stripeSecretKey),
      detail: stripeSecretKey ? "Server-side Stripe API access is configured." : "ARCHITEC_CLOUD_STRIPE_SECRET_KEY is missing."
    },
    {
      key: "publishable",
      label: "Publishable key",
      ready: Boolean(stripePublishableKey),
      detail: stripePublishableKey ? "Client-side Stripe publishing key is present." : "ARCHITEC_CLOUD_STRIPE_PUBLISHABLE_KEY is missing."
    },
    {
      key: "price",
      label: "Monthly price ID",
      ready: Boolean(stripePriceIdMonthly),
      detail: stripePriceIdMonthly ? `Using Stripe price ${stripePriceIdMonthly}.` : "ARCHITEC_CLOUD_STRIPE_PRICE_ID_MONTHLY is missing."
    },
    {
      key: "webhook",
      label: "Webhook secret",
      ready: Boolean(stripeWebhookSecret),
      detail: stripeWebhookSecret ? "Webhook signature verification can run." : "ARCHITEC_CLOUD_STRIPE_WEBHOOK_SECRET is missing."
    }
  ];
}

export async function ensureStripeCustomer(user: CloudUser): Promise<string> {
  if (!stripeEnabled) {
    throw new Error("STRIPE_NOT_CONFIGURED");
  }
  if (user.stripeCustomerId) {
    return user.stripeCustomerId;
  }
  const customer = await getStripe().customers.create({
    email: user.email,
    metadata: {
      userId: user.id,
      plan: user.plan
    }
  });

  await withDb(async (db) => {
    const target = db.users.find((item) => item.id === user.id);
    if (!target) {
      return;
    }
    target.stripeCustomerId = customer.id;
  });

  return customer.id;
}

export async function createCheckoutSession(user: CloudUser): Promise<string> {
  if (!stripeEnabled) {
    throw new Error("STRIPE_NOT_CONFIGURED");
  }
  const customerId = await ensureStripeCustomer(user);
  const session = await getStripe().checkout.sessions.create({
    mode: "subscription",
    customer: customerId,
    line_items: [
      {
        price: stripePriceIdMonthly,
        quantity: 1
      }
    ],
    metadata: {
      userId: user.id,
      plan: user.plan
    },
    subscription_data: {
      trial_period_days: trialDays,
      metadata: {
        userId: user.id,
        plan: user.plan
      }
    },
    success_url: absoluteAppUrl("/account/billing?result=checkout_success").toString(),
    cancel_url: absoluteAppUrl("/account/billing?result=checkout_cancelled").toString()
  });

  if (!session.url) {
    throw new Error("STRIPE_CHECKOUT_URL_MISSING");
  }
  return session.url;
}

export async function createPortalSession(user: CloudUser): Promise<string> {
  if (!stripeEnabled) {
    throw new Error("STRIPE_NOT_CONFIGURED");
  }
  const customerId = await ensureStripeCustomer(user);
  const session = await getStripe().billingPortal.sessions.create({
    customer: customerId,
    return_url: absoluteAppUrl("/account/billing").toString()
  });
  return session.url;
}

export async function syncUserFromStripeSubscription(
  customerId: string,
  subscriptionId: string,
  status: string,
  metadataUserId?: string | null
): Promise<boolean> {
  let updated = false;
  await withDb(async (db) => {
    const target =
      db.users.find((item) => metadataUserId && item.id === metadataUserId) ??
      db.users.find((item) => item.stripeCustomerId === customerId) ??
      db.users.find((item) => item.stripeSubscriptionId === subscriptionId);

    if (!target) {
      return;
    }

    target.stripeCustomerId = customerId;
    target.stripeSubscriptionId = subscriptionId;
    target.stripeSubscriptionStatus = status;
    target.licenseActive = licenseActiveForStripeStatus(status);
    updated = true;
  });
  return updated;
}

export async function syncUserFromCompletedCheckout(
  customerId: string,
  subscriptionId: string | null,
  metadataUserId?: string | null
): Promise<boolean> {
  let updated = false;
  await withDb(async (db) => {
    const target =
      db.users.find((item) => metadataUserId && item.id === metadataUserId) ??
      db.users.find((item) => item.stripeCustomerId === customerId);

    if (!target) {
      return;
    }

    target.stripeCustomerId = customerId;
    if (subscriptionId) {
      target.stripeSubscriptionId = subscriptionId;
    }
    updated = true;
  });
  return updated;
}
