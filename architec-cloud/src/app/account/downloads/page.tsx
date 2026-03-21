import type { Metadata } from "next";
import Link from "next/link";

import { requireUser } from "@/lib/auth";
import { defaultPlanLabel } from "@/lib/billing";
import {
  githubLatestChecksumsUrl,
  githubLatestInstallScriptUrl,
  githubLatestLinuxX64Url,
  githubLatestReleaseUrl,
  githubReleasesUrl,
  githubRepoUrl
} from "@/lib/config";

export const metadata: Metadata = {
  title: "Account downloads",
  description: "Open the GitHub Releases feed and use your account to authorize Architec installs after download."
};

export default async function DownloadsPage() {
  const user = await requireUser();

  return (
    <section className="stack">
      <section className="hero-shell">
        <div className="card glass hero-copy">
          <div className="section-head">
            <p className="eyebrow">Downloads</p>
            <h1>GitHub distributes the build. This account authorizes the install.</h1>
            <p className="page-lead">
              Downloads remain public on GitHub Releases so the website does not act as a file host. This account still
              controls trial status, seat limits, device revocation, and browser approval after the package is installed.
            </p>
          </div>
          <div className="pill-row">
            <span className="status-pill ok">{defaultPlanLabel}</span>
            <span className="status-pill">Account: {user.email}</span>
            <span className="status-pill ok">Authorization enforced here</span>
            <span className="status-pill ok">Compiled Linux build available</span>
          </div>
          <div className="button-row">
            <a className="button" href={githubLatestLinuxX64Url} target="_blank" rel="noreferrer">
              Download Linux Build
            </a>
            <a className="button secondary" href={githubLatestInstallScriptUrl} target="_blank" rel="noreferrer">
              Install Script
            </a>
            <Link className="button ghost" href="/account">Back to account</Link>
          </div>
        </div>
        <aside className="card hero-panel">
          <div className="section-head tight">
            <p className="eyebrow">Split of responsibilities</p>
            <h2>Public delivery outside. Access control inside.</h2>
          </div>
          <div className="matrix-list">
            <div className="matrix-row">
              <strong>GitHub</strong>
              <span>Publishes compiled binaries, install scripts, checksums, version history, and release notes.</span>
            </div>
            <div className="matrix-row">
              <strong>Website account</strong>
              <span>Registers users, starts the trial, enforces seats, and records approval events for each machine.</span>
            </div>
            <div className="matrix-row">
              <strong>Local workflow</strong>
              <span>After download, `archi login` remains the bind step for every machine that should be allowed to run.</span>
            </div>
          </div>
        </aside>
      </section>

      <section className="surface-grid">
        <div className="card surface-card">
          <p className="eyebrow">Install flow</p>
          <h2>What you do after downloading</h2>
          <pre>{`Download from GitHub Releases
Prefer archi-linux-x86_64.tar.gz or install_prod.sh
Install Architec locally
archi login
archi whoami`}</pre>
          <p className="muted">The website never needs to ship the file in order to control whether the install is allowed to run.</p>
        </div>
        <div className="card surface-card">
          <p className="eyebrow">Verification</p>
          <h2>What this page should help with</h2>
          <p className="muted">Use this page as a control surface for version links, install guidance, and account authorization state while artifacts stay on GitHub.</p>
        </div>
      </section>

      <div className="flow-grid">
        <div className="card download-card">
          <p className="eyebrow">Preferred artifact</p>
          <h2>Compiled Linux build</h2>
          <p className="muted">Use the compiled Linux package when you want the lower-exposure runtime rather than a Python source install.</p>
          <a className="status-pill ok" href={githubLatestLinuxX64Url} target="_blank" rel="noreferrer">
            Download build
          </a>
        </div>
        <div className="card download-card">
          <p className="eyebrow">Installer path</p>
          <h2>Hosted install script</h2>
          <p className="muted">Use the release-hosted installer script when you want to bootstrap the compiled Linux build without cloning any repository.</p>
          <a className="status-pill ok" href={githubLatestInstallScriptUrl} target="_blank" rel="noreferrer">
            Open install script
          </a>
        </div>
        <div className="card download-card">
          <p className="eyebrow">Verification</p>
          <h2>Release notes and checksums</h2>
          <p className="muted">Keep public downloads, release notes, and checksum files in a dedicated artifact repository while authorization remains enforced by browser approval and lease refresh.</p>
          <div className="button-row">
            <a className="status-pill ok" href={githubLatestChecksumsUrl} target="_blank" rel="noreferrer">
              Open checksums
            </a>
            <a className="status-pill ok" href={githubReleasesUrl} target="_blank" rel="noreferrer">
              Release feed
            </a>
            <a className="status-pill ok" href={githubRepoUrl} target="_blank" rel="noreferrer">
              Repository
            </a>
            <a className="status-pill ok" href={githubLatestReleaseUrl} target="_blank" rel="noreferrer">
              Latest release
            </a>
          </div>
        </div>
      </div>
    </section>
  );
}
