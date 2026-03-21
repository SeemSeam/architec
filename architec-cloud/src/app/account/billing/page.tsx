import Link from "next/link";

import { requireUser } from "@/lib/auth";
import { defaultPlanLabel, monthlyPriceUsd, pricingSummary, trialDays, trialEndsAt } from "@/lib/billing";
import {
  stripeEnabled,
  stripeModeLabel,
  stripeReadinessChecks,
  stripeStatusTone,
  stripeSubscriptionLabel
} from "@/lib/stripe";

type Props = {
  searchParams: Promise<{
    result?: string;
  }>;
};

function billingResultMessage(result: string): { kind: "ok" | "err"; text: string } | null {
  if (result === "checkout_stub") {
    return {
      kind: "ok",
      text: "Checkout is still a local stub. This is the handoff point where Stripe Checkout will be connected later."
    };
  }
  if (result === "portal_stub") {
    return {
      kind: "ok",
      text: "Customer portal is still a local stub. This endpoint is reserved for a future Stripe billing portal."
    };
  }
  if (result === "checkout_success") {
    return {
      kind: "ok",
      text: "Stripe Checkout returned successfully. Billing state will finalize through webhook synchronization."
    };
  }
  if (result === "checkout_cancelled") {
    return {
      kind: "err",
      text: "Checkout was cancelled before Stripe finished creating or confirming the subscription."
    };
  }
  if (result === "checkout_error") {
    return {
      kind: "err",
      text: "Stripe Checkout could not be opened. Verify Stripe keys, price ID, and redirect configuration."
    };
  }
  if (result === "portal_error") {
    return {
      kind: "err",
      text: "The Stripe customer portal could not be opened. Verify Stripe customer records and portal setup."
    };
  }
  return null;
}

