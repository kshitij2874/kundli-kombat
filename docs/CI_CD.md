# CI/CD setup

The workflow at `.github/workflows/ci-cd.yml` runs tests, lint, Convex typechecking,
and the Vite production build on every pull request and `main` push. A failed check
blocks both production deploy jobs.

Create a GitHub environment named `production`, then add:

## Environment secrets

- `CONVEX_DEPLOY_KEY`: deploy key for the same Convex deployment used by
  `apps/api/.env` as `CONVEX_URL`. At present that is the active
  `grandiose-possum-908` deployment; do not point CI at another deployment unless the
  API is migrated at the same time.
- `CLOUDFLARE_API_TOKEN`: token scoped to Cloudflare Pages edit/deploy access.
- `CLOUDFLARE_ACCOUNT_ID`: account ID containing the `kundli-kombat` Pages project.

## Environment variables

- `VITE_CONVEX_URL`: the same Convex URL used by the API, currently
  `https://grandiose-possum-908.eu-west-1.convex.cloud`.
- `VITE_API_URL`: the current public `https://*.trycloudflare.com` FastAPI tunnel URL.

The quick-tunnel URL changes after a tunnel restart. Update `VITE_API_URL` in the
GitHub `production` environment before the next Pages deployment whenever that happens.
The FastAPI process itself remains local by design and is not deployed by Actions.

For safer judging-day operation, enable required reviewers on the `production`
environment. Verification still runs automatically; deployment waits for approval.
