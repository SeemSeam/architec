import type { Metadata } from "next";
import Link from "next/link";

import { pricingSummary } from "@/lib/billing";

export const metadata: Metadata = {
  title: "How it works",
  description: "Learn how Architec Cloud handles registration and browser approval while the local CLI keeps analysis in the user environment."
};

export default function HowItWorksPage() {
  return (
    <section className="stack">
      <div className="card glass hero-copy">
        <div className="section-head">
          <p className="eyebrow">How it works</p>
          <h1>A browser control plane wrapped around a local CLI.</h1>
          <p className="page-lead">
            Users should not need to learn token plumbing. They create an account, run `archi login`, approve
            the install in a browser, and return to the same local toolchain they already use.
          </p>
        </div>
        <div className="hero-proof">
          <span className="status-pill ok">No repo upload required</span>
          <span className="status-pill ok">{pricingSummary()}</span>
          <span className="status-pill">Short auth code + renewable lease</span>
          <span className="status-pill">Works with Claude, Codex, and terminal usage</span>
        </div>
      </div>

      <div className="flow-grid">
        <div className="card flow-card">
          <span className="flow-number">01</span>
          <h2>Register the account</h2>
          <p className="muted">Create the account, start the trial, and expose the seat state that will govern local installs.</p>
        </div>
        <div className="card flow-card">
          <span className="flow-number">02</span>
          <h2>Launch the browser handoff</h2>
          <p className="muted">The CLI opens a browser-based authorization flow instead of collecting the account password in the terminal.</p>
        </div>
        <div className="card flow-card">
          <span className="flow-number">03</span>
          <h2>Approve one machine</h2>
          <p className="muted">The browser confirms identity, returns a short auth code to the waiting CLI, and the CLI stores renewable local credentials.</p>
        </div>
        <div className="card flow-card">
          <span className="flow-number">04</span>
          <h2>Keep working locally</h2>
          <p className="muted">Future commands reuse refresh state and signed leases so day-to-day usage stays in the local workflow.</p>
        </div>
      </div>

      <div className="rail-grid">
        <div className="card code-card glass">
          <div className="section-head tight">
            <p className="eyebrow">Quickstart</p>
            <h2>The shortest path from empty machine to active local session</h2>
          </div>
          <pre>{`archi login
archi whoami
archi status --json`}</pre>
          <p className="muted">
            After the browser callback completes, the local CLI can report identity, seat status, and lease
            health without treating the website as the execution surface.
          </p>
        </div>
        <div className="card timeline-card">
          <div className="section-head tight">
            <p className="eyebrow">Control flow</p>
            <h2>Identity on the web. Authorization returned to the CLI.</h2>
          </div>
          <div className="matrix-list">
            <div className="matrix-row">
              <strong>Browser session</strong>
              <span>Registers users, signs them in, and presents the install approval page.</span>
            </div>
            <div className="matrix-row">
              <strong>Authorization exchange</strong>
              <span>Returns a short auth code to the waiting CLI callback instead of embedding long-lived secrets in the terminal.</span>
            </div>
            <div className="matrix-row">
              <strong>Local session</strong>
              <span>Stores renewable state and continues normal work inside the machine-local execution path.</span>
            </div>
          </div>
        </div>
      </div>

      <div className="grid">
        <div className="card feature-card">
          <div className="section-head tight">
            <p className="eyebrow">What the CLI does</p>
            <h2>Local execution and local skill usage</h2>
          </div>
          <ul className="list">
            <li>Runs analysis locally inside the user environment.</li>
            <li>Uses the approved lease and refresh token to maintain access without constant re-login.</li>
            <li>Continues to work with the same local Claude or Codex skill flow.</li>
          </ul>
        </div>
        <div className="card feature-card">
          <div className="section-head tight">
            <p className="eyebrow">Operational result</p>
            <h2>A rollout path that feels technical, but not brittle</h2>
          </div>
          <ul className="list">
            <li>The user gets a browser login instead of manual token handling.</li>
            <li>The operator gets seat limits and revocation instead of uncontrolled redistribution.</li>
            <li>The product keeps a crisp split between identity control and local execution.</li>
          </ul>
        </div>
      </div>

      <section className="card glass cta-panel">
        <div className="section-head">
          <p className="eyebrow">Next steps</p>
          <h2>Start the trial when you are ready to bind the first machine.</h2>
          <p className="page-lead">
            The product path stays intentionally small: one plan, one browser handoff, one local execution surface.
          </p>
        </div>
        <div className="button-row">
          <Link className="button" href="/register">Start trial</Link>
          <Link className="button secondary" href="/security">Review the security boundary</Link>
        </div>
      </section>
    </section>
  );
}
