import Link from "next/link";

import { supportEmail } from "@/lib/config";

export default function PrivacyPage() {
  return (
    <section className="card legal-copy">
      <div className="section-head">
        <p className="eyebrow">Privacy</p>
        <h1>Privacy policy</h1>
        <p className="page-lead">
          Effective March 21, 2026. This policy explains what Architec Cloud stores to operate browser login,
          device authorization, account management, and the local CLI access flow.
        </p>
      </div>
      <div className="pill-row">
        <span className="status-pill ok">Local-first product boundary</span>
        <span className="status-pill">Browser identity and seat control online</span>
        <span className="status-pill">CLI execution stays on the user machine</span>
      </div>
      <section>
        <h3>1. Data we collect</h3>
        <div className="matrix-list">
          <div className="matrix-row">
            <strong>Account identity</strong>
            <span>Email address, password hash, account creation time, plan code, trial state, and license status.</span>
          </div>
          <div className="matrix-row">
            <strong>Browser session records</strong>
            <span>Session identifiers, creation time, and expiration time so account pages and CLI approval pages can stay signed in.</span>
          </div>
          <div className="matrix-row">
            <strong>Device and authorization records</strong>
            <span>Install ID, device name, creation time, last-seen time, revocation time, short-lived auth codes, and refresh-token metadata.</span>
          </div>
          <div className="matrix-row">
            <strong>Billing and operations metadata</strong>
            <span>Subscription status, billing customer references, operator actions, and support correspondence when those features are enabled.</span>
          </div>
        </div>
      </section>
      <section>
        <h3>2. Data we do not collect by design</h3>
        <ul className="list">
          <li>Repository contents are not uploaded as part of normal account registration or `archi login` authorization.</li>
          <li>Prompt bodies, local analysis output, and source code stay outside the website unless you intentionally send them to support.</li>
          <li>Payment card numbers are expected to be handled by a payment processor when recurring billing is enabled, not stored directly by Architec Cloud.</li>
        </ul>
      </section>
      <section>
        <h3>3. Why we process this data</h3>
        <ul className="list">
          <li>Authenticate browser users and maintain account sessions.</li>
          <li>Authorize local CLI installs, enforce seat limits, sign leases, and revoke stale devices.</li>
          <li>Prevent abuse, investigate failures, respond to support issues, and protect the service from account compromise.</li>
          <li>Operate billing, renewal, cancellation, refunds, and account administration when recurring billing is active.</li>
        </ul>
      </section>
      <section>
        <h3>4. Retention</h3>
        <div className="matrix-list">
          <div className="matrix-row">
            <strong>Browser sessions</strong>
            <span>Current local implementation keeps browser sessions for up to 7 days unless the user logs out or the record is removed.</span>
          </div>
          <div className="matrix-row">
            <strong>Authorization codes</strong>
            <span>CLI approval codes are short-lived and expire after 10 minutes.</span>
          </div>
          <div className="matrix-row">
            <strong>Refresh-token metadata</strong>
            <span>Current local implementation keeps refresh-token records for up to 30 days unless revoked earlier.</span>
          </div>
          <div className="matrix-row">
            <strong>Devices and account records</strong>
            <span>Device history and account records may be retained while the account is active and for a reasonable period afterward for security, billing, and audit purposes.</span>
          </div>
        </div>
      </section>
      <section>
        <h3>5. Sharing and subprocessors</h3>
        <p className="muted">
          Architec Cloud may rely on infrastructure, email, authentication, hosting, payment, logging, and support vendors
          to operate the service. Those providers receive only the data necessary to provide their part of the service,
          and they act under contractual or operational controls appropriate for that role.
        </p>
      </section>
      <section>
        <h3>6. Security posture</h3>
        <ul className="list">
          <li>Passwords are stored as derived hashes rather than plaintext.</li>
          <li>Local CLI authorization uses short codes, renewable refresh state, and signed Ed25519 leases.</li>
          <li>No internet-facing service can guarantee perfect security, so users should also protect their email account, browser session, and local machine.</li>
        </ul>
      </section>
      <section>
        <h3>7. Your controls</h3>
        <ul className="list">
          <li>You can revoke devices from the account console when a machine should no longer retain access.</li>
          <li>You can request account deletion, data export, correction, or support help for an authorization issue.</li>
          <li>You should review the <Link href="/security"><strong>security</strong></Link> and <Link href="/how-it-works"><strong>how it works</strong></Link> pages to understand the local-versus-online boundary.</li>
        </ul>
      </section>
      <section>
        <h3>8. Contact</h3>
        <p className="muted">
          {supportEmail
            ? `Privacy and data requests can be sent to ${supportEmail}.`
            : "For this local validation deployment, privacy and data requests are handled directly by the operator running the service instance. Configure ARCHITEC_CLOUD_SUPPORT_EMAIL before public launch."}
        </p>
      </section>
    </section>
  );
}
