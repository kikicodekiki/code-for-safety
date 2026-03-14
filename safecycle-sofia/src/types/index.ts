export type Coordinate = { lat: number; lon: number }

export type HazardType =
  | "obstacle"
  | "pothole"
  | "dangerous_traffic"
  | "road_closed"
  | "wet_surface"
  | "other"

export type SeverityLevel = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10

export type Hazard = {
  id: string
  lat: number
  lon: number
  type: HazardType
  severity: SeverityLevel
  description?: string
  timestamp: string // ISO 8601
  age_hours: number
}

export type HazardReport = Omit<Hazard, "id" | "age_hours">

// Aggregated cluster of multiple hazard reports near each other
export type AggregatedHazardResponse = {
  id: string
  lat: number
  lon: number
  hazard_type: HazardType
  type_display_name: string
  type_icon: string
  report_count: number
  consensus_severity: number
  effective_severity: SeverityLevel
  severity_label: string
  confidence: number
  confidence_label: string
  age_hours: number
  is_recent: boolean
  is_fresh: boolean
  description?: string
  routing_excluded: boolean
  decay_factor: number
  effective_penalty?: number
}

export type HazardReportCreate = {
  lat: number
  lon: number
  type: HazardType
  severity: SeverityLevel
  description?: string
}

export type HazardReportResponse = {
  id: string
  status: "reported" | "merged_into_cluster"
  cluster_id?: string
  severity: SeverityLevel
  type: HazardType
  timestamp: string
  expires_at: string
  routing_impact: {
    affects_routing: boolean
    edge_excluded: boolean
    penalty_added?: number
    description: string
  }
  message: string
}

export type HazardConfirmationCreate = {
  lat: number
  lon: number
  action: "confirm" | "dismiss"
}

export type RouteResponse = {
  path: GeoJSONLineString
  crossroad_nodes: Coordinate[]
  duration_min: number
  distance_m: number
  safety_score: number // 0.0–1.0
  surface_defaulted?: boolean // true if any edge used asphalt default
  speed_limit_defaulted?: boolean // true if any edge used 50 km/h default
  awareness_zones: AwarenessZone[]
}

export type AwarenessZone = {
  center: Coordinate
  radius_m: number
  type: "kindergarten" | "playground" | "bus_stop" | "accident_hotspot"
  name?: string
}

export type GeoJSONLineString = {
  type: "LineString"
  coordinates: [number, number][] // [lon, lat] pairs (GeoJSON standard)
}

export type ZoneStatus = "safe" | "caution" | "danger"

export type WSServerEvent =
  | { event: "crossroad"; payload: { distance_m: number; node: Coordinate } }
  | { event: "awareness_zone"; payload: { zone: AwarenessZone; distance_m: number } }
  | { event: "hazard_nearby"; payload: { hazard: AggregatedHazardResponse; distance_m: number } }

export type ConnectionStatus = "connected" | "connecting" | "disconnected" | "error"
