import type { HazardType, SeverityLevel } from "../types"

export interface HazardTypeDescriptor {
  key: HazardType
  displayName: string
  icon: string
  iconName: string
  colour: string
  descriptionRequired: boolean
  descriptionPlaceholder: string
  defaultSeverity: SeverityLevel
  severityPrompt: string
}

export const HAZARD_TYPE_DESCRIPTORS: Record<HazardType, HazardTypeDescriptor> = {
  pothole: {
    key: "pothole",
    displayName: "Pothole",
    icon: "🕳",
    iconName: "circle-outline",
    colour: "#E8453C",
    descriptionRequired: false,
    descriptionPlaceholder: "e.g. 'Large pothole near the tram tracks, right side of lane'",
    defaultSeverity: 3,
    severityPrompt: "How deep and dangerous is the pothole?",
  },
  obstacle: {
    key: "obstacle",
    displayName: "Obstacle",
    icon: "🚧",
    iconName: "barricade",
    colour: "#F5A623",
    descriptionRequired: false,
    descriptionPlaceholder: "e.g. 'Fallen branch blocking the bike lane'",
    defaultSeverity: 3,
    severityPrompt: "How much of the path is blocked?",
  },
  dangerous_traffic: {
    key: "dangerous_traffic",
    displayName: "Dangerous traffic",
    icon: "🚗",
    iconName: "car-emergency",
    colour: "#FF6B35",
    descriptionRequired: false,
    descriptionPlaceholder: "e.g. 'Cars ignoring the bike lane, speeding'",
    defaultSeverity: 5,
    severityPrompt: "How dangerous is the traffic situation?",
  },
  road_closed: {
    key: "road_closed",
    displayName: "Road closed",
    icon: "🚫",
    iconName: "road-variant",
    colour: "#9B59B6",
    descriptionRequired: false,
    descriptionPlaceholder: "e.g. 'Construction — path completely blocked until end of street'",
    defaultSeverity: 6,
    severityPrompt: "How much of the road is affected?",
  },
  wet_surface: {
    key: "wet_surface",
    displayName: "Wet surface",
    icon: "💧",
    iconName: "water",
    colour: "#3498DB",
    descriptionRequired: false,
    descriptionPlaceholder: "e.g. 'Water pooling after rain, very slippery cobblestones'",
    defaultSeverity: 3,
    severityPrompt: "How slippery or flooded is the surface?",
  },
  other: {
    key: "other",
    displayName: "Other",
    icon: "❓",
    iconName: "help-circle-outline",
    colour: "#7F8C8D",
    descriptionRequired: true,
    descriptionPlaceholder: "Please describe the hazard (required)",
    defaultSeverity: 3,
    severityPrompt: "How serious is this hazard?",
  },
}

export const HAZARD_TYPES = Object.values(HAZARD_TYPE_DESCRIPTORS)

export const HAZARD_DISPLAY_NAMES: Record<HazardType, string> = Object.fromEntries(
  HAZARD_TYPES.map((d) => [d.key, d.displayName])
) as Record<HazardType, string>

export const HAZARD_ICONS: Record<HazardType, string> = Object.fromEntries(
  HAZARD_TYPES.map((d) => [d.key, d.icon])
) as Record<HazardType, string>

export const HAZARD_COLOURS: Record<HazardType, string> = Object.fromEntries(
  HAZARD_TYPES.map((d) => [d.key, d.colour])
) as Record<HazardType, string>
