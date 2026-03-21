import type { Metadata } from "next";
import Link from "next/link";

import { pricingSummary } from "@/lib/billing";

export const metadata: Metadata = {
  title: "Local-first CLI access control",
  description: "Keep Architec analysis local while managing registration, seats, and browser-based CLI authorization online."
};

export default function HomePage() {
  return (
    <section className="stack">
      <section className="hero-shell">
        <div className="card glass hero-copy">
          <div className="section-head">
            <p className="eyebrow">Architec Cloud</p>
            <h1>Run Architec locally. Control access online.</h1>
            <p className="page-lead">
              Architec Cloud wraps the local `archi` CLI in a clean browser identity plane. Registration,
              seats, install approval, lease refresh, and revocation stay online. Repositories, prompts,
              and analysis execution stay local inside Claude, Codex, and the terminal.
            </p>
          </div>
          <div className="inline-metrics">
            <div className="inline-metric">
              <strong>7 days</strong>
              <span>free trial to bind the first machine</span>
            </div>
            <div className="inline-metric">
              <strong>$2/mo</strong>
              <span>single subscription after the trial</span>
            </div>
            <div className="inline-metric">
              <strong>3 seats</strong>
              <span>default device ceiling per account</span>
            </div>
          </div>
          <div className="hero-actions">
            <Link className="button" href="/register">Start 7-day trial</Link>
            <Link className="button secondary" href="/how-it-works">See the system flow</Link>
          </div>
          <div className="hero-proof">
            <span className="status-pill ok">Local-first by design</span>
            <span className="status-pill ok">Browser-issued CLI access</span>
            <span className="status-pill">Signed Ed25519 leases</span>
            <span className="status-pill">{pricingSummary()}</span>
          </div>
        </div>
        <aside className="hero-panel hero-panel-grid">
          <div className="card hero-data-card tinted">
            <div className="panel-header">
              <span className="panel-label">Authorization trace</span>
              <span className="status-pill ok">Healthy path</span>
            </div>
            <div className="signal-list">
              <div className="signal-row">
                <strong>1. Browser session validates the operator identity</strong>
                <span>Users authenticate on the web layer instead of typing account credentials into the CLI.</span>
              </div>
              <div className="signal-row">
                <strong>2. The install is approved against seat policy</strong>
                <span>Account state, active devices, and license status are checked before the machine is trusted.</span>
              </div>
              <div className="signal-row">
                <strong>3. CLI receives a short code and signed lease</strong>
                <span>The local machine stores renewable authorization state without turning the site into the runtime.</span>
              </div>
            </div>
          </div>
          <div className="card hero-console">
            <div className="panel-header">
              <span className="panel-label">Local command path</span>
              <span className="status-pill ghost">Execution stays local</span>
            </div>
            <div className="mini-shell">{`$ archi login
Open browser approval...
Lease issued for install demo-mbp

$ archi whoami
plan: standard
device: demo-mbp
lease: active`}</div>
          </div>
        </aside>
      </section>

      <section className="metric-strip">
        <div className="card metric-card">
          <span className="eyebrow">Execution surface</span>
          <strong>Local execution</strong>
          <p className="muted">Analysis stays in the same local stack your users already trust: Claude, Codex, and the `archi` command.</p>
        </div>
        <div className="card metric-card">
          <span className="eyebrow">Identity plane</span>
          <strong>Web-managed access</strong>
          <p className="muted">Registration, login, device issuance, revocation, and subscription state live in one managed control layer.</p>
        </div>
        <div className="card metric-card">
          <span className="eyebrow">Offer</span>
          <strong>7-day trial</strong>
          <p className="muted">Every account starts free for one week, then moves to a single $2/month subscription.</p>
        </div>
      </section>

      <section className="stack">
        <div className="section-head">
          <p className="eyebrow">System map</p>
          <h2>A technical product story that reads like a control plane, not a marketing shell.</h2>
          <p className="page-lead">
            The site needs to tell users exactly what the product is doing: where identity lives, where the
            machine is authorized, and why local execution remains local.
          </p>
        </div>
        <div className="flow-grid">
          <div className="card flow-card">
            <span className="flow-number">01</span>
            <h3>Account and seat ledger</h3>
            <p className="muted">The browser owns registration, trial state, active seats, license status, and install history.</p>
          </div>
          <div className="card flow-card">
            <span className="flow-number">02</span>
            <h3>Machine approval checkpoint</h3>
            <p className="muted">`archi login` creates a deliberate approval step so each install is attached to one real account event.</p>
          </div>
          <div className="card flow-card">
            <span className="flow-number">03</span>
            <h3>Signed local authorization</h3>
            <p className="muted">The local CLI stores renewable state and continues working inside the same Claude or Codex skill flow.</p>
          </div>
          <div className="card flow-card">
            <span className="flow-number">04</span>
            <h3>Revocation remains online</h3>
            <p className="muted">Operators can revoke stale installs later without touching project files or shipping a new binary.</p>
          </div>
        </div>
      </section>

      <section className="rail-grid">
        <div className="card diagram-card glass">
          <div className="section-head tight">
            <p className="eyebrow">Execution boundary</p>
            <h2>What the website controls, and what it never needs to touch.</h2>
          </div>
          <div className="two-up">
            <div className="highlight-box">
              <p className="eyebrow">Online control plane</p>
              <div className="matrix-list">
                <div className="matrix-row">
                  <strong>Identity and browser sessions</strong>
                  <span>Register, log in, authorize installs, and keep an auditable approval trail.</span>
                </div>
                <div className="matrix-row">
                  <strong>Seat and subscription policy</strong>
                  <span>Enforce device limits, trial windows, and active license status from one managed place.</span>
                </div>
                <div className="matrix-row">
                  <strong>Revocation and GitHub distribution</strong>
                  <span>Detach stale installs while public installers and release notes stay on GitHub instead of the website.</span>
                </div>
              </div>
            </div>
            <div className="highlight-box">
              <p className="eyebrow">Local execution plane</p>
              <div className="matrix-list">
                <div className="matrix-row">
                  <strong>Repository access</strong>
                  <span>Codebases remain on the user machine instead of becoming a website upload requirement.</span>
                </div>
                <div className="matrix-row">
                  <strong>Analysis and prompts</strong>
                  <span>Architec runs inside the same terminal, Claude, or Codex environment users already trust.</span>
                </div>
                <div className="matrix-row">
                  <strong>Daily workflows</strong>
                  <span>The product monetizes access control without forcing a browser IDE rewrite.</span>
                </div>
              </div>
            </div>
          </div>
        </div>
        <aside className="card timeline-card">
          <div className="section-head tight">
            <p className="eyebrow">Built for</p>
            <h2>Teams turning a local tool into an operable product.</h2>
          </div>
          <div className="step-list">
            <div className="step-item">
              <span className="step-index">1</span>
              <div className="cell-stack">
                <strong>Local-first product teams</strong>
                <span className="muted">Keep the valuable runtime in the CLI instead of rebuilding it as a web app.</span>
              </div>
            </div>
            <div className="step-item">
              <span className="step-index">2</span>
              <div className="cell-stack">
                <strong>Operators who need device control</strong>
                <span className="muted">Track installs, enforce seats, and block inactive accounts without exposing long-lived secrets.</span>
              </div>
            </div>
            <div className="step-item">
              <span className="step-index">3</span>
              <div className="cell-stack">
                <strong>Technical buyers who inspect boundaries</strong>
                <span className="muted">Show clearly that the site handles access control, not repository ingestion or analysis execution.</span>
              </div>
            </div>
          </div>
        </aside>
      </section>

      <section className="stack">
        <div className="section-head">
          <p className="eyebrow">User journey</p>
          <h2>A short path from first install to reusable local session.</h2>
          <p className="page-lead">
            The friction should be deliberate where it matters, and absent everywhere else. One browser approval,
            then back to a durable local workflow.
          </p>
        </div>
        <div className="feature-grid">
          <div className="card feature-card">
            <p className="eyebrow">Step 1</p>
            <h3>Open the account layer</h3>
            <p className="muted">Registration exposes trial state, seats, and authorization without changing the local tool or the GitHub release path.</p>
          </div>
          <div className="card feature-card">
            <p className="eyebrow">Step 2</p>
            <h3>Launch `archi login`</h3>
            <p className="muted">The CLI opens a browser handoff instead of embedding account credentials inside the terminal.</p>
          </div>
          <div className="card feature-card">
            <p className="eyebrow">Step 3</p>
            <h3>Approve one machine</h3>
            <p className="muted">A short-lived auth code and signed lease unlock the install while the identity flow remains in the browser.</p>
          </div>
          <div className="card feature-card">
            <p className="eyebrow">Result</p>
            <h3>Keep the workflow local</h3>
            <p className="muted">Users continue inside Claude, Codex, and the terminal with clear device visibility and revocation controls.</p>
          </div>
        </div>
        <div className="button-row">
          <Link className="button" href="/how-it-works">Read the quickstart</Link>
          <Link className="button secondary" href="/security">Review the security boundary</Link>
        </div>
      </section>

      <section className="stack">
        <div className="section-head">
          <p className="eyebrow">Trust boundary</p>
          <h2>Say the hard part out loud.</h2>
          <p className="page-lead">
            The first serious question is always the same: is the portal a hidden data channel, or is it only
            the control plane? The site should answer that immediately.
          </p>
        </div>
        <div className="grid">
          <div className="card feature-card">
            <h3>The portal manages identity</h3>
            <p className="muted">Accounts, sessions, device seats, and subscription state live on the website, where operators can actually control them.</p>
          </div>
          <div className="card feature-card">
            <h3>The CLI keeps execution local</h3>
            <p className="muted">The browser approves the machine, but the analysis itself stays in the local toolchain and skill flow.</p>
          </div>
          <div className="card feature-card">
            <h3>Operators can revoke access</h3>
            <p className="muted">Seat limits and device revocation create a real commercial boundary instead of shipping an uncontrolled binary.</p>
          </div>
        </div>
      </section>

      <section className="card glass cta-panel">
        <div className="section-head">
          <p className="eyebrow">Start here</p>
          <h2>Start the trial. Authorize one install. Keep the rest local.</h2>
          <p className="page-lead">
            The commercial model stays intentionally small: one offer, one browser approval path, and one local execution surface.
          </p>
        </div>
        <div className="button-row">
          <Link className="button" href="/register">Start 7-day trial</Link>
          <Link className="button secondary" href="/pricing">See pricing</Link>
        </div>
      </section>
    </section>
  );
}
