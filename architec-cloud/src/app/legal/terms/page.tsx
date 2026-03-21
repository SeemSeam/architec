import Link from "next/link";

import { defaultSeatLimit, monthlyPriceUsd, trialDays } from "@/lib/billing";
import { supportEmail } from "@/lib/config";

export default function TermsPage() {
  return (
    <section className="card legal-copy">
      <div className="section-head">
        <p className="eyebrow">Terms</p>
        <h1>Terms of service</h1>
        <p className="page-lead">
          Effective March 21, 2026. These terms govern access to Architec Cloud, the browser-based identity plane
          around the local `archi` CLI, and the account-bound download and authorization surfaces.
        </p>
      </div>
      <div className="pill-row">
        <span className="status-pill ok">One commercial offer</span>
        <span className="status-pill">{trialDays}-day trial</span>
        <span className="status-pill">${monthlyPriceUsd}/month after trial</span>
      </div>
      <section>
        <h3>1. Service scope</h3>
        <p className="muted">
          Architec Cloud manages registration, browser login, device approval, signed CLI authorization, account controls,
          and related subscription state. The service does not promise to host or execute repository analysis in the browser.
          The valuable runtime remains local to the user machine.
        </p>
      </section>
      <section>
        <h3>2. Account responsibilities</h3>
        <ul className="list">
          <li>Users must provide accurate registration information and keep credentials confidential.</li>
          <li>Each account is responsible for activity performed through its browser session and approved local installs.</li>
          <li>Users must promptly revoke devices that are lost, shared improperly, or no longer under their control.</li>
        </ul>
      </section>
      <section>
        <h3>3. Trial, subscription, and pricing</h3>
        <ul className="list">
          <li>The service currently follows one commercial path only: {trialDays} days free, then ${monthlyPriceUsd}/month.</li>
          <li>The trial begins when the account is created, not when the first device is approved.</li>
          <li>When recurring billing is live, renewals continue until canceled. Pricing changes or tax changes must be disclosed before they take effect for existing customers.</li>
        </ul>
      </section>
      <section>
        <h3>4. Seats, devices, and authorization</h3>
        <ul className="list">
          <li>Accounts default to {defaultSeatLimit} active device seats unless the operator explicitly changes that limit.</li>
          <li>Each `archi login` approval binds one install to the account and may be blocked if the seat limit is already reached.</li>
          <li>CLI access may be denied or later invalidated based on account state, device revocation, expired refresh state, or signed lease validity.</li>
        </ul>
      </section>
      <section>
        <h3>5. Acceptable use</h3>
        <ul className="list">
          <li>Do not attempt to bypass seat controls, share account access outside your organization, or tamper with authorization checks.</li>
          <li>Do not probe, overload, scrape, or attack the service or use it for unlawful or abusive activity.</li>
          <li>Do not redistribute account-bound builds or credentials in a way that defeats the intended access-control model.</li>
        </ul>
      </section>
      <section>
        <h3>6. Suspension and termination</h3>
        <p className="muted">
          Access may be suspended or terminated for non-payment, fraud, abuse, security risk, legal exposure, or material
          breach of these terms. A local binary or source checkout may still exist on the user machine, but browser-managed
          authorization, lease refresh, downloads, and seat issuance can be stopped when the service relationship ends.
        </p>
      </section>
      <section>
        <h3>7. Cancellation and refunds</h3>
        <p className="muted">
          Users may cancel future renewals through the billing surface when live billing is enabled. During local validation
          or manual billing phases, cancellation and refund handling remains operator-managed and case specific. Public launch
          should replace that manual path with a documented self-serve flow on the <Link href="/account/billing"><strong>billing page</strong></Link>.
        </p>
      </section>
      <section>
        <h3>8. Warranty and liability limits</h3>
        <p className="muted">
          The service is provided on an as-available basis. To the maximum extent permitted by law, Architec Cloud disclaims
          implied warranties and limits liability for indirect, incidental, or consequential damages. Public launch should have
          these terms reviewed by counsel in the jurisdiction where the service is offered.
        </p>
      </section>
      <section>
        <h3>9. Contact</h3>
        <p className="muted">
          {supportEmail
            ? `Contract, billing, and account notices can be directed to ${supportEmail}.`
            : "For this local validation deployment, contractual and account notices are handled directly by the operator running the service instance. Configure ARCHITEC_CLOUD_SUPPORT_EMAIL before public launch."}
        </p>
      </section>
    </section>
  );
}
