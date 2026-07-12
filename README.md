# Kundli Kombat

An astrologer's practice run by an agent organization, packaged as a game: discover your cosmic identity, battle charts, and ask the Oracle.

## Runtime map

- `apps/web`: Vite + React web app for Cloudflare Pages
- `apps/api`: FastAPI agency exposed through a Cloudflare quick tunnel
- `convex`: schema, mutations, queries, actions, and live leaderboard
- `packages/shared`: shared schemas and types
- `workers/transit-ticker`: hourly Cloudflare Worker cron
- `hermes`: reserved for Hermes-session work
- `assets`: build-time static artwork

See `AGENTS.md` for build, safety, deployment, and ownership rules.
