import type { Metadata } from "next";
import Link from "next/link";

import {
  githubLatestChecksumsUrl,
  githubLatestInstallScriptUrl,
  githubLatestLinuxX64Url,
  githubLatestReleaseUrl,
  githubReleasesUrl,
  githubRepoUrl
} from "@/lib/config";

export const metadata: Metadata = {
  title: "Download",
  description: "Download Architec from GitHub Releases, then return to the website for registration, login, and CLI authorization."
};

export default function DownloadPage() {
  return (
    <section className="stack">
      <div className="card glass hero-copy">
        <div className="section-head">
          <p className="eyebrow">Download</p>
          <h1>Download from GitHub. Authorize through the browser.</h1>
          <p className="page-lead">
            Architec installers and release archives live on GitHub Releases. This website only handles registration,
            login, trial state, device seats, and browser approval after the CLI is installed locally.
          </p>
        </div>
        <div className="hero-proof">
          <span className="status-pill ok">Compiled Linux build live</span>
          <span className="status-pill ok">GitHub-hosted distribution</span>
          <span className="status-pill ok">Local CLI workflow</span>
          <span className="status-pill">Website does not host installers</span>
        </div>
        <div className="button-row">
          <a className="button" href={githubLatestLinuxX64Url} target="_blank" rel="noreferrer">
            Download Linux Build
          </a>
          <a className="button secondary" href={githubLatestInstallScriptUrl} target="_blank" rel="noreferrer">
            Download Install Script
          </a>
          <a className="button ghost" href={githubReleasesUrl} target="_blank" rel="noreferrer">
            Open GitHub Releases
          </a>
        </div>
      </div>

      <section className="pricing-shell">
        <div className="card code-card glass">
          <div className="section-head tight">
            <p className="eyebrow">Release path</p>
            <h2>Install the package, then bind the machine</h2>
          </div>
          <pre>{`Option A: direct installer path
curl -fsSL ${githubLatestInstallScriptUrl} -o install_prod.sh
bash install_prod.sh

Option B: manual archive path
Download ${githubLatestLinuxX64Url}
Extract the archive

Then run:
archi login
archi whoami`}</pre>
          <p className="muted">
            The compiled Linux artifact is now the preferred public package. Checksums and historical artifacts remain
            on GitHub Releases. Identity, seats, and authorization stay on the website.
          </p>
        </div>
        <div className="card price-card">
          <div className="section-head tight">
            <p className="eyebrow">After install</p>
            <h2>What happens next</h2>
          </div>
          <div className="matrix-list">
            <div className="matrix-row">
              <strong>1. Download the compiled build or installer script</strong>
              <span>Prefer the latest Linux compiled package or the hosted install script instead of editable source installs.</span>
            </div>
            <div className="matrix-row">
              <strong>2. Sign in on the website</strong>
              <span>Create the account or reuse an existing browser session before approving a machine.</span>
            </div>
            <div className="matrix-row">
              <strong>3. Run `archi login` and approve the machine</strong>
              <span>The install is checked against seat limits and linked to the account before the CLI receives local authorization state.</span>
            </div>
          </div>
        </div>
      </section>

      <div className="flow-grid">
        <div className="card download-card">
          <p className="eyebrow">Preferred artifact</p>
          <h2>Compiled Linux x86_64 build</h2>
          <p className="muted">This build reduces source exposure and is the public download target you should surface first for Linux users.</p>
          <a className="status-pill ok" href={githubLatestLinuxX64Url} target="_blank" rel="noreferrer">
            Download compiled build
          </a>
        </div>
        <div className="card download-card">
          <p className="eyebrow">Fast path</p>
          <h2>Hosted install script</h2>
          <p className="muted">Linux users can download the installer script from the release and avoid touching the source repository entirely.</p>
          <a className="status-pill ok" href={githubLatestInstallScriptUrl} target="_blank" rel="noreferrer">
            Open install script
          </a>
        </div>
        <div className="card download-card">
          <p className="eyebrow">Verification</p>
          <h2>Checksums and release notes</h2>
          <p className="muted">Keep SHA256 verification, historical builds, and operational notes in the dedicated release repository.</p>
          <div className="button-row">
            <a className="status-pill ok" href={githubLatestChecksumsUrl} target="_blank" rel="noreferrer">
              Open checksums
            </a>
            <a className="status-pill ok" href={githubRepoUrl} target="_blank" rel="noreferrer">
              Release repository
            </a>
          </div>
        </div>
      </div>

      <section className="card glass cta-panel">
        <div className="section-head">
          <p className="eyebrow">Next step</p>
          <h2>Download the build from GitHub, then use the website to authorize it.</h2>
          <p className="page-lead">
            GitHub is responsible for file delivery. The browser is responsible for identity confirmation. The CLI is
            responsible for local execution.
          </p>
        </div>
        <div className="button-row">
          <a className="button" href={githubLatestLinuxX64Url} target="_blank" rel="noreferrer">
            Get Linux Binary
          </a>
          <Link className="button secondary" href="/register">Register and authorize</Link>
          <a className="button ghost" href={githubLatestReleaseUrl} target="_blank" rel="noreferrer">
            Open latest release
          </a>
        </div>
      </section>
    </section>
  );
}
