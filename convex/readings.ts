import { mutation } from "./_generated/server";
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

