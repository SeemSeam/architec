import type { Metadata } from "next";
import Link from "next/link";

import { defaultPlanLabel, defaultSeatLimit, monthlyPriceUsd, pricingSummary, trialDays } from "@/lib/billing";

export const metadata: Metadata = {
  title: "Pricing",
  description: "Architec Cloud uses one subscription path: a 7-day free trial followed by $2/month."
};

export default function PricingPage() {
  return (
    <section className="stack">
      <div className="card glass hero-copy">
        <div className="section-head">
          <p className="eyebrow">Pricing</p>
          <h1>One technical product. One subscription.</h1>
          <p className="page-lead">
            No plan maze, no free-forever split, and no second enterprise tier. The same account model handles
            trial, seats, browser approval, and local usage: {pricingSummary()}.
          </p>
        </div>
        <div className="hero-proof">
          <span className="status-pill ok">Single commercial path</span>
          <span className="status-pill">No feature gating by plan tier</span>
          <span className="status-pill">Same CLI flow before and after billing starts</span>
        </div>
      </div>
      <section className="pricing-shell">
        <div className="card pricing-frame glass">
          <div className="section-head tight">
            <p className="eyebrow">{defaultPlanLabel}</p>
            <h2>The same product from day 1 through paid usage.</h2>
          </div>
          <div className="pricing-split">
            <div className="pricing-callout">
              <div className="price-value">
                <strong>$0</strong>
                <span>for the first {trialDays} days</span>
              </div>
              <p className="muted">Use the real registration, browser approval, and device flow before billing ever begins.</p>
            </div>
            <div className="pricing-callout">
              <div className="price-value">
                <strong>${monthlyPriceUsd}</strong>
                <span>per month after trial</span>
              </div>
              <p className="muted">Keep the same account, same devices, and same local CLI workflow once the trial converts.</p>
            </div>
          </div>
          <div className="inline-metrics">
            <div className="inline-metric">
              <strong>{defaultSeatLimit}</strong>
              <span>authorized devices included</span>
            </div>
            <div className="inline-metric">
              <strong>1 flow</strong>
              <span>browser approval for every install</span>
            </div>
            <div className="inline-metric">
              <strong>Local</strong>
              <span>execution remains off the website</span>
            </div>
          </div>
          <ul className="list">
            <li>Browser login, signed CLI lease, and local skill usage are part of the same product surface.</li>
            <li>Pricing stays simple so the trust boundary is easier to explain and easier to operate.</li>
            <li>Revocation, seat enforcement, and GitHub-based distribution remain available without a higher tier.</li>
          </ul>
          <Link className="button" href="/register">Start the 7-day trial</Link>
        </div>

        <aside className="card price-card">
          <div className="section-head tight">
            <p className="eyebrow">What is included</p>
            <h2>No hidden premium path behind the trial.</h2>
          </div>
          <div className="matrix-list">
            <div className="matrix-row">
              <strong>Account and session layer</strong>
              <span>Registration, login, and durable browser identity for the same user account.</span>
            </div>
            <div className="matrix-row">
              <strong>Machine authorization flow</strong>
              <span>`archi login` opens browser approval, checks seat policy, and issues local authorization state.</span>
            </div>
            <div className="matrix-row">
              <strong>Device operations</strong>
              <span>Inspect installs, revoke stale machines, and keep seat occupancy understandable.</span>
            </div>
            <div className="matrix-row">
              <strong>Commercial boundary</strong>
              <span>A small subscription keeps the access-control layer active without locking execution into the website.</span>
            </div>
          </div>
          <div className="pricing-split">
            <div className="pricing-stat">
              <strong>{trialDays} days</strong>
              <span>free evaluation period</span>
            </div>
            <div className="pricing-stat">
              <strong>{defaultSeatLimit} seats</strong>
              <span>default limit per account</span>
            </div>
          </div>
        </aside>
      </section>
    </section>
  );
}
