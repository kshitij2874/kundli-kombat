import { z } from "zod";

export const toneSchema = z.enum(["comfort", "straight", "roast"]);
export const languageSchema = z.enum(["en", "hinglish"]);
export const sourceSchema = z.enum(["web", "telegram"]);
export const evidenceSchema = z.object({ planet: z.string(), sign: z.string(), longitude: z.number() });

