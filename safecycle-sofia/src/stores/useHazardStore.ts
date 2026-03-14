import { create } from "zustand"
import { apiClient } from "../api/client"
import type { Hazard, HazardReport } from "../types"

interface HazardState {
  hazards: Hazard[]
  myReports: HazardReport[]
  isFetching: boolean
  isSubmitting: boolean
  submitError: string | null
  fetchHazards: () => Promise<void>
  submitReport: (report: HazardReport) => Promise<void>
  getActiveHazards: () => Hazard[]
  getRecentHazards: () => Hazard[]
  clearSubmitError: () => void
}

export const useHazardStore = create<HazardState>((set, get) => ({
  hazards: [],
  myReports: [],
  isFetching: false,
  isSubmitting: false,
  submitError: null,

  fetchHazards: async () => {
    set({ isFetching: true })
    try {
      const hazards = await apiClient.getHazards()
      set({ hazards })
    } finally {
      set({ isFetching: false })
    }
  },

  submitReport: async (report) => {
    set({ isSubmitting: true, submitError: null })
    try {
      const response = await apiClient.reportHazard({
        lat: report.lat,
        lon: report.lon,
        type: report.type,
        description: report.description,
      })

      const newHazard: Hazard = {
        ...report,
        id: response.id,
        age_hours: 0,
      }

      set((state) => ({
        hazards: [newHazard, ...state.hazards],
        myReports: [report, ...state.myReports],
      }))
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to submit report"
      set({ submitError: message })
      throw err
    } finally {
      set({ isSubmitting: false })
    }
  },

  getActiveHazards: () => {
    return get().hazards.filter((h) => h.age_hours < 10)
  },

  getRecentHazards: () => {
    return get().hazards.filter((h) => h.age_hours < 1)
  },

  clearSubmitError: () => set({ submitError: null }),
}))
