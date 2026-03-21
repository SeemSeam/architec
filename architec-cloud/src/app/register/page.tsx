import type { Metadata } from "next";
import Link from "next/link";

import { monthlyPriceUsd, pricingSummary, trialDays } from "@/lib/billing";

export const metadata: Metadata = {
  title: "Register",
  description: "Create an Architec Cloud account, start the 7-day trial, and unlock browser-based CLI authorization."
};

type Props = {
  searchParams: Promise<{
    error?: string;
  }>;
};

function registerErrorMessage(error: string): string {
  if (error === "email_exists") {
    return "This email is already registered. Sign in instead or use a different address.";
  }
  if (error === "invalid_input") {
    return "Enter a valid email and a password with at least 8 characters.";
  }
  if (error === "server_error") {
    return "Registration did not complete. Try again.";
  }
  if (error === "rate_limited") {
    return "Too many registration attempts from this browser context. Wait a bit before trying again.";
  }
  return "";
}

export default async function RegisterPage({ searchParams }: Props) {
  const params = await searchParams;
  const errorMessage = registerErrorMessage(String(params.error || ""));

  return (
    <section className="auth-shell">
      <div className="card auth-aside glass">
        <div className="section-head">
          <p className="eyebrow">Register</p>
          <h1>Create the control account for local Architec installs.</h1>
          <p className="page-lead">
            This site is the access-control layer around the local CLI. The account you create here will own browser
            login, device seats, approval history, and the signed lease flow behind `archi login`.
          </p>
        </div>
        <div className="field-chip-row">
          <span className="status-pill ok">Trial starts immediately</span>
          <span className="status-pill">Same account for site and CLI approval</span>
        </div>
        <div className="note-box">
          <p className="eyebrow">Commercial path</p>
          <p className="muted">This account starts with a {trialDays}-day free trial and then continues at ${monthlyPriceUsd}/month. There is no second plan to migrate onto later.</p>
        </div>
        <div className="matrix-list">
          <div className="matrix-row">
            <strong>After signup</strong>
            <span>You can log into the site, run `archi login`, approve a machine, and inspect devices from one account surface.</span>
          </div>
          <div className="matrix-row">
            <strong>For local testing</strong>
            <span>The first registered user is promoted to admin so you can exercise device and license controls end to end.</span>
          </div>
          <div className="matrix-row">
            <strong>Offer shape</strong>
            <span>The product uses one offer only: {pricingSummary()}.</span>
          </div>
        </div>
        <div className="mini-shell">{`$ archi login
Browser approval opens
Install is attached to this account

$ archi whoami
license: active`}</div>
      </div>
      <div className="card auth-form-card">
        <div className="form-shell">
          <div className="form-intro">
            <div className="section-head tight">
              <p className="eyebrow">New account</p>
              <h2>Start with the same browser-first flow your users will follow.</h2>
            </div>
            <p className="caption">
              Use a real email and password. After registration you will land in the account console and can
              immediately test CLI authorization.
            </p>
          </div>
          {errorMessage ? <div className="notice err">{errorMessage}</div> : null}
          <form className="form" action="/api/auth/register" method="post">
            <label>
              Email
              <input type="email" name="email" autoComplete="email" placeholder="you@example.com" required />
            </label>
            <label>
              Password
              <input
                type="password"
                name="password"
                autoComplete="new-password"
                minLength={8}
                placeholder="At least 8 characters"
                required
              />
            </label>
            <button className="button" type="submit">Create account</button>
          </form>
          <div className="highlight-box">
            <p className="eyebrow">What happens next</p>
            <ul className="list">
              <li>Account session is created in the browser.</li>
              <li>You can open the account page and inspect seat state.</li>
              <li>The same identity will be reused when the CLI requests browser approval.</li>
            </ul>
          </div>
          <p className="field-note">
            Already registered? Go to <Link href="/login"><strong>Login</strong></Link>.
          </p>
        </div>
      </div>
    </section>
  );
}
