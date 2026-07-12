import { mutation } from "./_generated/server";
import { v } from "convex/values";

export const create = mutation({
  args: {
    playerId: v.optional(v.id("players")), question: v.string(),
    policy: v.union(
      v.literal("doom"), v.literal("medical"), v.literal("pregnancy"), v.literal("legal"),
      v.literal("financial"), v.literal("abuse"), v.literal("prompt_injection"), v.literal("under13")
    ),
    context: v.any(),
  },
  returns: v.id("escalations"),
  handler: (ctx, args) => ctx.db.insert("escalations", { ...args, createdAt: Date.now() }),
});
