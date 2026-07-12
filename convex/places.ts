import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const get = query({
  args: { key: v.string() },
  returns: v.union(v.null(), v.object({ results: v.array(v.any()), createdAt: v.number() })),
  handler: async (ctx, { key }) => {
    const record = await ctx.db.query("placeCache").withIndex("by_key", (q) => q.eq("key", key)).unique();
    return record ? { results: record.results, createdAt: record.createdAt } : null;
  },
});

export const put = mutation({
  args: { key: v.string(), query: v.string(), results: v.array(v.any()) },
  returns: v.id("placeCache"),
  handler: async (ctx, args) => {
    const record = await ctx.db.query("placeCache").withIndex("by_key", (q) => q.eq("key", args.key)).unique();
    if (record) {
      await ctx.db.patch(record._id, { query: args.query, results: args.results, createdAt: Date.now() });
      return record._id;
    }
    return ctx.db.insert("placeCache", { ...args, createdAt: Date.now() });
  },
});

