import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

const round = v.object({
  name: v.string(), p1Score: v.number(), p2Score: v.number(), compatibilityScore: v.number(),
  line: v.string(), aspects: v.array(v.string()),
});

export const create = mutation({
  args: {
    code: v.string(), p1Id: v.id("players"), p2Id: v.optional(v.id("players")), celebrity: v.optional(v.string()),
    rounds: v.array(round), verdictPct: v.number(), prediction: v.string(), latencyMs: v.number(),
    costUsd: v.number(), langfuseTraceId: v.string(),
  },
  returns: v.object({ battleId: v.id("battles"), cardId: v.id("cards") }),
  handler: async (ctx, args) => {
    const cardId = await ctx.db.insert("cards", {
      playerId: args.p1Id, type: "scorecard", title: `${args.verdictPct}% chart match`,
      glyphs: ["☉", "☽", "⚔"], line: args.prediction,
      rarity: args.verdictPct >= 85 ? "mythic" : args.verdictPct >= 70 ? "rare" : "common",
      createdAt: Date.now(),
    });
    const battleId = await ctx.db.insert("battles", { ...args, cardId, createdAt: Date.now() });
    return { battleId, cardId };
  },
});

export const leaderboard = query({
  args: {},
  returns: v.array(v.any()),
  handler: async (ctx) => {
    const battles = await ctx.db.query("battles").withIndex("by_created_at").order("desc").take(50);
    return battles.map((item) => ({ code: item.code, celebrity: item.celebrity, verdictPct: item.verdictPct, createdAt: item.createdAt }));
  },
});

