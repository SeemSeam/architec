import type { Metadata } from "next";
import Link from "next/link";

import { requireUser } from "@/lib/auth";
import { cliMinVersion } from "@/lib/config";
import { activeDevices, findDeviceByInstallId, readDb } from "@/lib/db";
import { getCliVersionGate } from "@/lib/version";

export const metadata: Metadata = {
  title: "Authorize CLI install",
  description: "Approve or deny a local Architec CLI install from the browser and review current seat state."
};

type Props = {
  searchParams: Promise<{
    state?: string;
    install_id?: string;
    device_name?: string;
    redirect_uri?: string;
    app_version?: string;
  }>;
};

export default async function CliLoginPage({ searchParams }: Props) {
  const user = await requireUser();
  const params = await searchParams;
  const db = await readDb();
  const devices = activeDevices(db, user.id);
  const existingDevice = findDeviceByInstallId(db, user.id, String(params.install_id || ""));
  const seatLimitReached = !existingDevice && devices.length >= user.seatLimit;
  const versionGate = getCliVersionGate(params.app_version);
  const versionBlocked = versionGate.invalidClientVersion || versionGate.invalidMinimumVersion || versionGate.upgradeRequired;

  return (
    <section className="auth-shell">
      <div className="card auth-aside glass">
        <div className="section-head">
          <p className="eyebrow">CLI Login</p>
          <h1>Approve a local Architec install in one deliberate step.</h1>
          <p className="page-lead">
            The browser stays responsible for identity while the CLI receives a short-lived auth code and a signed lease.
          </p>
        </div>
        <div className="field-chip-row">
          <span className={user.licenseActive ? "status-pill ok" : "status-pill danger"}>
            License: {user.licenseActive ? "active" : "inactive"}
          </span>
          <span className={seatLimitReached ? "status-pill danger" : "status-pill ok"}>
            Seats: {devices.length}/{user.seatLimit}
          </span>
          <span className="status-pill">Existing install: {existingDevice ? "yes" : "no"}</span>
          <span className={versionBlocked ? "status-pill danger" : "status-pill ok"}>
            CLI: {versionGate.clientVersion || params.app_version || "not reported"}
          </span>
          <span className="status-pill">
            Min: {versionGate.minimumVersion || (cliMinVersion || "not enforced")}
          </span>
        </div>
        <div className="note-box">
          <p className="eyebrow">Install details</p>
          <p><strong>Install:</strong> <code>{params.install_id || ""}</code></p>
          <p><strong>Device:</strong> {params.device_name || ""}</p>
          <p><strong>CLI version:</strong> {params.app_version || "not provided"}</p>
        </div>
        <div className="matrix-list">
          <div className="matrix-row">
            <strong>Approval scope</strong>
            <span>The browser is approving access for a local CLI install, not uploading project code or prompt contents.</span>
          </div>
          <div className="matrix-row">
            <strong>Return path</strong>
            <span>Approval returns a short-lived auth code to the waiting CLI callback, which then performs the exchange locally.</span>
          </div>
          <div className="matrix-row">
            <strong>Ongoing usage</strong>
            <span>The resulting refresh token and signed lease keep the install usable without interactive login on every command.</span>
          </div>
        </div>
      </div>
      <form className="card auth-form-card form" action="/api/cli/authorize" method="post">
        <input type="hidden" name="state" value={params.state || ""} />
        <input type="hidden" name="installId" value={params.install_id || ""} />
        <input type="hidden" name="deviceName" value={params.device_name || ""} />
        <input type="hidden" name="redirectUri" value={params.redirect_uri || ""} />
        <input type="hidden" name="appVersion" value={params.app_version || ""} />
        <div className="section-head tight">
          <p className="eyebrow">Authorization</p>
          <h2>Issue an auth code for this local install.</h2>
        </div>
        <div className={seatLimitReached || !user.licenseActive || versionBlocked ? "notice err" : "notice ok"}>
          {versionGate.invalidMinimumVersion
            ? versionGate.detail
            : versionGate.invalidClientVersion
              ? "The CLI version string is invalid. Reinstall from the latest GitHub release before retrying browser authorization."
              : versionGate.upgradeRequired
                ? versionGate.detail
                : seatLimitReached
            ? "Seat limit is already reached for this account. Revoke an old device before authorizing a new one."
            : !user.licenseActive
              ? "This account is currently inactive, so the install cannot be approved."
              : "After approval, the browser will send a callback to the waiting local CLI and the CLI will exchange it for a refresh token plus a signed lease."}
        </div>
        <div className="button-row">
          <button className="button" type="submit" disabled={seatLimitReached || !user.licenseActive || versionBlocked}>
            Authorize this install
          </button>
          <button className="button secondary" formAction="/api/cli/deny" type="submit">
            Deny and return
          </button>
          <Link className="button ghost" href="/account/devices">Manage devices</Link>
        </div>
      </form>
    </section>
  );
}
