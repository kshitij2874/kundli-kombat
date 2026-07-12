import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

const tone = v.union(v.literal("comfort"), v.literal("straight"), v.literal("roast"));
const kind = v.union(v.literal("identity"), v.literal("daily"), v.literal("placement"), v.literal("oracle"), v.literal("deep"));
const evidence = v.array(v.object({ planet: v.string(), sign: v.string(), longitude: v.number() }));

export const create = mutation({
  args: {
    playerId: v.id("players"), kind, question: v.optional(v.string()), tone,
    text: v.string(), evidence, latencyMs: v.number(), costUsd: v.number(), langfuseTraceId: v.string(),
  },
  returns: v.id("readings"),
  handler: (ctx, args) => ctx.db.insert("readings", { ...args, createdAt: Date.now() }),
});

export const recentOracle = query({
  args: { playerId: v.id("players"), limit: v.optional(v.number()) },
  returns: v.array(v.any()),
  handler: async (ctx, args) => {
    const rows = await ctx.db.query("readings")
      .withIndex("by_player", (q) => q.eq("playerId", args.playerId))
      .order("desc")
      .take(Math.min(args.limit ?? 6, 10));
    return rows.filter((row) => row.kind === "oracle" && row.question).reverse();
  },
});
