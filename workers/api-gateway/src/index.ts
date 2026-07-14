function originUrl(env: Env, pathAndSearch: string): URL {
  const origin = new URL(env.ORIGIN_URL);
  if (origin.protocol !== "https:") {
    throw new Error("ORIGIN_URL must use HTTPS");
  }
  return new URL(pathAndSearch, `${origin.origin}/`);
}

export function buildOriginRequest(request: Request, env: Env): Request {
  const incoming = new URL(request.url);
  const target = originUrl(env, `${incoming.pathname}${incoming.search}`);
  const headers = new Headers(request.headers);
  headers.set("X-KK-Origin-Secret", env.ORIGIN_SHARED_SECRET);

  return new Request(target, {
    method: request.method,
    headers,
    body: request.method === "GET" || request.method === "HEAD" ? null : request.body,
    redirect: "manual",
  });
}

async function checkOrigin(env: Env): Promise<Response> {
  return fetch(originUrl(env, "/health"), {
    headers: { "X-KK-Origin-Secret": env.ORIGIN_SHARED_SECRET },
    cf: { cacheTtl: 0, cacheEverything: false },
  });
}

async function gatewayHealth(env: Env): Promise<Response> {
  const started = Date.now();
  const upstream = await checkOrigin(env);
  return Response.json(
    {
      ok: upstream.ok,
      service: "kundli-kombat-api-gateway",
      originStatus: upstream.status,
      latencyMs: Date.now() - started,
    },
    {
      status: upstream.ok ? 200 : 503,
      headers: { "Cache-Control": "no-store" },
    },
  );
}

async function proxy(request: Request, env: Env): Promise<Response> {
  const upstream = await fetch(buildOriginRequest(request, env));
  return new Response(upstream.body, upstream);
}

export default {
  async fetch(request, env): Promise<Response> {
    try {
      if (new URL(request.url).pathname === "/__gateway/health") {
        return await gatewayHealth(env);
      }
      return await proxy(request, env);
    } catch (error) {
      console.error(JSON.stringify({
        message: "gateway request failed",
        path: new URL(request.url).pathname,
        error: error instanceof Error ? error.message : String(error),
      }));
      return Response.json(
        { ok: false, detail: "The Kundli Kombat API is briefly unavailable." },
        { status: 502, headers: { "Cache-Control": "no-store" } },
      );
    }
  },

  scheduled(_controller, env, ctx): void {
    ctx.waitUntil(
      checkOrigin(env)
        .then((response) => {
          console.log(JSON.stringify({
            message: "origin keepalive",
            ok: response.ok,
            status: response.status,
          }));
        })
        .catch((error: unknown) => {
          console.error(JSON.stringify({
            message: "origin keepalive failed",
            error: error instanceof Error ? error.message : String(error),
          }));
        }),
    );
  },
} satisfies ExportedHandler<Env>;
