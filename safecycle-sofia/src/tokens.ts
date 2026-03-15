export const colors = {
  // Brand
  primary: "#00C97B",
  primaryDark: "#009B60",
  primaryLight: "#E6FFF5",

  // Semantic states
  safe: "#00C97B",
  caution: "#F5A623",
  danger: "#E8453C",
  dangerLight: "#FFF0EF",

  // Awareness
  awarenessZone: "#F5A623",
  awarenessZoneAlpha: "rgba(245, 166, 35, 0.18)",

  // Crossroad marker
  crossroadBorder: "#F5A623",
  crossroadFill: "#FFFFFF",

  // Map route
  routeStroke: "#00C97B",
  routeStrokeAlternate: "#F5A623",

  // Surface/speed defaults (used in UI chips)
  defaultDataChip: "#F0F0F0",
  defaultDataText: "#888888",

  // Neutrals
  background: "#0D0D0D",
  surface: "#1A1A1A",
  surfaceElevated: "#242424",
  border: "#2E2E2E",
  textPrimary: "#F5F5F5",
  textSecondary: "#9A9A9A",
  textDisabled: "#555555",

  // Hazard type colours
  hazardPothole: "#E8453C",
  hazardObstacle: "#F5A623",
  hazardTraffic: "#FF6B35",
  hazardClosed: "#9B59B6",
  hazardWet: "#3498DB",
  hazardOther: "#7F8C8D",
} as const

export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
} as const

export const radius = {
  sm: 6,
  md: 10,
  lg: 16,
  xl: 24,
  full: 9999,
} as const

export const typography = {
  fontFamily: {
    regular: "System",
    bold: "System",
    mono: "Courier",
  },
  size: {
    xs: 11,
    sm: 13,
    md: 15,
    lg: 17,
    xl: 22,
    xxl: 28,
    hero: 36,
  },
  weight: {
    regular: "400" as const,
    medium: "500" as const,
    semibold: "600" as const,
    bold: "700" as const,
    black: "900" as const,
  },
} as const
