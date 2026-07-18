/**
 * Integration configuration.
 * All environment variables are accessed through this module only.
 *
 * EXPO_PUBLIC_* references must use the literal `process.env.EXPO_PUBLIC_X`
 * form directly below -- Expo's Babel plugin statically replaces that exact
 * syntax at build time. Reading through an aliased variable (e.g.
 * `const env = process.env; env.EXPO_PUBLIC_X`) is NOT recognised, so it
 * silently falls through to the fallback in every production/EAS build
 * (process.env isn't populated at runtime on-device) while still appearing
 * to work under `expo start`, where a real env-loaded process is involved.
 */

export const integrationConfig = {
  apiBaseUrl: process.env.EXPO_PUBLIC_API_BASE_URL ?? "http://localhost:8000",
  wsBaseUrl: process.env.EXPO_PUBLIC_WS_BASE_URL ?? "ws://localhost:8000",
  googleMapsKey: process.env.EXPO_PUBLIC_GOOGLE_MAPS_API_KEY ?? "",
  // Shared secret for the SafeCycle backend. Sent as the `X-API-Key` header on
  // every REST call and as `?token=` on the GPS WebSocket. Empty = no header
  // (works against a local backend that has auth disabled).
  apiKey: process.env.EXPO_PUBLIC_API_KEY ?? "",
  environment: (process.env.EXPO_PUBLIC_ENVIRONMENT ?? "development") as
    "development" | "staging" | "production",

  get isDevelopment() { return this.environment === "development" },
  get isProduction() { return this.environment === "production" },

  // Timeouts (ms)
  httpTimeoutMs: 12_000,
  wsReconnectBaseMs: 1_000,
  wsReconnectMaxMs: 30_000,
  wsHeartbeatMs: 25_000,

  // Retry policy
  maxRetryAttempts: 3,
  retryBackoffBase: 1_000,

  // Polling intervals
  hazardRefreshMs: 30_000,
  gpsPublishMs: 10_000,

  // Spatial (must match backend)
  sofiaBbox: {
    north: 42.73, south: 42.62,
    east: 23.42, west: 23.23,
  },
  crossroadAlertRadiusM: 15,
  awarenessZoneRadiusM: 30,
  hazardAlertRadiusM: 20,
} as const

export type IntegrationConfig = typeof integrationConfig
