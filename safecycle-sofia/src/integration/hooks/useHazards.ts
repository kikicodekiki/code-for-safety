import { useEffect, useCallback, useRef } from "react"
import { AppState, type AppStateStatus } from "react-native"
import { useHazardStore } from "../../stores/useHazardStore"
import { syncHazards, submitHazardReport, confirmHazard } from "../sync/hazardSync"
import { integrationConfig } from "../config"
import type { HazardReportCreate, HazardConfirmationCreate } from "../types/api"

export function useHazards(options: {
  autoRefresh?: boolean
  lat?:         number
  lon?:         number
  radiusM?:     number
} = {}) {
  const { autoRefresh = true, lat, lon, radiusM = 500 } = options

  const hazards      = useHazardStore((s) => s.hazards)
  const isSubmitting = useHazardStore((s) => s.isSubmitting)
  const submitError  = useHazardStore((s) => s.submitError)

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Initial fetch
  useEffect(() => {
    syncHazards({ lat, lon, radius_m: radiusM })
  }, [lat, lon, radiusM])

  // Periodic refresh
  useEffect(() => {
    if (!autoRefresh) return
    timerRef.current = setInterval(
      () => syncHazards({ lat, lon, radius_m: radiusM }),
      integrationConfig.hazardRefreshMs,
    )
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [autoRefresh, lat, lon, radiusM])

  // Refresh on foreground
  useEffect(() => {
    const sub = AppState.addEventListener("change", (state: AppStateStatus) => {
      if (state === "active") syncHazards({ lat, lon, radius_m: radiusM })
    })
    return () => sub.remove()
  }, [lat, lon, radiusM])

  const submitReport = useCallback(
    (report: HazardReportCreate, position: { lat: number; lon: number }) =>
      submitHazardReport(report, position),
    [],
  )

  const confirm = useCallback(
    (reportId: string, payload: HazardConfirmationCreate) =>
      confirmHazard(reportId, payload),
    [],
  )

  const refresh = useCallback(
    () => syncHazards({ lat, lon, radius_m: radiusM }),
    [lat, lon, radiusM],
  )

  return { hazards, isSubmitting, submitError, submitReport, confirm, refresh }
}
