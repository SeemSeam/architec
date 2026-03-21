# architec-cloud

`architec-cloud` is the standalone web service for Architec registration, login, device management, billing integration, and CLI authorization.

The current local flow is modeled as a single subscription: `7` days free, then `$2/month`.

## Current scope

This scaffold is intentionally local-first:

- Next.js App Router structure
- account, pricing, legal, download, and admin pages
- route handlers for auth, admin, and CLI authorization
- local JSON-backed state for development
- Ed25519-signed CLI lease payloads

It is designed to be replaced later with:

- Supabase Auth
- Supabase Postgres
- Stripe Billing
- Vercel deployment

## Start

```bash
cd architec-cloud
pnpm install
pnpm dev
```

Open:

```text
http://127.0.0.1:3000
```

Run a local smoke check against the running server:

```bash
pnpm smoke
```

Run browser e2e coverage with Playwright:

```bash
pnpm playwright:install
pnpm test:e2e
```

## Local dev notes

- The first registered account is promoted to admin.
- State is stored under `.data/dev-db.json`.
- Public signing key is exposed at `/api/cli/public-key`.
- The current route handlers are local-development implementations, not production auth.
- Billing remains stubbed locally, but the product copy and account model assume a 7-day trial followed by $2/month.
- Configure `ARCHITEC_CLOUD_SUPPORT_EMAIL` before exposing the site to real users.
- Playwright e2e runs use `.data-e2e/` and a dedicated port `3100` so they do not collide with the main local server on `3000`.

## Stripe mode

The billing layer automatically stays in local stub mode unless all required Stripe values are present:

```bash
export ARCHITEC_CLOUD_STRIPE_SECRET_KEY=sk_test_...
export ARCHITEC_CLOUD_STRIPE_PUBLISHABLE_KEY=pk_test_...
export ARCHITEC_CLOUD_STRIPE_PRICE_ID_MONTHLY=price_...
export ARCHITEC_CLOUD_STRIPE_WEBHOOK_SECRET=whsec_...
```

With those values configured:

- `pnpm stripe:install-cli` installs Stripe CLI into `tools/bin/stripe`
- `/api/billing/checkout` creates a Stripe Checkout subscription session
- `/api/billing/portal` creates a Stripe Billing Portal session
- `/api/webhooks/stripe` verifies webhook signatures and syncs local user billing state
- `pnpm stripe:check` validates required env vars and local CLI readiness
- `pnpm stripe:listen` forwards Stripe webhook events to the local webhook endpoint

Without them:

- the same pages keep working in local stub mode
- billing buttons redirect back with clear stub feedback
- no Stripe network call is attempted

## Next migration steps

- replace file-backed state with Supabase
- move password/session handling to Supabase Auth
- replace local admin actions with authenticated operator workflows
- finish Stripe product, price, and portal configuration in the live account
- deploy to Vercel with managed environment variables

## Runbooks

- local Stripe cutover checklist: `docs/stripe-live-cutover.md`
- launch operations runbook: `../docs/launch-ops-runbook.md`
