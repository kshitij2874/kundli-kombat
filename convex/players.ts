import { mutation } from "./_generated/server";
import { v } from "convex/values";

const tone = v.union(v.literal("comfort"), v.literal("straight"), v.literal("roast"));
const language = v.union(v.literal("en"), v.literal("hinglish"));

export const create = mutation({
  args: {
    name: v.string(), dob: v.string(), tob: v.optional(v.string()), tobUnknown: v.boolean(),
    place: v.string(), lat: v.number(), lon: v.number(), tz: v.string(), chart: v.any(),
    big3: v.object({ sun: v.string(), moon: v.string(), rising: v.string() }),
    nakshatra: v.string(), tone, lang: language,
    source: v.union(v.literal("web"), v.literal("telegram")),
  },
  returns: v.id("players"),
  handler: async (ctx, args) => ctx.db.insert("players", {
    ...args,
    tob: args.tob,
    streak: 0,
    xp: 0,
    badges: [],
    createdAt: Date.now(),
  }),
});

