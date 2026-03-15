// ─── Primitives ───────────────────────────────────────────────────────────────

export interface Coordinate {
  lat: number
  lon: number
}

export interface GeoJSONLineString {
  type: "LineString"
  coordinates: [number, number][]  // [lon, lat] GeoJSON order
}

// ─── Route ────────────────────────────────────────────────────────────────────

export interface RouteRequest {
  origin_lat: number
  origin_lon: number
  dest_lat:   number
  dest_lon:   number
}

export interface AwarenessZone {
  center:   Coordinate
  radius_m: number
  type:     "kindergarten" | "playground" | "bus_stop" | "accident_hotspot"
  name?:    string
}

export interface RouteResponse {
  path:                  GeoJSONLineString
  crossroad_nodes:       Coordinate[]
  distance_m:            number
  duration_min:          number
  safety_score:          number           // 0.0–1.0
  surface_defaulted?:    boolean
  speed_limit_defaulted?: boolean
  awareness_zones:       AwarenessZone[]
}

// ─── Hazards ──────────────────────────────────────────────────────────────────

export type HazardType =
  | "pothole"
  | "obstacle"
  | "dangerous_traffic"
  | "road_closed"
  | "wet_surface"
  | "other"

// 1–10 severity scale
export type SeverityLevel = 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10

export interface HazardReportCreate {
  lat:          number
  lon:          number
  type:         HazardType
  severity:     SeverityLevel
  description?: string
}

export interface RoutingImpact {
  affects_routing: boolean
  edge_excluded:   boolean
  penalty_added:   number | null
  description:     string
}

export interface HazardReportResponse {
  id:             string
  status:         "reported" | "merged_into_cluster"
  cluster_id:     string | null
  severity:       SeverityLevel
  type:           HazardType
  timestamp:      string
  expires_at:     string
  routing_impact: RoutingImpact
  message:        string
}

export interface AggregatedHazardResponse {
  id:                 string
  lat:                number
  lon:                number
  hazard_type:        HazardType
  type_display_name:  string
  type_icon:          string
  report_count:       number
  consensus_severity: number
  effective_severity: SeverityLevel
  severity_label:     string
  confidence:         number
  confidence_label:   string
  age_hours:          number
  is_recent:          boolean
  is_fresh:           boolean
  description?:       string
  routing_excluded:   boolean
  decay_factor:       number
  effective_penalty:  number | null
}

export interface HazardConfirmationCreate {
  lat:    number
  lon:    number
  action: "confirm" | "dismiss"
}

export interface HazardStatsResponse {
  total_active_clusters:    number
  total_reports_today:      number
  by_type:                  Record<string, number>
  by_severity:              Record<number, number>
  most_reported_area:       string | null
  edges_currently_excluded: number
  avg_confidence:           number
  coverage_radius_km:       number
}

// ─── Device ───────────────────────────────────────────────────────────────────

export interface DeviceTokenCreate {
  token:    string
  platform: "ios" | "android"
}

// ─── WebSocket ────────────────────────────────────────────────────────────────

export interface GPSUpdate {
  lat:        number
  lon:        number
  heading:    number
  speed_kmh:  number
  accuracy_m?: number
}

export type WSServerEvent =
  | { event: "crossroad";     payload: { distance_m: number; node: Coordinate } }
  | { event: "awareness_zone"; payload: { zone: AwarenessZone; distance_m: number } }
  | { event: "hazard_nearby"; payload: { hazard: AggregatedHazardResponse; distance_m: number } }

// ─── Health ───────────────────────────────────────────────────────────────────

export interface HealthResponse {
  status:  "ok"
  version: string
}

export interface ReadinessResponse {
  status: "ready" | "not_ready"
  checks: {
    graph_loaded:     boolean
    graph_node_count: number
    redis:            boolean
    database:         boolean
  }
}

// ─── Route error ─────────────────────────────────────────────────────────────

export interface RouteError {
  type:      "offline" | "not_found" | "outside_bbox" | "graph_loading" | "server_error" | "unknown"
  message:   string
  retryable: boolean
}

// ─── VeloBG (Bike Paths) ──────────────────────────────────────────────────────

export type VeloBGPathType =
  | "dedicated_lane"
  | "painted_lane"
  | "shared_path"
  | "greenway"
  | "off_road"
  | "proposed"
  | "unknown"

export interface VeloBGPath {
  id: string
  name: string | null
  description: string | null
  path_type: VeloBGPathType
  layer_name: string | null
  colour_hex: string | null
  length_m: number
  is_bidirectional: boolean
  geojson: GeoJSONLineString | { type: "MultiLineString"; coordinates: [number, number][][] }
  fetched_at: string
}

export interface VeloBGPathsResponse {
  paths: VeloBGPath[]
  total: number
  source: string
  fetched_at: string
}