export default async function BillingPage({ searchParams }: Props) {
  const user = await requireUser();
  const params = await searchParams;
  const trialEndDate = trialEndsAt(user.createdAt);
  const trialMsRemaining = trialEndDate.getTime() - Date.now();
  const inTrial = trialMsRemaining > 0;
  const trialDaysRemaining = Math.max(0, Math.ceil(trialMsRemaining / (24 * 60 * 60 * 1000)));
  const feedback = billingResultMessage(String(params.result || ""));
  const readiness = stripeReadinessChecks();

  return (
    <section className="stack">
      <section className="hero-shell">
        <div className="card glass hero-copy">
          <div className="section-head">
            <p className="eyebrow">Billing</p>
            <h1>One subscription, one trial window, one monthly renewal price.</h1>
            <p className="page-lead">
              The commercial model is fixed to {pricingSummary()}. This account page shows the current state
              of that offer, even while checkout and self-serve portal routes remain stubs in local testing.
            </p>
          </div>
          <div className="inline-metrics">
            <div className="inline-metric">
              <strong>{inTrial ? `${trialDaysRemaining}d` : "$2"}</strong>
              <span>{inTrial ? "remaining in trial" : "monthly renewal target"}</span>
            </div>
            <div className="inline-metric">
              <strong>{trialDays}</strong>
              <span>trial days on every account</span>
            </div>
            <div className="inline-metric">
              <strong>{user.licenseActive ? "on" : "off"}</strong>
              <span>license activation state</span>
            </div>
          </div>
          <div className="pill-row">
            <span className="status-pill ok">{defaultPlanLabel}</span>
            <span className={inTrial ? "status-pill ok" : "status-pill"}>
              Phase: {inTrial ? "trial" : "post-trial price path"}
            </span>
            <span className="status-pill">Trial ends: {trialEndDate.toLocaleDateString()}</span>
            <span className="status-pill">Billing mode: {stripeModeLabel()}</span>
            <span className={`status-pill ${stripeStatusTone(user.stripeSubscriptionStatus)}`}>
              Stripe status: {stripeSubscriptionLabel(user.stripeSubscriptionStatus)}
            </span>
            <span className={user.licenseActive ? "status-pill ok" : "status-pill danger"}>
              License: {user.licenseActive ? "active" : "inactive"}
            </span>
          </div>
          {feedback ? <div className={`notice ${feedback.kind}`}>{feedback.text}</div> : null}
        </div>
        <aside className="card hero-panel">
          <div className="section-head tight">
            <p className="eyebrow">Current account state</p>
            <h2>Commercial messaging is fixed even before payments go live.</h2>
          </div>
          <div className="matrix-list">
            <div className="matrix-row">
              <strong>Offer shape</strong>
              <span>No free-forever fallback and no second paid tier. The same account continues through trial and paid usage.</span>
            </div>
            <div className="matrix-row">
              <strong>Local testing reality</strong>
              <span>
                {stripeEnabled
                  ? "Stripe routes are enabled. The commercial contract is now backed by real checkout and portal endpoints."
                  : "Billing routes still act as local stubs, but the user-facing contract is already constrained to one offer."}
              </span>
            </div>
            <div className="matrix-row">
              <strong>Next integration point</strong>
              <span>
                {stripeEnabled
                  ? "Webhook synchronization remains the source of truth for customer and subscription state after Stripe redirects."
                  : "Stripe checkout and customer portal can replace these stub actions later without changing page structure or copy."}
              </span>
            </div>
            <div className="matrix-row">
              <strong>Stripe linkage</strong>
              <span>
                Customer ID: {user.stripeCustomerId || "not created yet"}.
                Subscription ID: {user.stripeSubscriptionId || "not created yet"}.
              </span>
            </div>
          </div>
          <div className="button-row">
            <Link className="button secondary" href="/pricing">Open public pricing page</Link>
            <Link className="button ghost" href="/account">Back to account</Link>
          </div>
        </aside>
      </section>

      <section className="surface-grid">
        {readiness.map((item) => (
          <div key={item.key} className="card surface-card">
            <div className="topline">
              <span className="eyebrow">{item.label}</span>
              <span className={item.ready ? "status-pill ok" : "status-pill danger"}>
                {item.ready ? "ready" : "missing"}
              </span>
            </div>
            <h2>{item.ready ? "Configured" : "Needs setup"}</h2>
            <p className="muted">{item.detail}</p>
          </div>
        ))}
      </section>

      <section className="pricing-shell">
        <div className="card price-card glass">
          <div className="section-head tight">
            <p className="eyebrow">Subscription</p>
            <h2>Keep the offer understandable from the first visit.</h2>
          </div>
          <div className="matrix-list">
            <div className="matrix-row">
              <strong>Start</strong>
              <span>Every account begins on the same {trialDays}-day free trial.</span>
            </div>
            <div className="matrix-row">
              <strong>Continue</strong>
              <span>After the trial window, the account is expected to renew at ${monthlyPriceUsd}/month.</span>
            </div>
            <div className="matrix-row">
              <strong>Constraint</strong>
              <span>There is no separate free plan and no alternate paid tier to explain or migrate between.</span>
            </div>
          </div>
        </div>
        <div className="card price-card">
          <div className="section-head tight">
            <p className="eyebrow">Billing actions</p>
            <h2>{stripeEnabled ? "Stripe endpoints are ready to be exercised." : "Payment hooks are still local placeholders."}</h2>
          </div>
          <div className="button-row">
            <form action="/api/billing/checkout" method="post">
              <button className="button" type="submit" data-busy-label="Opening checkout...">
                {stripeEnabled ? "Open Stripe checkout" : "Open checkout stub"}
              </button>
            </form>
            <form action="/api/billing/portal" method="post">
              <button className="button secondary" type="submit" data-busy-label="Opening portal...">
                {stripeEnabled ? "Open Stripe portal" : "Open portal stub"}
              </button>
            </form>
          </div>
          <p className="muted">
            These endpoints are intentionally isolated so they can be swapped to Stripe later without changing the
            single-offer product structure or the account language around it.
          </p>
        </div>
      </section>
    </section>
  );
}
