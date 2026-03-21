import { NextResponse } from "next/server";

import type Stripe from "stripe";

import { getStripe, stripeWebhookEnabled, syncUserFromCompletedCheckout, syncUserFromStripeSubscription } from "@/lib/stripe";
import { stripeWebhookSecret } from "@/lib/config";

export async function POST(request: Request) {
  if (!stripeWebhookEnabled) {
    return NextResponse.json({ received: true, mode: "stub" });
  }

  const signature = request.headers.get("stripe-signature");
  if (!signature || !stripeWebhookSecret) {
    return NextResponse.json({ error: "missing_signature" }, { status: 400 });
  }

  const body = await request.text();
  let event: Stripe.Event;
  try {
    event = getStripe().webhooks.constructEvent(body, signature, stripeWebhookSecret);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "invalid_signature" },
      { status: 400 }
    );
  }

  switch (event.type) {
    case "checkout.session.completed": {
      const session = event.data.object as Stripe.Checkout.Session;
      const customerId = typeof session.customer === "string" ? session.customer : null;
      const subscriptionId = typeof session.subscription === "string" ? session.subscription : null;
      if (customerId) {
        await syncUserFromCompletedCheckout(customerId, subscriptionId, session.metadata?.userId ?? null);
      }
      break;
    }
    case "customer.subscription.created":
    case "customer.subscription.updated":
    case "customer.subscription.deleted": {
      const subscription = event.data.object as Stripe.Subscription;
      const customerId =
        typeof subscription.customer === "string" ? subscription.customer : subscription.customer.id;
      await syncUserFromStripeSubscription(
        customerId,
        subscription.id,
        subscription.status,
        subscription.metadata?.userId ?? null
      );
      break;
    }
    default:
      break;
  }

  return NextResponse.json({ received: true, type: event.type });
}
