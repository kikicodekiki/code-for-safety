/**
 * Integration configuration.
 * All environment variables are accessed through this module only.
 */

const env = process.env

export const integrationConfig = {
  apiBaseUrl:   env.EXPO_PUBLIC_API_BASE_URL    ?? "http://localhost:8000",
  wsBaseUrl:    env.EXPO_PUBLIC_WS_BASE_URL     ?? "ws://localhost:8000",
  googleMapsKey: env.EXPO_PUBLIC_GOOGLE_MAPS_API_KEY ?? "",
  environment:  (env.EXPO_PUBLIC_ENVIRONMENT   ?? "development") as
                  "development" | "staging" | "production",

  get isDevelopment() { return this.environment === "development" },
  get isProduction()  { return this.environment === "production"  },

  // Timeouts (ms)
  httpTimeoutMs:       12_000,
  wsReconnectBaseMs:    1_000,
  wsReconnectMaxMs:    30_000,
  wsHeartbeatMs:       25_000,

  // Retry policy
  maxRetryAttempts:    3,
  retryBackoffBase:    1_000,

  // Polling intervals
  hazardRefreshMs:    30_000,
  gpsPublishMs:       10_000,

  // Spatial (must match backend)
  sofiaBbox: {
    north: 42.73, south: 42.62,
    east:  23.42, west:  23.23,
  },
  crossroadAlertRadiusM:  15,
  awarenessZoneRadiusM:   30,
  hazardAlertRadiusM:     20,
} as const

export type IntegrationConfig = typeof integrationConfig
