import Link from "next/link";

import { requireUser } from "@/lib/auth";
import { defaultPlanLabel, monthlyPriceUsd, trialEndsAt, trialDays } from "@/lib/billing";
import { activeDevices, readDb } from "@/lib/db";
import { stripeModeLabel, stripeStatusTone, stripeSubscriptionLabel } from "@/lib/stripe";

export default async function AccountPage() {
  const user = await requireUser();
  const db = await readDb();
  const devices = activeDevices(db, user.id);
  const allDevices = db.devices.filter((item) => item.userId === user.id);
  const revokedCount = allDevices.filter((item) => item.revokedAt).length;
  const trialEnd = trialEndsAt(user.createdAt).toLocaleDateString();
  const accountAgeDays = Math.max(
    1,
    Math.ceil((Date.now() - new Date(user.createdAt).getTime()) / (24 * 60 * 60 * 1000))
  );

  return (
    <section className="stack">
      <section className="hero-shell">
        <div className="card glass hero-copy">
          <div className="section-head">
            <p className="eyebrow">Account</p>
            <h1>{user.email}</h1>
            <p className="page-lead">
              This account is the control record behind your browser session, device seats, GitHub release access
              guidance, and signed CLI authorization state.
            </p>
          </div>
          <div className="inline-metrics">
            <div className="inline-metric">
              <strong>{devices.length}</strong>
              <span>active devices attached</span>
            </div>
            <div className="inline-metric">
              <strong>{user.seatLimit}</strong>
              <span>seat ceiling for this account</span>
            </div>
            <div className="inline-metric">
              <strong>{accountAgeDays}d</strong>
              <span>since this account was created</span>
            </div>
          </div>
          <div className="pill-row">
            <span className="status-pill ok">Plan: {defaultPlanLabel}</span>
            <span className="status-pill">Trial ends: {trialEnd}</span>
            <span className={`status-pill ${stripeStatusTone(user.stripeSubscriptionStatus)}`}>
              Billing: {stripeSubscriptionLabel(user.stripeSubscriptionStatus)}
            </span>
            <span className="status-pill">Mode: {stripeModeLabel()}</span>
            <span className={user.licenseActive ? "status-pill ok" : "status-pill danger"}>
              License: {user.licenseActive ? "active" : "inactive"}
            </span>
            <span className="status-pill">Admin: {user.isAdmin ? "yes" : "no"}</span>
          </div>
          <div className="button-row">
            <Link className="button" href="/account/devices">Open device ledger</Link>
            <Link className="button secondary" href="/account/billing">Review billing state</Link>
          </div>
        </div>
        <aside className="card hero-panel">
          <div className="section-head tight">
            <p className="eyebrow">Control status</p>
            <h2>The browser account remains the source of truth.</h2>
          </div>
          <div className="matrix-list">
            <div className="matrix-row">
              <strong>Identity</strong>
              <span>Browser login and CLI approval both map back to this same user record.</span>
            </div>
            <div className="matrix-row">
              <strong>Authorization</strong>
              <span>Seat occupancy and license activity are checked before a new machine is approved.</span>
            </div>
            <div className="matrix-row">
              <strong>Recovery</strong>
              <span>Revoking a device detaches its refresh state without affecting project files on disk.</span>
            </div>
            <div className="matrix-row">
              <strong>Billing sync</strong>
              <span>
                Customer: {user.stripeCustomerId || "not linked yet"}.
                Subscription: {user.stripeSubscriptionId || "not linked yet"}.
              </span>
            </div>
          </div>
          <div className="mini-shell">{`$ archi whoami
email: ${user.email}
plan: ${defaultPlanLabel.toLowerCase()}
license: ${user.licenseActive ? "active" : "inactive"}
seats: ${devices.length}/${user.seatLimit}`}</div>
        </aside>
      </section>

      <div className="metric-strip">
        <div className="card metric-card">
          <span className="eyebrow">Active seats</span>
          <strong>{devices.length}</strong>
          <p className="muted">Authorized installs currently attached to this account.</p>
        </div>
        <div className="card metric-card">
          <span className="eyebrow">Seat limit</span>
          <strong>{user.seatLimit}</strong>
          <p className="muted">The maximum number of devices allowed before the portal blocks a new install.</p>
        </div>
        <div className="card metric-card">
          <span className="eyebrow">Revoked</span>
          <strong>{revokedCount}</strong>
          <p className="muted">Historical installs that were explicitly detached from this user.</p>
        </div>
      </div>

      <div className="feature-grid">
        <Link className="card feature-card" href="/account/devices">
          <p className="eyebrow">Devices</p>
          <h2>{devices.length} active devices</h2>
          <p className="muted">Inspect install IDs, revoke stale seats, and understand current occupancy.</p>
        </Link>
        <Link className="card feature-card" href="/account/billing">
          <p className="eyebrow">Billing</p>
          <h2>{trialDays}-day trial, then ${monthlyPriceUsd}/month</h2>
          <p className="muted">The account model is now a single subscription path with one weekly trial window.</p>
        </Link>
        <Link className="card feature-card" href="/account/downloads">
          <p className="eyebrow">Downloads</p>
          <h2>GitHub release links</h2>
          <p className="muted">Open the release feed, latest build, and install guidance without turning the site into a file host.</p>
        </Link>
      </div>
    </section>
  );
}
