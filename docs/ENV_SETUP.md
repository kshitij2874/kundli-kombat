# Environment setup

Never paste secret values into source files, chat, the web bundle, or Git history.

## 1. FastAPI agency

Create `apps/api/.env` by copying `apps/api/.env.example`, then replace the placeholders:

- `DEEPSEEK_API_KEY`: DeepSeek server key used only by FastAPI.
- `DEEPSEEK_BASE_URL`: keep `https://api.deepseek.com` unless DeepSeek changes its official endpoint.
- `DEEPSEEK_MODEL`: defaults to `deepseek-v4-flash` for low-latency Manager, Interpreter, and Referee calls.
- `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL`: values from the same Langfuse project. Use the exact region-specific base URL shown by Langfuse.
- `ELEVENLABS_API_KEY`: workspace key used only by the API for TTS.
- `LINKUP_API_KEY`: server-side key for celebrity lookup and news garnish.
- `DODO_API_KEY`: Dodo live-mode server key. Never put this in the web app.
- `CONVEX_URL`: deployment URL printed by `npx convex dev`.
- `WEB_ORIGIN`: `http://localhost:5173` locally, then the final `https://*.pages.dev` origin for the demo.

Restart FastAPI after changing the file. `GET /health` must then return `"traceExported": true`; verify the `manager.health` trace in Langfuse.

## 2. Convex

Run `npx convex dev` once and complete its login/project prompts. Put the printed deployment URL in the two runtime files above. Add server secrets directly to Convex, one at a time:

```sh
npx convex env set DEEPSEEK_API_KEY
npx convex env set LANGFUSE_PUBLIC_KEY
npx convex env set LANGFUSE_SECRET_KEY
npx convex env set LANGFUSE_HOST
npx convex env set ELEVENLABS_API_KEY
npx convex env set LINKUP_API_KEY
npx convex env set DODO_API_KEY
```

Each command securely prompts for its value. Do not append values to the command or shell history.

## 3. Web app

Create `apps/web/.env` from `apps/web/.env.example`:

- `VITE_CONVEX_URL`: public Convex deployment URL.
- `VITE_API_URL`: start as `http://localhost:8000`; replace it with the `https://*.trycloudflare.com` URL after the quick tunnel starts.

Only variables prefixed with `VITE_` enter the browser bundle. No secret key may use that prefix.

## 4. Cloudflare quick tunnel and Worker

Start FastAPI first, then run `scripts/start-tunnel.sh` once and leave that terminal running. Copy its HTTPS URL into `apps/web/.env` and the Hermes `kundli` skill configuration, then rebuild Pages.

Set the Worker API target without committing the changing tunnel URL:

```sh
cd workers/transit-ticker
npx wrangler secret put API_URL
```

Paste the tunnel URL only when Wrangler prompts. Deploy after the API has the `/internal/transits/refresh` endpoint.

## 5. Hermes

Hermes keys stay only in `~/.hermes/.env`. The repository must never copy or read that file. The Hermes-session-owned `kundli` skill receives only the public tunnel URL.

The repo-owned source is `hermes/kundli`. A Hermes session installs that directory as
the user-local `kundli` skill, after which the gateway must be restarted so Telegram
loads it. Verify without exposing credentials:

```sh
hermes skills list
hermes gateway status
python3 hermes/kundli/scripts/call_hermes.py --probe
python3 hermes/kundli/scripts/call_hermes.py --self-test
```

The skill must appear as `local` and `enabled`, and the gateway state must report
Telegram `connected`. The application contract is `POST /hermes`; do not call the
Telegram Bot API from this repository.
