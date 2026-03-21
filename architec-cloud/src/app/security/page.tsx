import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Security boundary",
  description: "See what Architec Cloud manages online and what stays local in the CLI and skill workflow."
};

export default function SecurityPage() {
  return (
    <section className="stack">
      <div className="card glass hero-copy">
        <div className="section-head">
          <p className="eyebrow">Security</p>
          <h1>Identity in the browser. Execution off the website.</h1>
          <p className="page-lead">
            The portal exists to manage who can use the local tool, not to become the tool itself. Technical users
            should be able to see, quickly, which responsibilities stay online and which never need to leave the machine.
          </p>
        </div>
        <div className="hero-proof">
          <span className="status-pill ok">No repo upload requirement</span>
          <span className="status-pill">Seat policy enforced online</span>
          <span className="status-pill">Local analysis path preserved</span>
        </div>
      </div>

      <div className="two-up">
        <div className="card tinted">
          <div className="section-head tight">
            <p className="eyebrow">Local execution plane</p>
            <h2>Project code and analysis stay on the machine.</h2>
          </div>
          <div className="matrix-list">
            <div className="matrix-row">
              <strong>Repository access</strong>
              <span>Source code remains in the local workspace instead of being funneled through the website.</span>
            </div>
            <div className="matrix-row">
              <strong>Prompt and skill usage</strong>
              <span>Claude, Codex, and terminal flows remain the runtime environment for day-to-day work.</span>
            </div>
            <div className="matrix-row">
              <strong>Analysis execution</strong>
              <span>The portal is not the compute surface and should never read like a hidden remote runner.</span>
            </div>
          </div>
        </div>
        <div className="card tinted">
          <div className="section-head tight">
            <p className="eyebrow">Online control plane</p>
            <h2>Identity, subscription, and device state live on the web layer.</h2>
          </div>
          <div className="matrix-list">
            <div className="matrix-row">
              <strong>Accounts and sessions</strong>
              <span>Browser login, password handling, and approval history are centralized in the website.</span>
            </div>
            <div className="matrix-row">
              <strong>Seat and license policy</strong>
              <span>Subscription state, seat occupancy, and active-account checks are enforced before authorizing a machine.</span>
            </div>
            <div className="matrix-row">
              <strong>Revocation</strong>
              <span>Operators can block or detach stale installs without touching local repositories or bundled prompts.</span>
            </div>
          </div>
        </div>
      </div>

      <div className="grid">
        <div className="card feature-card">
          <div className="section-head tight">
            <p className="eyebrow">Browser login</p>
            <h2>The terminal never needs the account password</h2>
          </div>
          <ul className="list">
            <li>The CLI sends users to the browser instead of collecting passwords locally.</li>
            <li>The browser confirms identity and returns a short auth code to the waiting CLI.</li>
            <li>The local install keeps the resulting refresh token and lease for ongoing use.</li>
          </ul>
        </div>
        <div className="card feature-card">
          <div className="section-head tight">
            <p className="eyebrow">Local lease model</p>
            <h2>Short-lived approval with renewable local access</h2>
          </div>
          <ul className="list">
            <li>Local usage is backed by signed leases rather than permanent hard-coded credentials.</li>
            <li>Refresh records allow the product to keep access usable without forcing constant re-login.</li>
            <li>Revocation still remains possible from the account or admin surface.</li>
          </ul>
        </div>
      </div>

      <div className="card code-card glass">
        <div className="section-head tight">
          <p className="eyebrow">Design rule</p>
          <h2>The website should never feel like a hidden data pipe.</h2>
        </div>
        <pre>{`Website responsibilities:
- registration
- browser login
- subscription state
- device seats
- install approval

Local responsibilities:
- repository access
- analysis execution
- skill usage
- local CLI workflows`}</pre>
        <p className="muted">
          This separation is not just an implementation detail. It is the commercial and trust boundary of the product.
        </p>
      </div>

      <section className="card glass cta-panel">
        <div className="section-head">
          <p className="eyebrow">Move forward</p>
          <h2>Read the system flow, then evaluate the boundary yourself.</h2>
          <p className="page-lead">
            The product becomes easier to trust when users can immediately see what the portal controls and what
            continues to run entirely in their own environment.
          </p>
        </div>
        <div className="button-row">
          <Link className="button" href="/how-it-works">Read how it works</Link>
          <Link className="button secondary" href="/register">Start trial</Link>
        </div>
      </section>
    </section>
  );
}
