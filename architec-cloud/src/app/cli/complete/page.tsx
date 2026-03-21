import type { Metadata } from "next";
import Link from "next/link";

import ContinueToTarget from "@/app/cli/complete/continue-to-target";

export const metadata: Metadata = {
  title: "CLI authorization result",
  description: "See the browser-side result of an Architec CLI authorization request before returning to the local callback."
};

type Props = {
  searchParams: Promise<{
    result?: string;
    next?: string;
    install_id?: string;
    device_name?: string;
  }>;
};

export default async function CliCompletePage({ searchParams }: Props) {
  const params = await searchParams;
  const result = String(params.result || "approved");
  const nextUrl = String(params.next || "/account");
  const installId = String(params.install_id || "");
  const deviceName = String(params.device_name || "");
  const approved = result === "approved";
  const upgradeRequired = result === "upgrade_required";
  const denied = !approved && !upgradeRequired;

  return (
    <section className="auth-shell">
      <div className="card auth-aside glass">
        <div className="section-head">
          <p className="eyebrow">CLI authorization</p>
          <h1>{approved
            ? "The install has been approved in the browser."
            : upgradeRequired
              ? "The CLI must be upgraded before this install can be approved."
              : "The install request was denied."}</h1>
          <p className="page-lead">
            {approved
              ? "The browser has finished its part of the flow. The last step is returning the result to the waiting local CLI callback."
              : upgradeRequired
                ? "No auth code was issued. Download the current build from GitHub Releases, then restart the browser approval flow from the updated CLI."
                : "No local credentials were issued. The browser will now return a denial result to the waiting CLI callback."}
          </p>
        </div>
        <div className="field-chip-row">
          <span className={approved ? "status-pill ok" : "status-pill danger"}>
            Result: {approved ? "approved" : upgradeRequired ? "upgrade required" : "denied"}
          </span>
          <span className="status-pill">Browser step complete</span>
        </div>
        <div className="note-box">
          <p className="eyebrow">Install summary</p>
          <p><strong>Install:</strong> <code>{installId}</code></p>
          <p><strong>Device:</strong> {deviceName || "Unknown device"}</p>
        </div>
        <div className="mini-shell">{approved
          ? `$ browser step complete
$ redirect to local callback
$ cli exchanges auth code
$ local session becomes active`
          : upgradeRequired
            ? `$ browser version gate triggered
$ no auth code issued
$ install must be upgraded
$ retry the browser flow after reinstall`
            : `$ browser denial recorded
$ redirect to local callback
$ cli stops waiting
$ no local lease issued`}</div>
      </div>

      <div className="card auth-form-card">
        <div className="section-head tight">
          <p className="eyebrow">Return path</p>
          <h2>{approved
            ? "Send the auth result back to the local CLI."
            : upgradeRequired
              ? "Upgrade the local CLI before restarting the authorization flow."
              : "Return the denial result to the local CLI."}</h2>
        </div>
        <div className={approved ? "notice ok" : "notice err"}>
          {approved
            ? "The next redirect should deliver the auth code to the local callback, after which the CLI will exchange it for local session state."
            : upgradeRequired
              ? "This install is below the minimum supported CLI version. Update from the latest GitHub release before requesting authorization again."
              : "The next redirect should notify the local CLI that the request was denied, so the terminal can stop waiting and report the refusal clearly."}
        </div>
        {!upgradeRequired ? <ContinueToTarget nextUrl={nextUrl} /> : null}
        <div className="button-row">
          {!upgradeRequired ? <a className="button" href={nextUrl}>Continue now</a> : null}
          <Link className="button secondary" href="/account">Back to account</Link>
          <Link className="button ghost" href="/account/devices">Manage devices</Link>
        </div>
      </div>
    </section>
  );
}
