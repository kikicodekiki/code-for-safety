import { create } from "zustand"
import { apiClient } from "../api/client"
import type {
  AggregatedHazardResponse,
  HazardType,
  SeverityLevel,
} from "../types"

interface ReportDraft {
  type: HazardType | null
  severity: SeverityLevel
  description: string
  location: { lat: number; lon: number } | null
  stage: 1 | 2 | 3
}

interface HazardState {
  // Data
  hazards: AggregatedHazardResponse[]
  isFetching: boolean

  // Form state
  reportDraft: ReportDraft

  // UI state
  isSheetVisible: boolean
  isSubmitting: boolean
  submitError: string | null
  lastSubmittedId: string | null

  // Computed selectors
  getActiveHazards: () => AggregatedHazardResponse[]
  getFreshHazards: () => AggregatedHazardResponse[]
  getRecentHazards: () => AggregatedHazardResponse[]
  getHazardsNear: (lat: number, lon: number, radiusM: number) => AggregatedHazardResponse[]
  getEdgesExcluded: () => AggregatedHazardResponse[]
  getByType: (type: HazardType) => AggregatedHazardResponse[]
  getByMinSeverity: (min: SeverityLevel) => AggregatedHazardResponse[]

  // Draft actions
  setDraftType: (type: HazardType) => void
  setDraftSeverity: (severity: SeverityLevel) => void
  setDraftDescription: (text: string) => void
  setDraftLocation: (loc: { lat: number; lon: number }) => void
  advanceDraftStage: () => void
  resetDraft: () => void

  // Sheet actions
  openSheet: (initialLocation?: { lat: number; lon: number }) => void
  closeSheet: () => void

  // Async actions
  fetchHazards: (lat?: number, lon?: number, radius?: number) => Promise<void>
  submitReport: (data: {
    type: HazardType
    severity: SeverityLevel
    description?: string
    lat: number
    lon: number
  }) => Promise<void>
  confirmHazard: (id: string, action: "confirm" | "dismiss") => Promise<void>
  clearSubmitError: () => void
}

const DEFAULT_DRAFT: ReportDraft = {
  type: null,
  severity: 3,
  description: "",
  location: null,
  stage: 1,
}

function haversineDistanceM(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number
): number {
  const R = 6_371_000
  const dLat = ((lat2 - lat1) * Math.PI) / 180
  const dLon = ((lon2 - lon1) * Math.PI) / 180
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLon / 2) ** 2
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

export const useHazardStore = create<HazardState>((set, get) => ({
  hazards: [],
  isFetching: false,
  reportDraft: { ...DEFAULT_DRAFT },
  isSheetVisible: false,
  isSubmitting: false,
  submitError: null,
  lastSubmittedId: null,

  // --- Computed selectors ---

  getActiveHazards: () =>
    get().hazards.filter((h) => h.decay_factor > 0),

  getFreshHazards: () =>
    get().hazards.filter((h) => h.is_fresh),

  getRecentHazards: () =>
    get().hazards.filter((h) => h.is_recent),

  getHazardsNear: (lat, lon, radiusM) =>
    get().hazards.filter(
      (h) => haversineDistanceM(lat, lon, h.lat, h.lon) <= radiusM
    ),

  getEdgesExcluded: () =>
    get().hazards.filter((h) => h.routing_excluded),

  getByType: (type) =>
    get().hazards.filter((h) => h.hazard_type === type),

  getByMinSeverity: (min) =>
    get().hazards.filter((h) => h.effective_severity >= min),

  // --- Draft actions ---

  setDraftType: (type) =>
    set((s) => ({ reportDraft: { ...s.reportDraft, type, stage: 1 } })),

  setDraftSeverity: (severity) =>
    set((s) => ({ reportDraft: { ...s.reportDraft, severity } })),

  setDraftDescription: (text) =>
    set((s) => ({ reportDraft: { ...s.reportDraft, description: text } })),

  setDraftLocation: (loc) =>
    set((s) => ({ reportDraft: { ...s.reportDraft, location: loc } })),

  advanceDraftStage: () =>
    set((s) => ({
      reportDraft: {
        ...s.reportDraft,
        stage: Math.min(s.reportDraft.stage + 1, 3) as 1 | 2 | 3,
      },
    })),

  resetDraft: () => set({ reportDraft: { ...DEFAULT_DRAFT } }),

  // --- Sheet actions ---

  openSheet: (initialLocation) =>
    set({
      isSheetVisible: true,
      reportDraft: {
        ...DEFAULT_DRAFT,
        location: initialLocation ?? null,
      },
    }),

  closeSheet: () => set({ isSheetVisible: false }),

  // --- Async actions ---

  fetchHazards: async (lat, lon, radius = 1000) => {
    set({ isFetching: true })
    try {
      const hazards = await apiClient.getHazards({ lat, lon, radius_m: radius, active_only: true })
      set({ hazards })
    } finally {
      set({ isFetching: false })
    }
  },

  submitReport: async ({ type, severity, description, lat, lon }) => {
    set({ isSubmitting: true, submitError: null })
    try {
      const response = await apiClient.reportHazard({ lat, lon, type, severity, description })

      // Optimistically add a local placeholder until next fetch
      const optimistic: AggregatedHazardResponse = {
        id: response.id,
        lat,
        lon,
        hazard_type: type,
        type_display_name: type,
        type_icon: "",
        report_count: 1,
        consensus_severity: severity,
        effective_severity: severity,
        severity_label: `${severity}/10`,
        confidence: 0.2,
        confidence_label: "Low",
        age_hours: 0,
        is_recent: true,
        is_fresh: true,
        routing_excluded: response.routing_impact?.edge_excluded ?? false,
        decay_factor: 1.0,
        effective_penalty: response.routing_impact?.penalty_added,
        description,
      }

      set((s) => ({
        hazards: [optimistic, ...s.hazards],
        lastSubmittedId: response.id,
      }))
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to submit report"
      set({ submitError: message })
      throw err
    } finally {
      set({ isSubmitting: false })
    }
  },

  confirmHazard: async (id, action) => {
    const current = useNavigationPosition()
    await apiClient.confirmHazard(id, {
      lat: current?.lat ?? 0,
      lon: current?.lon ?? 0,
      action,
    })
    // Remove or refresh the hazard if dismissed
    if (action === "dismiss") {
      set((s) => ({
        hazards: s.hazards.filter((h) => h.id !== id),
      }))
    }
  },

  clearSubmitError: () => set({ submitError: null }),
}))

// Lazy import to avoid circular dependency
function useNavigationPosition(): { lat: number; lon: number } | null {
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { useNavigationStore } = require("./useNavigationStore")
    return useNavigationStore.getState().currentPosition
  } catch {
    return null
  }
}
