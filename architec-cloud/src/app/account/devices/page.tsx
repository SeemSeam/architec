import Link from "next/link";

import { requireUser } from "@/lib/auth";
import { readDb } from "@/lib/db";

type Props = {
  searchParams: Promise<{
    result?: string;
  }>;
};

function deviceResultMessage(result: string): { kind: "ok" | "err"; text: string } | null {
  if (result === "device_revoked") {
    return { kind: "ok", text: "The device was revoked and its refresh path was disabled." };
  }
  if (result === "device_missing") {
    return { kind: "err", text: "The requested device record was not found for this account." };
  }
  return null;
}

export default async function DevicesPage({ searchParams }: Props) {
  const user = await requireUser();
  const params = await searchParams;
  const db = await readDb();
  const devices = db.devices.filter((item) => item.userId === user.id);
  const activeCount = devices.filter((item) => !item.revokedAt).length;
  const revokedCount = devices.length - activeCount;
  const seatUsagePercent = Math.max(8, Math.min(100, Math.round((activeCount / user.seatLimit) * 100)));
  const feedback = deviceResultMessage(String(params.result || ""));

  return (
    <section className="stack">
      <section className="hero-shell">
        <div className="card glass hero-copy">
          <div className="section-head">
            <p className="eyebrow">Devices</p>
            <h1>Authorized installs</h1>
            <p className="page-lead">
              Review every install tied to this account. Revoking a device also revokes the refresh tokens attached
              to it, which keeps the seat ledger and local authorization state aligned.
            </p>
          </div>
          <div className="pill-row">
            <span className="status-pill ok">Active seats: {activeCount}</span>
            <span className="status-pill">Seat limit: {user.seatLimit}</span>
            <span className="status-pill">Historical records: {devices.length}</span>
          </div>
          {feedback ? <div className={`notice ${feedback.kind}`}>{feedback.text}</div> : null}
          <div className="highlight-box">
            <p className="eyebrow">Seat occupancy</p>
            <div className="meter" aria-hidden="true">
              <div className="meter-fill" style={{ width: `${seatUsagePercent}%` }} />
            </div>
            <p className="caption">
              {activeCount} of {user.seatLimit} seats are currently occupied.
            </p>
          </div>
        </div>
        <aside className="card hero-panel">
          <div className="section-head tight">
            <p className="eyebrow">Ledger meaning</p>
            <h2>Each row is an install-level trust decision.</h2>
          </div>
          <div className="matrix-list">
            <div className="matrix-row">
              <strong>Install ID</strong>
              <span>The identifier the local CLI presents during browser authorization.</span>
            </div>
            <div className="matrix-row">
              <strong>Last seen</strong>
              <span>The most recent timestamp associated with activity from that machine.</span>
            </div>
            <div className="matrix-row">
              <strong>Revoke</strong>
              <span>Immediately invalidates the install's refresh path so the machine must be reauthorized.</span>
            </div>
          </div>
          <div className="button-row">
            <Link className="button secondary" href="/account">Back to account</Link>
            <Link className="button ghost" href="/how-it-works">Review CLI flow</Link>
          </div>
        </aside>
      </section>

      <div className="metric-strip">
        <div className="card metric-card">
          <span className="eyebrow">Active</span>
          <strong>{activeCount}</strong>
          <p className="muted">Machines that can still refresh local authorization state.</p>
        </div>
        <div className="card metric-card">
          <span className="eyebrow">Revoked</span>
          <strong>{revokedCount}</strong>
          <p className="muted">Historical installs that have already been detached from this account.</p>
        </div>
        <div className="card metric-card">
          <span className="eyebrow">Account</span>
          <strong>{user.seatLimit}</strong>
          <p className="muted">The total number of seats allowed before a new CLI approval is blocked.</p>
        </div>
      </div>

      <section className="card table-card">
        <div className="table-toolbar">
          <div className="section-head tight">
            <p className="eyebrow">Seat ledger</p>
            <h2>Every install, with clear status.</h2>
          </div>
          <span className="caption">{user.email}</span>
        </div>
        {devices.length === 0 ? (
          <div className="empty-state">
            <strong>No installs have been authorized for this account yet.</strong>
            <p className="muted">
              Run <code>archi login</code> on a local machine, approve it in the browser, and then return here
              to inspect the resulting seat record.
            </p>
          </div>
        ) : (
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
                {devices.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <div className="cell-stack">
                        <strong><code>{item.installId}</code></strong>
                        <span className="muted">Created {new Date(item.createdAt).toLocaleString()}</span>
                      </div>
                    </td>
                    <td>
                      <div className="cell-stack">
                        <strong>{item.deviceName}</strong>
                        <span className="muted">Last seen {new Date(item.lastSeenAt).toLocaleString()}</span>
                      </div>
                    </td>
                    <td>
                      <span className={item.revokedAt ? "status-pill danger" : "status-pill ok"}>
                        {item.revokedAt ? "revoked" : "active"}
                      </span>
                    </td>
                    <td>
                      {!item.revokedAt ? (
                        <form
                          action="/api/account/devices/revoke"
                          method="post"
                          data-confirm-message={`Revoke ${item.deviceName}? This will force the machine to reauthorize.`}
                        >
                          <input type="hidden" name="deviceId" value={item.id} />
                          <button className="button danger" type="submit" data-busy-label="Revoking...">Revoke</button>
                        </form>
                      ) : (
                        <span className="muted">No action required</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </section>
  );
}
