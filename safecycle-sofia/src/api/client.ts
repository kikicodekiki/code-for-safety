import axios, { AxiosInstance } from "axios"
import type {
  AggregatedHazardResponse,
  HazardConfirmationCreate,
  HazardReportCreate,
  HazardReportResponse,
  HazardType,
  RouteResponse,
} from "../types"

const BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL ?? "http://localhost:8000"

interface RouteParams {
  origin_lat: number
  origin_lon: number
  dest_lat: number
  dest_lon: number
}

interface HazardQueryParams {
  lat?: number
  lon?: number
  radius_m?: number
  type?: HazardType
  min_severity?: number
  aggregated?: boolean
  active_only?: boolean
}

interface DeviceTokenBody {
  token: string
  platform: "ios" | "android"
}

class ApiClient {
  private readonly http: AxiosInstance

  constructor(baseURL: string) {
    this.http = axios.create({
      baseURL,
      timeout: 15_000,
      headers: { "Content-Type": "application/json" },
    })
  }

  async getRoute(params: RouteParams): Promise<RouteResponse> {
    const { data } = await this.http.get<RouteResponse>("/route", { params })
    return data
  }

  async reportHazard(body: HazardReportCreate): Promise<HazardReportResponse> {
    const { data } = await this.http.post<HazardReportResponse>("/hazard", body)
    return data
  }

  async getHazards(params?: HazardQueryParams): Promise<AggregatedHazardResponse[]> {
    const { data } = await this.http.get<AggregatedHazardResponse[]>("/hazards", { params })
    return data
  }

  async confirmHazard(
    reportId: string,
    payload: HazardConfirmationCreate
  ): Promise<void> {
    await this.http.post(`/hazard/${reportId}/confirm`, payload)
  }

  async deleteHazard(reportId: string, reason: string): Promise<void> {
    await this.http.delete(`/hazard/${reportId}`, { params: { reason } })
  }

  async registerDeviceToken(body: DeviceTokenBody): Promise<void> {
    await this.http.post("/device-token", body)
  }

  getWebSocketUrl(): string {
    const wsBase = BASE_URL.replace(/^http/, "ws")
    return `${wsBase}/ws/gps`
  }
}

export const apiClient = new ApiClient(BASE_URL)

export type { RouteParams, HazardQueryParams, DeviceTokenBody }
