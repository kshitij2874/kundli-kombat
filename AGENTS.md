# Kundli Kombat build rules

Kundli Kombat is a Hermes Buildathon Track 03 project. Protect working-product, observability, agency, eval, and partner-integration rubric points before polish.

## Non-negotiables

- Build in the phase order from the build brief and commit at every phase boundary.
- Telegram must run through `hermes gateway` with a `kundli` skill calling the API. Never implement a direct Telegram Bot API client here.
- Hermes sessions own `hermes/` scaffolding, skill/config work, and prompt iteration. Codex owns the web app, Convex functions, FastAPI internals, and tests.
- Every LLM request must be instrumented in Langfuse. Store trace ID, latency, and cost with the resulting Convex record.
- The Desk Manager plans, delegates, reviews specialist output, and may retry once. Deterministic chart and battle math never comes from an LLM.
- Guard against death, health, pregnancy, legal, financial-doom, abuse, prompt-injection, and under-13 requests. Return a warm refusal and create an escalation record.
- Every reading ends with: “for reflection and fun, not fate.”
- Referee narration may roast chart dynamics, never the real person or protected/personal traits.
- Keep text reading and battle tasks under 60 seconds and $0.10.
- Do not use runtime image generation. Static art may be generated once at build time.

## Deployment map

- Web: Vite build deployed to Cloudflare Pages with `wrangler pages deploy dist`.
- API: local FastAPI on port 8000 exposed by one long-running `cloudflared` quick tunnel.
- State: Convex Cloud.
- Cloudflare Worker: hourly transit-ticker refresh cron.
- No Vercel and no alternate production hosting.

## Secrets

- `apps/api/.env` is the API secret source of truth and must never be committed.
- Convex secrets are set with `npx convex env set`; never expose them to client code.
- Web receives only `VITE_CONVEX_URL` and `VITE_API_URL` through `apps/web/.env`.
- Hermes credentials remain in `~/.hermes/.env`; do not copy them into this repository.
- Commit `.env.example` files with names only and safe placeholders.

## Engineering constraints

- Sidereal identity and battle calculations use Lahiri ayanamsa; tropical is optional behind a setting.
- Unknown birth time uses a noon/solar chart and must be labeled approximate.
- Battle scores are deterministic. Identical chart pairs and house rules must produce identical round scores.
- Interpreter output must include non-empty evidence referencing placements that exist in the chart.
- Preserve the exact Convex collection and core field names from the build brief; fields may be added but not renamed.
- Avoid speculative scope. Cut in this order: r3f arena, odds meter, quests, management UI depth, eval breadth.
- Never cut onboarding-to-reading, core battle, partner evidence, submission buffer, or backup videos.

## Human-only boundaries

- Kshitij runs Hermes sessions, maintains the gateway, confirms live-mode partner accounts, recruits players, records backup videos, gathers mentor evidence, and submits by 17:00.
- Never commit credentials, payment details, user birth data, tunnel URLs intended to stay private, or mentor evidence containing private information.

