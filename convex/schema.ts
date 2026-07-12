import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

const tone = v.union(v.literal("comfort"), v.literal("straight"), v.literal("roast"));
const language = v.union(v.literal("en"), v.literal("hinglish"));
const evidence = v.array(v.object({ planet: v.string(), sign: v.string(), longitude: v.number() }));

export default defineSchema({
  players: defineTable({
    name: v.string(), dob: v.string(), tob: v.optional(v.string()), tobUnknown: v.boolean(),
    place: v.string(), lat: v.number(), lon: v.number(), tz: v.string(), chart: v.any(),
    big3: v.object({ sun: v.string(), moon: v.string(), rising: v.string() }),
    nakshatra: v.string(), tone, lang: language, streak: v.number(), lastPullAt: v.optional(v.number()),
    xp: v.number(), badges: v.array(v.string()), createdAt: v.number(),
    source: v.union(v.literal("web"), v.literal("telegram")),
  }).index("by_created_at", ["createdAt"]),
  readings: defineTable({
    playerId: v.id("players"), kind: v.union(v.literal("identity"), v.literal("daily"), v.literal("placement"), v.literal("oracle"), v.literal("deep")),
    question: v.optional(v.string()), tone, text: v.string(), voiceUrl: v.optional(v.string()), evidence,
    latencyMs: v.number(), costUsd: v.number(), langfuseTraceId: v.string(), createdAt: v.number(),
  }).index("by_player", ["playerId", "createdAt"]),
  battles: defineTable({
    code: v.string(), p1Id: v.id("players"), p2Id: v.optional(v.id("players")), celebrity: v.optional(v.string()),
    rounds: v.array(v.object({ name: v.string(), p1Score: v.number(), p2Score: v.number(), compatibilityScore: v.number(), line: v.string(), aspects: v.array(v.string()) })),
    verdictPct: v.number(), prediction: v.string(), cardId: v.optional(v.id("cards")), latencyMs: v.number(),
    costUsd: v.number(), langfuseTraceId: v.string(), createdAt: v.number(),
  }).index("by_code", ["code"]).index("by_created_at", ["createdAt"]),
  cards: defineTable({
    playerId: v.id("players"), type: v.union(v.literal("identity"), v.literal("pull"), v.literal("scorecard"), v.literal("badge")),
    title: v.string(), glyphs: v.array(v.string()), line: v.string(), rarity: v.union(v.literal("common"), v.literal("rare"), v.literal("mythic")), createdAt: v.number(),
  }).index("by_player", ["playerId", "createdAt"]),
  celebrities: defineTable({
    name: v.string(), dob: v.string(), tob: v.optional(v.string()), tobUnknown: v.boolean(), place: v.string(),
    sourceUrl: v.string(), chart: v.any(), big3: v.object({ sun: v.string(), moon: v.string(), rising: v.string() }),
  }).index("by_name", ["name"]),
  escalations: defineTable({
    playerId: v.optional(v.id("players")), question: v.string(), policy: v.union(
      v.literal("doom"), v.literal("medical"), v.literal("pregnancy"), v.literal("legal"),
      v.literal("financial"), v.literal("abuse"), v.literal("prompt_injection"), v.literal("under13")
    ), context: v.any(), createdAt: v.number(),
  }).index("by_created_at", ["createdAt"]),
  policies: defineTable({ key: v.string(), value: v.any() }).index("by_key", ["key"]),
  specialists: defineTable({ name: v.string(), jobPrompt: v.string(), tools: v.array(v.string()), guardrails: v.array(v.string()), active: v.boolean(), createdAt: v.number() }).index("by_name", ["name"]),
  events: defineTable({ playerId: v.optional(v.id("players")), kind: v.string(), meta: v.any(), createdAt: v.number() }).index("by_player", ["playerId", "createdAt"]).index("by_kind", ["kind", "createdAt"]),
  placeCache: defineTable({ key: v.string(), query: v.string(), results: v.array(v.any()), createdAt: v.number() }).index("by_key", ["key"]),
  telegramIdentities: defineTable({
    channel: v.literal("telegram"), userId: v.string(), chatId: v.string(),
    threadId: v.optional(v.string()), playerId: v.id("players"),
    createdAt: v.number(), updatedAt: v.number(),
  }).index("by_channel_user", ["channel", "userId"]),
  hermesRequests: defineTable({
    requestId: v.string(), fingerprint: v.string(), response: v.any(), createdAt: v.number(),
  }).index("by_request_id", ["requestId"]),
});
