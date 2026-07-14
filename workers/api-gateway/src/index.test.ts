import { describe, expect, it } from "vitest";

import { buildOriginRequest } from "./index";

const env = {
  ORIGIN_URL: "https://kundli-kombat-api.onrender.com",
  ORIGIN_SHARED_SECRET: "real-origin-secret",
} as Env;

describe("API gateway", () => {
  it("preserves the path and query while routing to the stable origin", () => {
    const request = new Request("https://gateway.example/places?q=New%20Delhi");
    const forwarded = buildOriginRequest(request, env);

    expect(forwarded.url).toBe(
      "https://kundli-kombat-api.onrender.com/places?q=New%20Delhi",
    );
  });

  it("replaces an attacker-supplied origin credential", () => {
    const request = new Request("https://gateway.example/celebrities", {
      headers: { "X-KK-Origin-Secret": "attacker-value" },
    });
    const forwarded = buildOriginRequest(request, env);

    expect(forwarded.headers.get("X-KK-Origin-Secret")).toBe("real-origin-secret");
  });
});
