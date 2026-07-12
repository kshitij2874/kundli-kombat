/* eslint-disable */
/**
 * Generated `api` utility.
 *
 * THIS CODE IS AUTOMATICALLY GENERATED.
 *
 * To regenerate, run `npx convex dev`.
 * @module
 */

import type * as battles from "../battles.js";
import type * as celebrities from "../celebrities.js";
import type * as escalations from "../escalations.js";
import type * as health from "../health.js";
import type * as hermes from "../hermes.js";
import type * as places from "../places.js";
import type * as players from "../players.js";
import type * as readings from "../readings.js";

import type {
  ApiFromModules,
  FilterApi,
  FunctionReference,
} from "convex/server";

declare const fullApi: ApiFromModules<{
  battles: typeof battles;
  celebrities: typeof celebrities;
  escalations: typeof escalations;
  health: typeof health;
  hermes: typeof hermes;
  places: typeof places;
  players: typeof players;
  readings: typeof readings;
}>;

/**
 * A utility for referencing Convex functions in your app's public API.
 *
 * Usage:
 * ```js
 * const myFunctionReference = api.myModule.myFunction;
 * ```
 */
export declare const api: FilterApi<
  typeof fullApi,
  FunctionReference<any, "public">
>;

/**
 * A utility for referencing Convex functions in your app's internal API.
 *
 * Usage:
 * ```js
 * const myFunctionReference = internal.myModule.myFunction;
 * ```
 */
export declare const internal: FilterApi<
  typeof fullApi,
  FunctionReference<any, "internal">
>;

export declare const components: {};
