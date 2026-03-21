# Stripe Live Cutover

This runbook turns the current local billing scaffold into a real Stripe-backed subscription flow.

## 1. Create the recurring price

In Stripe:

1. Create a product for Architec Cloud.
2. Create one recurring monthly price at `$2.00`.
3. Copy the resulting `price_...` identifier.

The product model is fixed:

- `7-day free trial`
- then `$2/month`
- one subscription path only

## 2. Export required environment variables

Use the same names expected by the app:

```bash
export ARCHITEC_CLOUD_STRIPE_SECRET_KEY=sk_test_...
export ARCHITEC_CLOUD_STRIPE_PUBLISHABLE_KEY=pk_test_...
export ARCHITEC_CLOUD_STRIPE_PRICE_ID_MONTHLY=price_...
export ARCHITEC_CLOUD_STRIPE_WEBHOOK_SECRET=whsec_...
```

Optional but usually needed:

```bash
export ARCHITEC_CLOUD_APP_URL=http://127.0.0.1:3000
```

## 3. Check readiness

If Stripe CLI is not installed yet, install it locally into the repo:

```bash
cd architec-cloud
pnpm stripe:install-cli
```

Then run:

```bash
cd architec-cloud
pnpm stripe:check
```

Expected result:

- all four Stripe env vars are marked `[ok]`
- Stripe CLI is marked `[ok]`

## 4. Start webhook forwarding

In one terminal:

```bash
cd architec-cloud
pnpm stripe:listen
```

The Stripe CLI prints a webhook signing secret. Copy it into:

```bash
export ARCHITEC_CLOUD_STRIPE_WEBHOOK_SECRET=whsec_...
```

Then restart the Next.js server so the app reads the new secret.

## 5. Start the app

```bash
cd architec-cloud
pnpm build
pnpm start --hostname 127.0.0.1 --port 3000
```

Open:

```text
http://127.0.0.1:3000/account/billing
```

When Stripe is configured correctly, the page should show:

- `Billing mode: live integration ready`
- a monthly price ID readiness card marked `ready`
- buttons labeled `Open Stripe checkout` and `Open Stripe portal`

## 6. Run the first end-to-end test

1. Register or log in with a test account.
2. Open `/account/billing`.
3. Click `Open Stripe checkout`.
4. Complete checkout with Stripe test card details.
5. Return to the app.
6. Confirm the webhook updates the local user record.

Expected local outcomes:

- `stripeCustomerId` is stored on the user
- `stripeSubscriptionId` is stored on the user
- `stripeSubscriptionStatus` becomes `trialing` or `active`
- `licenseActive` stays `true`

The state is visible in:

- `/account`
- `/account/billing`
- `/admin`
- `.data/dev-db.json`

## 7. Verify the customer portal

After checkout:

1. Open `/account/billing`
2. Click `Open Stripe portal`

Expected result:

- Stripe Customer Portal opens
- the portal return path comes back to `/account/billing`

## 8. Webhook events that matter

The local webhook currently handles:

- `checkout.session.completed`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`

These are enough to attach the customer, attach the subscription, and keep `licenseActive` synchronized with Stripe subscription state.

## 9. Pre-production checks

Before switching from local test mode to hosted use:

1. Create production Stripe keys and production price IDs.
2. Configure a production webhook endpoint that points to `/api/webhooks/stripe`.
3. Confirm redirect URLs use the deployed domain.
4. Test one complete checkout and one cancellation in production mode.
5. Test one subscription deletion and verify the local account becomes inactive.

## 10. Known current boundary

This project now has a real Stripe integration path, but still uses:

- local JSON user storage
- local session handling
- local admin controls

That is acceptable for local and staging validation, but not for real commercial launch. A real launch should still migrate account storage and sessions to a proper managed backend.
