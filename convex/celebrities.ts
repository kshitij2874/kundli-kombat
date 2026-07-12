import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const list = query({
  args: {},
  returns: v.array(v.any()),
  handler: async (ctx) => ctx.db.query("celebrities").collect(),
});

export const upsert = mutation({
  args: {
    name: v.string(), dob: v.string(), tob: v.optional(v.string()), tobUnknown: v.boolean(),
    place: v.string(), sourceUrl: v.string(), chart: v.any(),
    big3: v.object({ sun: v.string(), moon: v.string(), rising: v.string() }),
  },
  returns: v.id("celebrities"),
  handler: async (ctx, args) => {
    const current = await ctx.db.query("celebrities").withIndex("by_name", (q) => q.eq("name", args.name)).unique();
    if (current) {
      await ctx.db.patch(current._id, args);
      return current._id;
    }
    return ctx.db.insert("celebrities", args);
  },
});

