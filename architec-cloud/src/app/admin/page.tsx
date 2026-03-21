import Link from "next/link";

import { defaultPlanLabel, monthlyPriceUsd, trialDays } from "@/lib/billing";
import { requireAdmin } from "@/lib/auth";
import { readDb } from "@/lib/db";
import { stripeModeLabel, stripeStatusTone, stripeSubscriptionLabel } from "@/lib/stripe";

type Props = {
  searchParams: Promise<{
    result?: string;
  }>;
};

function adminResultMessage(result: string): { kind: "ok" | "err"; text: string } | null {
  if (result === "user_updated") {
    return { kind: "ok", text: "The user record was updated successfully." };
  }
  if (result === "user_missing") {
    return { kind: "err", text: "The requested user record could not be found." };
  }
  if (result === "device_revoked") {
    return { kind: "ok", text: "The device was revoked and its refresh tokens were disabled." };
  }
  if (result === "device_missing") {
    return { kind: "err", text: "The requested device record could not be found." };
  }
  return null;
}

export default async function AdminPage({ searchParams }: Props) {
  const admin = await requireAdmin();
  const params = await searchParams;
  const db = await readDb();
  const activeDeviceCount = db.devices.filter((device) => !device.revokedAt).length;
  const inactiveUserCount = db.users.filter((user) => !user.licenseActive).length;
  const activeUserCount = db.users.length - inactiveUserCount;
  const totalSeats = db.users.reduce((sum, user) => sum + user.seatLimit, 0);
  const feedback = adminResultMessage(String(params.result || ""));

  return (
    <section className="stack">
      <section className="hero-shell">
        <div className="card glass hero-copy">
          <div className="section-head">
            <p className="eyebrow">Admin</p>
            <h1>Commercial control panel</h1>
            <p className="page-lead">
              This page is intentionally operational. It keeps user licenses, seat counts, trial timing, and
              device revocation visible without turning the product into a giant back-office system.
            </p>
          </div>
          <div className="inline-metrics">
            <div className="inline-metric">
              <strong>{db.users.length}</strong>
              <span>registered users</span>
            </div>
            <div className="inline-metric">
              <strong>{activeDeviceCount}</strong>
              <span>active devices across all accounts</span>
            </div>
            <div className="inline-metric">
              <strong>{inactiveUserCount}</strong>
              <span>inactive licenses requiring attention</span>
            </div>
          </div>
          <div className="pill-row">
            <span className="status-pill ok">Operator: {admin.email}</span>
            <span className="status-pill">Users: {db.users.length}</span>
            <span className="status-pill">Seat capacity: {totalSeats}</span>
            <span className="status-pill">Billing mode: {stripeModeLabel()}</span>
            <span className="status-pill">{trialDays}-day trial to ${monthlyPriceUsd}/month</span>
          </div>
          {feedback ? <div className={`notice ${feedback.kind}`}>{feedback.text}</div> : null}
        </div>
        <aside className="card hero-panel">
          <div className="section-head tight">
            <p className="eyebrow">Operator lens</p>
            <h2>See license policy and install state in one place.</h2>
          </div>
          <div className="matrix-list">
            <div className="matrix-row">
              <strong>User controls</strong>
              <span>Adjust seat limits, keep every plan on the same commercial shape, and disable licenses when needed.</span>
            </div>
            <div className="matrix-row">
              <strong>Install controls</strong>
              <span>Revoke device records centrally so stale machines lose their refresh path immediately.</span>
            </div>
            <div className="matrix-row">
              <strong>Commercial model</strong>
              <span>The system still assumes one offer only: {trialDays} days free, then ${monthlyPriceUsd}/month.</span>
            </div>
          </div>
          <div className="button-row">
            <Link className="button secondary" href="/account">Back to account</Link>
            <Link className="button ghost" href="/pricing">Open public pricing</Link>
          </div>
        </aside>
      </section>

      <div className="metric-strip">
        <div className="card metric-card">
          <span className="eyebrow">Active users</span>
          <strong>{activeUserCount}</strong>
          <p className="muted">Accounts currently allowed to authorize and refresh local installs.</p>
        </div>
        <div className="card metric-card">
          <span className="eyebrow">Inactive users</span>
          <strong>{inactiveUserCount}</strong>
          <p className="muted">Accounts that will fail authorization or lease refresh until re-enabled.</p>
        </div>
        <div className="card metric-card">
          <span className="eyebrow">Device load</span>
          <strong>{activeDeviceCount}</strong>
          <p className="muted">Total active installs currently attached across every account record.</p>
        </div>
      </div>

      <section className="card table-card">
        <div className="table-toolbar">
          <div className="section-head tight">
            <p className="eyebrow">Users</p>
            <h2>Subscription, seats, and license state.</h2>
          </div>
          <span className="caption">Plan locked to {defaultPlanLabel}</span>
        </div>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Email</th>
                <th>Plan</th>
                <th>Seats</th>
                <th>Billing</th>
                <th>License</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {db.users.map((user) => (
                <tr key={user.id}>
                  <td>
                    <div className="cell-stack">
                      <strong>{user.email}</strong>
                      <span className="muted">{user.isAdmin ? "Admin user" : "Standard user"}</span>
                    </div>
                  </td>
                  <td>
                    <span className="status-pill">{defaultPlanLabel}</span>
                  </td>
                  <td>{user.seatLimit}</td>
                  <td>
                    <div className="cell-stack">
                      <span className={`status-pill ${stripeStatusTone(user.stripeSubscriptionStatus)}`}>
                        {stripeSubscriptionLabel(user.stripeSubscriptionStatus)}
                      </span>
                      <span className="muted">
                        {user.stripeCustomerId ? `Customer ${user.stripeCustomerId}` : "No Stripe customer yet"}
                      </span>
                    </div>
                  </td>
                  <td>
                    <span className={user.licenseActive ? "status-pill ok" : "status-pill danger"}>
                      {user.licenseActive ? "active" : "inactive"}
                    </span>
                  </td>
                  <td>
                    <form
                      className="inline-form"
                      action="/api/admin/users/update"
                      method="post"
                      data-confirm-message={`Save seat or license changes for ${user.email}?`}
                    >
                      <input type="hidden" name="userId" value={user.id} />
                      <input type="number" name="seatLimit" defaultValue={user.seatLimit} min={1} />
                      <label className="inline-check">
                        <input type="checkbox" name="licenseActive" value="1" defaultChecked={user.licenseActive} />
                        active
                      </label>
                      <button className="button" type="submit" data-busy-label="Saving...">Save</button>
                    </form>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card table-card">
        <div className="table-toolbar">
          <div className="section-head tight">
            <p className="eyebrow">Devices</p>
            <h2>Install visibility and revoke controls.</h2>
          </div>
          <span className="caption">{db.devices.length} total device records</span>
        </div>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Install</th>
                <th>Device</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {db.devices.map((device) => (
                <tr key={device.id}>
                  <td>
                    <div className="cell-stack">
                      <strong><code>{device.installId}</code></strong>
                      <span className="muted">Created {new Date(device.createdAt).toLocaleString()}</span>
                    </div>
                  </td>
                  <td>
                    <div className="cell-stack">
                      <strong>{device.deviceName}</strong>
                      <span className="muted">Last seen {new Date(device.lastSeenAt).toLocaleString()}</span>
                    </div>
                  </td>
                  <td>
                    <span className={device.revokedAt ? "status-pill danger" : "status-pill ok"}>
                      {device.revokedAt ? "revoked" : "active"}
                    </span>
                  </td>
                  <td>
                    {!device.revokedAt ? (
                      <form
                        action="/api/admin/devices/revoke"
                        method="post"
                        data-confirm-message={`Revoke ${device.deviceName}? This disables refresh for that install.`}
                      >
                        <input type="hidden" name="deviceId" value={device.id} />
                        <button className="button danger" type="submit" data-busy-label="Revoking...">Revoke</button>
                      </form>
                    ) : (
                      <span className="muted">Already revoked</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </section>
  );
}
