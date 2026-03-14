import { apiClient } from "../http/client"
import type {
  AggregatedHazardResponse,
  HazardConfirmationCreate,
  HazardReportCreate,
  HazardReportResponse,
  HazardStatsResponse,
} from "../types/api"

export interface GetHazardsParams {
  lat?:          number
  lon?:          number
  radius_m?:     number
  type?:         string
  min_severity?: number
  aggregated?:   boolean
  active_only?:  boolean
}

export const hazardService = {
  async submitReport(report: HazardReportCreate): Promise<HazardReportResponse> {
    const { data } = await apiClient.post<HazardReportResponse>("/hazard", report)
    return data
  },

  async getHazards(params: GetHazardsParams = {}): Promise<AggregatedHazardResponse[]> {
    const { data } = await apiClient.get<AggregatedHazardResponse[]>("/hazards", { params })
    return data
  },

  async confirmHazard(reportId: string, payload: HazardConfirmationCreate): Promise<void> {
    await apiClient.post(`/hazard/${reportId}/confirm`, payload)
  },

  async removeHazard(reportId: string, reason: string): Promise<void> {
    await apiClient.delete(`/hazard/${reportId}`, { params: { reason } })
  },

  async getStatistics(): Promise<HazardStatsResponse> {
    const { data } = await apiClient.get<HazardStatsResponse>("/hazards/stats")
    return data
  },
}
