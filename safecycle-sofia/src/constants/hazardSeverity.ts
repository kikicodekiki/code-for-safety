import type { HazardType, SeverityLevel } from "../types"

export interface SeverityDescriptor {
  label: string
  shortLabel: string
  colour: string
  routingNote: string
  examplesByType: Record<HazardType, string>
}

export const SEVERITY_DESCRIPTORS: Record<SeverityLevel, SeverityDescriptor> = {
  1: {
    label: "Negligible",
    shortLabel: "1 – Negligible",
    colour: "#4CAF50",
    routingNote: "No routing impact",
    examplesByType: {
      pothole: "Barely visible crack, no risk",
      obstacle: "Tiny piece of debris, well off the path",
      dangerous_traffic: "Slightly inattentive driver",
      road_closed: "Advisory sign only, path clear",
      wet_surface: "Barely damp surface",
      other: "Trivial nuisance",
    },
  },
  2: {
    label: "Minor",
    shortLabel: "2 – Minor",
    colour: "#66BB6A",
    routingNote: "Very small penalty added",
    examplesByType: {
      pothole: "Shallow dip, easily avoidable",
      obstacle: "Small debris on the side of the path",
      dangerous_traffic: "Slightly impatient driver",
      road_closed: "One lane reduced, still comfortable",
      wet_surface: "Slightly damp, no visible water",
      other: "Minor inconvenience",
    },
  },
  3: {
    label: "Low",
    shortLabel: "3 – Low",
    colour: "#8BC34A",
    routingNote: "Small penalty — route mostly unaffected",
    examplesByType: {
      pothole: "Small pothole, slow to pass",
      obstacle: "Object on the edge of the path",
      dangerous_traffic: "Driver ignoring the bike lane",
      road_closed: "Lane reduction causing mild delay",
      wet_surface: "Wet surface, slightly reduced grip",
      other: "Worth noting to nearby cyclists",
    },
  },
  4: {
    label: "Moderate",
    shortLabel: "4 – Moderate",
    colour: "#CDDC39",
    routingNote: "Moderate penalty — route may slightly prefer alternatives",
    examplesByType: {
      pothole: "Noticeable pothole, need to slow down",
      obstacle: "Object partially blocking the path",
      dangerous_traffic: "Aggressive overtaking, unsafe speed",
      road_closed: "Significant lane reduction",
      wet_surface: "Wet surface, clearly reduced grip",
      other: "Worth avoiding if a nearby alternative exists",
    },
  },
  5: {
    label: "Noticeable",
    shortLabel: "5 – Noticeable",
    colour: "#FFC107",
    routingNote: "Noticeable penalty — alternatives mildly preferred",
    examplesByType: {
      pothole: "Large pothole requiring a detour around it",
      obstacle: "Obstacle blocking half the lane",
      dangerous_traffic: "Sustained risky driving behaviour",
      road_closed: "Road effectively half-closed",
      wet_surface: "Standing water patches, slippery",
      other: "Poses some risk to most cyclists",
    },
  },
  6: {
    label: "Serious",
    shortLabel: "6 – Serious",
    colour: "#FF9800",
    routingNote: "Significant penalty — routing prefers alternatives",
    examplesByType: {
      pothole: "Large pothole, risk of fall if hit directly",
      obstacle: "Obstacle covering most of the path",
      dangerous_traffic: "Repeated dangerous close passes",
      road_closed: "Road effectively closed for cyclists",
      wet_surface: "Continuous standing water, very slippery",
      other: "Poses real risk to most cyclists",
    },
  },
  7: {
    label: "Severe",
    shortLabel: "7 – Severe",
    colour: "#FF5722",
    routingNote: "High penalty — routing strongly avoids this segment",
    examplesByType: {
      pothole: "Very deep pothole, wheel/rim damage risk",
      obstacle: "Large obstacle, path nearly blocked",
      dangerous_traffic: "Road rage or collision near-miss",
      road_closed: "Full closure, confirmed by signage",
      wet_surface: "Flooding beginning, do not attempt at speed",
      other: "Serious danger to most cyclists",
    },
  },
  8: {
    label: "Dangerous",
    shortLabel: "8 – Dangerous",
    colour: "#F44336",
    routingNote: "Very high penalty — strong avoidance in routing",
    examplesByType: {
      pothole: "Crater-level pothole, almost impassable",
      obstacle: "Large object blocking the full path",
      dangerous_traffic: "Active collision risk, vehicles in bike lane",
      road_closed: "Emergency closure, police on scene",
      wet_surface: "Flash flooding, standing water > 10 cm",
      other: "Dangerous to any cyclist",
    },
  },
  9: {
    label: "Critical",
    shortLabel: "9 – Critical",
    colour: "#E8453C",
    routingNote: "Edge excluded from routing — treat as impassable",
    examplesByType: {
      pothole: "Road surface collapsed, impassable",
      obstacle: "Vehicle or fallen tree blocking path entirely",
      dangerous_traffic: "Active accident or violence on the road",
      road_closed: "Emergency closure — firefighters/ambulance on scene",
      wet_surface: "Flash flood conditions, water flowing",
      other: "Immediate danger to any cyclist",
    },
  },
  10: {
    label: "Emergency",
    shortLabel: "10 – Emergency",
    colour: "#B71C1C",
    routingNote: "Edge permanently excluded — life-threatening conditions",
    examplesByType: {
      pothole: "Road fully collapsed, structural failure",
      obstacle: "Multiple vehicles or building material blocking route",
      dangerous_traffic: "Active emergency, do not enter",
      road_closed: "Full area closed — mass casualty or disaster",
      wet_surface: "Severe flooding, risk to life",
      other: "Life-threatening — do not pass under any circumstances",
    },
  },
}

export const SEVERITY_LABELS: Record<SeverityLevel, string> = Object.fromEntries(
  (Object.entries(SEVERITY_DESCRIPTORS) as [string, SeverityDescriptor][]).map(
    ([k, v]) => [Number(k), v.label]
  )
) as Record<SeverityLevel, string>

export const SEVERITY_COLOURS: Record<SeverityLevel, string> = Object.fromEntries(
  (Object.entries(SEVERITY_DESCRIPTORS) as [string, SeverityDescriptor][]).map(
    ([k, v]) => [Number(k), v.colour]
  )
) as Record<SeverityLevel, string>

/** Returns "Low" | "Medium" | "High" | "Verified" for confidence 0–1 */
export function confidenceLabel(confidence: number): string {
  if (confidence < 0.25) return "Low"
  if (confidence < 0.5) return "Medium"
  if (confidence < 1.0) return "High"
  return "Verified"
}

/** Returns the SeverityLevel (1–10) closest to a raw consensus float */
export function clampSeverity(value: number): SeverityLevel {
  const clamped = Math.max(1, Math.min(10, Math.round(value)))
  return clamped as SeverityLevel
}
