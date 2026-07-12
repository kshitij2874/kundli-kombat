import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const getIdentity = query({
  args: { channel: v.literal("telegram"), userId: v.string() },
  returns: v.any(),
  handler: async (ctx, args) => {
    const identity = await ctx.db.query("telegramIdentities")
      .withIndex("by_channel_user", (q) => q.eq("channel", args.channel).eq("userId", args.userId))
      .unique();
    if (!identity) return null;
    const player = await ctx.db.get(identity.playerId);
    return player ? { identity, playerId: identity.playerId, player } : null;
  },
});

export const bindIdentity = mutation({
  args: {
    channel: v.literal("telegram"), userId: v.string(), chatId: v.string(),
    threadId: v.optional(v.string()), playerId: v.id("players"),
  },
  returns: v.id("telegramIdentities"),
  handler: async (ctx, args) => {
    const existing = await ctx.db.query("telegramIdentities")
      .withIndex("by_channel_user", (q) => q.eq("channel", args.channel).eq("userId", args.userId))
      .unique();
    const now = Date.now();
    if (existing) {
      await ctx.db.patch(existing._id, {
        chatId: args.chatId, threadId: args.threadId, playerId: args.playerId, updatedAt: now,
      });
      return existing._id;
    }
    return ctx.db.insert("telegramIdentities", { ...args, createdAt: now, updatedAt: now });
  },
});

export const getRequest = query({
  args: { requestId: v.string() },
  returns: v.any(),
  handler: (ctx, args) => ctx.db.query("hermesRequests")
    .withIndex("by_request_id", (q) => q.eq("requestId", args.requestId)).unique(),
});

export const storeRequest = mutation({
  args: { requestId: v.string(), fingerprint: v.string(), response: v.any() },
  returns: v.id("hermesRequests"),
  handler: async (ctx, args) => {
    const existing = await ctx.db.query("hermesRequests")
      .withIndex("by_request_id", (q) => q.eq("requestId", args.requestId)).unique();
    if (existing) return existing._id;
    return ctx.db.insert("hermesRequests", { ...args, createdAt: Date.now() });
  },
});
