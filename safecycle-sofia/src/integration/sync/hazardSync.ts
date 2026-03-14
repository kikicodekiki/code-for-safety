import { hazardService, GetHazardsParams } from "../services/hazardService"
import { useHazardStore } from "../../stores/useHazardStore"
import { OfflineError } from "../errors"
import type { HazardReportCreate, HazardConfirmationCreate, AggregatedHazardResponse } from "../types/api"

export async function syncHazards(params: GetHazardsParams = {}): Promise<void> {
  try {
    const hazards = await hazardService.getHazards({
      active_only: true,
      aggregated:  true,
      ...params,
    })
    useHazardStore.getState().setHazards(hazards)
  } catch (error) {
    if (!(error instanceof OfflineError)) {
      console.warn("[hazardSync] Failed to refresh hazards:", error)
    }
    // Silently fail — stale data is better than no data
  }
}

export async function submitHazardReport(
  report:   HazardReportCreate,
  position: { lat: number; lon: number },
): Promise<void> {
  const store = useHazardStore.getState()
  const provisionalId = `provisional-${Date.now()}`

  // Optimistic: show pin on map immediately
  const provisional: AggregatedHazardResponse = {
    id:                 provisionalId,
    lat:                position.lat,
    lon:                position.lon,
    hazard_type:        report.type,
    type_display_name:  report.type,
    type_icon:          "⏳",
    report_count:       1,
    consensus_severity: report.severity,
    effective_severity: report.severity,
    severity_label:     String(report.severity),
    confidence:         0,
    confidence_label:   "Pending",
    age_hours:          0,
    is_recent:          true,
    is_fresh:           true,
    description:        report.description,
    routing_excluded:   false,
    decay_factor:       1.0,
    effective_penalty:  null,
  }
  store.addProvisionalHazard(provisional)
  store.setSubmitting(true)
  store.setSubmitError(null)

  try {
    const result = await hazardService.submitReport(report)
    store.resolveProvisionalHazard(provisionalId, result.id)
    // Refresh to get the server-aggregated view
    await syncHazards()
  } catch (error) {
    store.removeProvisionalHazard(provisionalId)
    if (error instanceof OfflineError) {
      store.setSubmitError("No internet connection. Your report was not saved.")
    } else {
      store.setSubmitError("Failed to submit report. Please try again.")
    }
    throw error
  } finally {
    store.setSubmitting(false)
  }
}

export async function confirmHazard(
  reportId: string,
  payload:  HazardConfirmationCreate,
): Promise<void> {
  const store = useHazardStore.getState()
  store.optimisticallyConfirm(reportId, payload.action)
  try {
    await hazardService.confirmHazard(reportId, payload)
    await syncHazards()
  } catch {
    store.rollbackConfirmation(reportId, payload.action)
  }
}
