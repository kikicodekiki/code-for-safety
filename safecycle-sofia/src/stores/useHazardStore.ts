import { create } from "zustand"
import type { AggregatedHazardResponse, HazardType, SeverityLevel } from "../types"

interface HazardState {
  // Data
  hazards:       AggregatedHazardResponse[]
  isFetching:    boolean
  isSubmitting:  boolean
  submitError:   string | null
  lastSubmittedId: string | null

  // Computed selectors
  getActiveHazards:   () => AggregatedHazardResponse[]
  getFreshHazards:    () => AggregatedHazardResponse[]
  getRecentHazards:   () => AggregatedHazardResponse[]
  getHazardsNear:     (lat: number, lon: number, radiusM: number) => AggregatedHazardResponse[]
  getEdgesExcluded:   () => AggregatedHazardResponse[]
  getByType:          (type: HazardType) => AggregatedHazardResponse[]
  getByMinSeverity:   (min: SeverityLevel) => AggregatedHazardResponse[]

  // Data actions
  setHazards:               (hazards: AggregatedHazardResponse[]) => void
  addProvisionalHazard:     (hazard: AggregatedHazardResponse) => void
  resolveProvisionalHazard: (provisionalId: string, realId: string) => void
  removeProvisionalHazard:  (provisionalId: string) => void
  setSubmitting:            (submitting: boolean) => void
  setSubmitError:           (error: string | null) => void
  addMyReport:              (report: unknown) => void
  optimisticallyConfirm:    (id: string, action: "confirm" | "dismiss") => void
  rollbackConfirmation:     (id: string, action: "confirm" | "dismiss") => void
  clearSubmitError:         () => void

  // Legacy compat — kept so existing callers don't break
  fetchHazards: (lat?: number, lon?: number, radius?: number) => Promise<void>
  submitReport: (data: {
    type: HazardType
    severity: SeverityLevel
    description?: string
    lat: number
    lon: number
  }) => Promise<void>
  confirmHazard: (id: string, action: "confirm" | "dismiss") => Promise<void>
}

function haversineM(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6_371_000
  const dLat = ((lat2 - lat1) * Math.PI) / 180
  const dLon = ((lon2 - lon1) * Math.PI) / 180
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLon / 2) ** 2
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
}

export const useHazardStore = create<HazardState>((set, get) => ({
  hazards:         [],
  isFetching:      false,
  isSubmitting:    false,
  submitError:     null,
  lastSubmittedId: null,

  // ─── Selectors ───────────────────────────────────────────────────────────────
  getActiveHazards:  () => get().hazards.filter((h) => h.decay_factor > 0),
  getFreshHazards:   () => get().hazards.filter((h) => h.is_fresh),
  getRecentHazards:  () => get().hazards.filter((h) => h.is_recent),
  getEdgesExcluded:  () => get().hazards.filter((h) => h.routing_excluded),
  getByType:         (type) => get().hazards.filter((h) => h.hazard_type === type),
  getByMinSeverity:  (min)  => get().hazards.filter((h) => h.effective_severity >= min),
  getHazardsNear:    (lat, lon, radiusM) =>
    get().hazards.filter((h) => haversineM(lat, lon, h.lat, h.lon) <= radiusM),

  // ─── Data actions ────────────────────────────────────────────────────────────
  setHazards: (hazards) => set({ hazards }),

  addProvisionalHazard: (hazard) =>
    set((s) => ({ hazards: [hazard, ...s.hazards] })),

  resolveProvisionalHazard: (provisionalId, realId) =>
    set((s) => ({
      hazards: s.hazards.map((h) =>
        h.id === provisionalId ? { ...h, id: realId, type_icon: h.type_icon === "⏳" ? "" : h.type_icon } : h
      ),
      lastSubmittedId: realId,
    })),

  removeProvisionalHazard: (provisionalId) =>
    set((s) => ({ hazards: s.hazards.filter((h) => h.id !== provisionalId) })),

  setSubmitting:  (isSubmitting) => set({ isSubmitting }),
  setSubmitError: (submitError)  => set({ submitError }),
  clearSubmitError: ()           => set({ submitError: null }),
  addMyReport:    (_report)      => { /* persisted via resolveProvisionalHazard */ },

  optimisticallyConfirm: (id, action) =>
    set((s) => ({
      hazards: s.hazards.map((h) => {
        if (h.id !== id) return h
        const newCount  = (h.report_count ?? 1) + 1
        const newConf   = Math.min(1.0, newCount / 5)
        return action === "confirm"
          ? { ...h, report_count: newCount, confidence: newConf }
          : { ...h }
      }),
    })),

  rollbackConfirmation: (id, action) =>
    set((s) => ({
      hazards: s.hazards.map((h) => {
        if (h.id !== id) return h
        const prevCount = Math.max(1, h.report_count - 1)
        return action === "confirm"
          ? { ...h, report_count: prevCount, confidence: Math.min(1.0, prevCount / 5) }
          : { ...h }
      }),
    })),

  // ─── Legacy compat (delegate to integration layer) ───────────────────────────
  fetchHazards: async (lat, lon, radius = 1000) => {
    set({ isFetching: true })
    try {
      const { syncHazards } = await import("../integration/sync/hazardSync")
      await syncHazards({ lat, lon, radius_m: radius, active_only: true })
    } catch { /* silent */ } finally {
      set({ isFetching: false })
    }
  },

  submitReport: async ({ type, severity, description, lat, lon }) => {
    const { submitHazardReport } = await import("../integration/sync/hazardSync")
    await submitHazardReport({ lat, lon, type, severity, description }, { lat, lon })
  },

  confirmHazard: async (id, action) => {
    const pos = useNavigationPosition()
    const { confirmHazard } = await import("../integration/sync/hazardSync")
    await confirmHazard(id, { lat: pos?.lat ?? 0, lon: pos?.lon ?? 0, action })
  },
}))

function useNavigationPosition(): { lat: number; lon: number } | null {
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { useNavigationStore: nav } = require("./useNavigationStore")
    return nav.getState().currentPosition
  } catch { return null }
}
