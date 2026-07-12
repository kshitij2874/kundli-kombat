# Kundli Kombat

An astrologer's practice run by an agent organization, packaged as a game: discover your cosmic identity, battle charts, and ask the Oracle.

## Runtime map

- `apps/web`: Vite + React web app for Cloudflare Pages
- `apps/api`: FastAPI agency exposed through a Cloudflare quick tunnel
- `convex`: schema, mutations, queries, actions, and live leaderboard
- `packages/shared`: shared schemas and types
- `workers/transit-ticker`: hourly Cloudflare Worker cron
- `hermes/kundli`: Hermes-authored Telegram skill, strict API helper, and `/hermes` contract
- `assets`: build-time static artwork

See `AGENTS.md` for build, safety, deployment, and ownership rules.

Environment setup is documented in `docs/ENV_SETUP.md`. After Convex is configured,
run `.venv/bin/python ../../scripts/seed_celebrities.py` from `apps/api`.

The live Telegram lane is [@KundliKombatBot](https://t.me/KundliKombatBot):
`hermes gateway` owns Telegram, the `kundli` skill calls the tunneled FastAPI
`POST /hermes` adapter, and Convex restores the sender's player memory.
