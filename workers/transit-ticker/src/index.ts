interface Env { API_URL: string }

export default {
  async scheduled(_: ScheduledController, env: Env, ctx: ExecutionContext): Promise<void> {
    ctx.waitUntil(fetch(`${env.API_URL}/internal/transits/refresh`, { method: "POST" }));
  },
  async fetch(): Promise<Response> {
    return Response.json({ ok: true, service: "kundli-kombat-transit-ticker" });
  },
};

