import type { Metadata } from "next";
import Link from "next/link";

import { cliMinVersion, supportEmail } from "@/lib/config";

export const metadata: Metadata = {
  title: "Status",
  description: "Current operational status for Architec Cloud browser identity, CLI authorization, billing mode, and release delivery."
};

const components = [
  {
    name: "Browser identity and account pages",
    state: "Operational in local validation mode",
    tone: "ok",
    detail: "Registration, login, account pages, device views, and admin controls are available in the local JSON-backed environment."
  },
  {
    name: "CLI authorization exchange",
    state: "Operational",
    tone: "ok",
    detail: "The browser approval page, auth-code exchange, signed lease issuance, and refresh flow are wired for local testing."
  },
  {
    name: "Recurring billing",
    state: "Stubbed for local validation",
    tone: "warn",
    detail: "The commercial model is defined, but live payment processing should not be considered production-ready until the Stripe cutover is finished."
  },
  {
    name: "Release distribution",
    state: "Operational through GitHub Releases",
    tone: "ok",
    detail: "The website links users out to GitHub for installers and version history while browser identity and device authorization remain enforced here."
  }
];

export default function StatusPage() {
  return (
    <section className="stack">
      <section className="card glass hero-copy">
        <div className="section-head">
          <p className="eyebrow">Status</p>
          <h1>Current service status is local validation, not public production SLA.</h1>
          <p className="page-lead">
            This page should tell users what is genuinely live, what is still stubbed, and what is not yet a committed
            public service surface. Today the stack is suitable for local testing, private beta, and technical validation.
          </p>
        </div>
        <div className="hero-proof">
          <span className="status-pill ok">Register and login flow active</span>
          <span className="status-pill ok">CLI browser approval active</span>
          <span className="status-pill warn">Billing still local stub</span>
          <span className="status-pill">{cliMinVersion ? `Minimum supported CLI version: ${cliMinVersion}` : "No CLI minimum version enforced"}</span>
        </div>
      </section>

      <section className="surface-grid">
        {components.map((item) => (
          <div key={item.name} className="card surface-card">
            <div className="panel-header">
              <span className="panel-label">{item.name}</span>
              <span className={`status-pill ${item.tone}`}>{item.state}</span>
            </div>
            <p className="muted">{item.detail}</p>
          </div>
        ))}
      </section>

      <section className="grid">
        <div className="card feature-card">
          <div className="section-head tight">
            <p className="eyebrow">Escalation</p>
            <h2>What to do during a user-visible issue</h2>
          </div>
          <ul className="list">
            <li>Check the account console and device list before asking the user to reinstall anything.</li>
            <li>Confirm whether the failure is in browser login, approval redirect, auth-code exchange, or lease refresh.</li>
            <li>Use the support surface to collect install ID, timestamps, and `archi status --json` output.</li>
          </ul>
        </div>
        <div className="card feature-card">
          <div className="section-head tight">
            <p className="eyebrow">Public honesty</p>
            <h2>Do not market undeployed paths as if they were live</h2>
          </div>
          <p className="muted">
            Before public launch, this page should be backed by real monitoring, incident ownership, and uptime expectations.
            For now it is an explicit disclosure page for the current pre-launch state.
          </p>
          <p className="muted">
            {supportEmail
              ? `If this environment is exposed to beta users, operational incidents should route to ${supportEmail}.`
              : "If this environment is exposed to beta users, configure ARCHITEC_CLOUD_SUPPORT_EMAIL before announcing it publicly."}
          </p>
          <div className="button-row">
            <Link className="button secondary" href="/support">Open support guide</Link>
            <Link className="button secondary" href="/faq">Read FAQ</Link>
          </div>
        </div>
      </section>
    </section>
  );
}
