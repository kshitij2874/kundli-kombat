import { describe, expect, it } from "vitest";

import { battlePower } from "./battle-ui";

describe("battlePower", () => {
  it("shows both real API scores after the round impact", () => {
    expect(battlePower(41, true)).toBe(41);
    expect(battlePower(62, true)).toBe(62);
  });

  it("keeps the pre-reveal bar full without changing the real score", () => {
    expect(battlePower(62, false)).toBe(100);
  });
});
