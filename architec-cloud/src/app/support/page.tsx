import type { Metadata } from "next";
import Link from "next/link";

import { supportEmail } from "@/lib/config";

export const metadata: Metadata = {
  title: "Support",
  description: "Operational support guidance for Architec Cloud accounts, device authorization, and local CLI access issues."
};

export default function SupportPage() {
  const mailboxConfigured = Boolean(supportEmail);

  return (
    <section className="stack">
      <section className="hero-shell">
        <div className="card glass hero-copy">
          <div className="section-head">
            <p className="eyebrow">Support</p>
            <h1>Support should resolve account, seat, and authorization problems without touching repository data.</h1>
            <p className="page-lead">
              The support surface exists for browser login failures, device revocation issues, trial or subscription questions,
              and `archi login` authorization failures. It is not a repository upload channel.
            </p>
          </div>
          <div className="hero-proof">
            <span className="status-pill ok">Account and device issues</span>
            <span className="status-pill">Authorization troubleshooting</span>
            <span className="status-pill">No code upload required</span>
          </div>
          <div className="note-box">
            <p className="eyebrow">Contact path</p>
            <p className="muted">
              {mailboxConfigured
                ? `Primary support mailbox: ${supportEmail}`
                : "No support mailbox is configured in this local environment yet. For public launch, set ARCHITEC_CLOUD_SUPPORT_EMAIL and route it to a monitored inbox."}
            </p>
          </div>
        </div>
        <aside className="card hero-panel">
          <div className="section-head tight">
            <p className="eyebrow">Before contacting support</p>
            <h2>Collect the smallest useful diagnostic set.</h2>
          </div>
          <ul className="list">
            <li>The email address tied to the account.</li>
            <li>The output of `archi status --json`, with secrets redacted if you share it externally.</li>
            <li>The device name and install ID shown by the CLI or account device list.</li>
            <li>The exact page or command where the failure happened and the UTC time if possible.</li>
          </ul>
        </aside>
      </section>

      <section className="surface-grid">
        <div className="card surface-card">
          <p className="eyebrow">Support scope</p>
          <h2>What support can fix directly</h2>
          <div className="matrix-list">
            <div className="matrix-row">
              <strong>Browser account access</strong>
              <span>Registration issues, login failures, session confusion, account state questions, and role mistakes.</span>
            </div>
            <div className="matrix-row">
              <strong>Seat and device problems</strong>
              <span>Revoke stale installs, explain seat usage, and help recover from “seat limit reached” states.</span>
            </div>
            <div className="matrix-row">
              <strong>Authorization failures</strong>
              <span>Investigate browser approval failures, exchange failures, lease refresh failures, and revoked-device errors.</span>
            </div>
          </div>
        </div>
        <div className="card surface-card">
          <p className="eyebrow">What support should not ask for</p>
          <h2>Keep the local-first boundary intact</h2>
          <ul className="list">
            <li>Support should not require full repository uploads for standard account or authorization issues.</li>
            <li>Support should not request plaintext passwords, refresh tokens, or browser cookies.</li>
            <li>Support should prefer command output, timestamps, install IDs, and screenshots over raw project data.</li>
          </ul>
        </div>
      </section>

      <section className="grid">
        <div className="card feature-card">
          <div className="section-head tight">
            <p className="eyebrow">Recommended response targets</p>
            <h2>Keep expectations explicit</h2>
          </div>
          <ul className="list">
            <li>Authorization outage or login outage: acknowledge within 1 business day.</li>
            <li>Billing or trial question: acknowledge within 1 business day.</li>
            <li>Feature request or packaging request: queue and confirm within 3 business days.</li>
          </ul>
        </div>
        <div className="card feature-card">
          <div className="section-head tight">
            <p className="eyebrow">Self-serve pages</p>
            <h2>Send users to the right surface first</h2>
          </div>
          <div className="button-row">
            <Link className="button secondary" href="/faq">FAQ</Link>
            <Link className="button secondary" href="/security">Security</Link>
            <Link className="button secondary" href="/status">Status</Link>
          </div>
          <p className="muted">
            A good support process uses public documentation to remove repeat questions before they become manual tickets.
          </p>
        </div>
      </section>
    </section>
  );
}
