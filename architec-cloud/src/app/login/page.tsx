import type { Metadata } from "next";
import Link from "next/link";

import { monthlyPriceUsd, trialDays } from "@/lib/billing";

export const metadata: Metadata = {
  title: "Log in",
  description: "Sign back into Architec Cloud to manage devices, subscription state, and browser-based CLI authorization."
};

type Props = {
  searchParams: Promise<{
    error?: string;
  }>;
};

function loginErrorMessage(error: string): string {
  if (error === "invalid_credentials") {
    return "Email or password is incorrect.";
  }
  if (error === "rate_limited") {
    return "Too many login attempts from this browser context. Wait a few minutes and try again.";
  }
  return "";
}

export default async function LoginPage({ searchParams }: Props) {
  const params = await searchParams;
  const errorMessage = loginErrorMessage(String(params.error || ""));

  return (
    <section className="auth-shell">
      <div className="card auth-aside glass">
        <div className="section-head">
          <p className="eyebrow">Login</p>
          <h1>Resume device control and browser authorization.</h1>
          <p className="page-lead">
            Sign back in with the same account that issued your CLI lease, device seats, and account settings.
            The browser remains the identity surface for both account management and `archi login`.
          </p>
        </div>
        <div className="field-chip-row">
          <span className="status-pill ok">Same account, same seat ledger</span>
          <span className="status-pill">No terminal password entry</span>
        </div>
        <div className="matrix-list">
          <div className="matrix-row">
            <strong>Browser identity</strong>
            <span>Reuse the same signed-in browser state when the CLI requests install approval.</span>
          </div>
          <div className="matrix-row">
            <strong>Control surfaces</strong>
            <span>Keep seat management, downloads, license state, and future billing controls in one place.</span>
          </div>
          <div className="matrix-row">
            <strong>Commercial model</strong>
            <span>The billing path is fixed to a {trialDays}-day free trial followed by ${monthlyPriceUsd}/month.</span>
          </div>
        </div>
        <div className="mini-shell">{`$ archi login
Reuses your browser session
Approve the machine

$ archi status --json
lease_state: valid`}</div>
      </div>
      <div className="card auth-form-card">
        <div className="form-shell">
          <div className="form-intro">
            <div className="section-head tight">
              <p className="eyebrow">Sign in</p>
              <h2>Access account, subscription, and device pages.</h2>
            </div>
            <p className="caption">
              This login is the browser-side entry point for account operations and CLI authorization approvals.
            </p>
          </div>
          {errorMessage ? <div className="notice err">{errorMessage}</div> : null}
          <form className="form" action="/api/auth/login" method="post">
            <label>
              Email
              <input type="email" name="email" autoComplete="email" placeholder="you@example.com" required />
            </label>
            <label>
              Password
              <input
                type="password"
                name="password"
                autoComplete="current-password"
                placeholder="Your account password"
                required
              />
            </label>
            <button className="button" type="submit">Continue to account</button>
          </form>
          <div className="highlight-box">
            <p className="eyebrow">After login</p>
            <ul className="list">
              <li>Review active devices and revoke any stale installs.</li>
              <li>Inspect trial or license state from the account console.</li>
              <li>Approve new machines when the local CLI opens a browser handoff.</li>
            </ul>
          </div>
          <p className="field-note">
            Need a new account? Go to <Link href="/register"><strong>Register</strong></Link>.
          </p>
        </div>
      </div>
    </section>
  );
}
