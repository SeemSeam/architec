import type { Metadata } from "next";
import type { ReactNode } from "react";
import Link from "next/link";
import { IBM_Plex_Sans, Sora } from "next/font/google";

import "@/app/globals.css";
import FormGuard from "@/app/form-guard";
import { currentUser } from "@/lib/auth";
import { appName } from "@/lib/config";

const displayFont = Sora({
  subsets: ["latin"],
  variable: "--font-display"
});

const bodyFont = IBM_Plex_Sans({
  subsets: ["latin"],
  variable: "--font-body"
});

export const metadata: Metadata = {
  title: {
    default: appName,
    template: `%s | ${appName}`
  },
  description: "Registration, billing, and CLI authorization service for Architec."
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  const user = await currentUser();

  return (
    <html lang="en">
      <body className={`${displayFont.variable} ${bodyFont.variable}`}>
        <FormGuard />
        <div className="shell">
          <div className="ambient ambient-a" />
          <div className="ambient ambient-b" />
          <header className="topbar">
            <div className="wrap topbar-inner">
              <Link className="brand" href="/">
                <span className="brand-mark">A</span>
                <span className="brand-copy">
                  <strong>{appName}</strong>
                  <span>Control plane for local AI workflows</span>
                </span>
              </Link>
              <nav className="nav nav-primary">
                <Link href="/">Product</Link>
                <Link href="/how-it-works">How it works</Link>
                <Link href="/pricing">Pricing</Link>
                <Link href="/download">Download</Link>
                <Link href="/security">Security</Link>
                <Link href="/support">Support</Link>
                <Link href="/status">Status</Link>
                <Link href="/faq">FAQ</Link>
                {user ? <Link href="/account">Account</Link> : null}
                {user?.isAdmin ? <Link href="/admin">Admin</Link> : null}
              </nav>
              <div className="nav nav-cta">
                {user ? (
                  <>
                    <span className="nav-session" title={user.email}>{user.email}</span>
                    <form className="nav-form" action="/api/auth/logout" method="post">
                      <button className="button secondary" type="submit">Log out</button>
                    </form>
                  </>
                ) : (
                  <>
                    <Link className="nav-link" href="/login">Log in</Link>
                    <Link className="button" href="/register">Start trial</Link>
                  </>
                )}
              </div>
            </div>
          </header>
          <main className="wrap page">{children}</main>
          <footer className="footer">
            <div className="wrap footer-inner">
              <div>
                <p className="eyebrow">Commercial model</p>
                <p className="muted">
                  Browser identity, seat enforcement, and CLI authorization live behind one offer: 7 days free, then $2/month.
                </p>
              </div>
              <div className="footer-links">
                <Link href="/how-it-works">How it works</Link>
                <Link href="/pricing">Pricing</Link>
                <Link href="/download">Download</Link>
                <Link href="/security">Security</Link>
                <Link href="/support">Support</Link>
                <Link href="/status">Status</Link>
                <Link href="/faq">FAQ</Link>
                <Link href="/legal/privacy">Privacy</Link>
                <Link href="/legal/terms">Terms</Link>
              </div>
            </div>
          </footer>
        </div>
      </body>
    </html>
  );
}
