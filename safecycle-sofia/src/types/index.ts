export type Coordinate = { lat: number; lon: number }

export type HazardType =
  | "obstacle"
  | "pothole"
  | "dangerous_traffic"
  | "road_closed"
  | "wet_surface"
  | "other"

export type Hazard = {
  id: string
  lat: number
  lon: number
  type: HazardType
  description?: string
  timestamp: string // ISO 8601
  age_hours: number
}

export type HazardReport = Omit<Hazard, "id" | "age_hours">

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
  | { event: "hazard_nearby"; payload: { hazard: Hazard; distance_m: number } }

export type ConnectionStatus = "connected" | "connecting" | "disconnected" | "error"
