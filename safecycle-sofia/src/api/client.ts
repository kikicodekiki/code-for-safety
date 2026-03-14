import axios, { AxiosInstance } from "axios"
import { Platform } from "react-native"
import type { Coordinate, Hazard, HazardType, RouteResponse } from "../types"

const getDefaultBaseUrl = () => {
  // On Android emulators, "localhost" refers to the emulator itself, so we need to
  // use the special 10.0.2.2 host to reach the development machine.
  if (Platform.OS === "android") {
    return "http://10.0.2.2:8000"
  }

  // iOS simulator and web can access the host via localhost.
  return "http://localhost:8000"
}

const resolveBaseUrl = () => {
  const envUrl = process.env.EXPO_PUBLIC_API_BASE_URL

  if (!envUrl) {
    return getDefaultBaseUrl()
  }

  // If someone sets localhost in env, fix it automatically for Android emulators.
  if (Platform.OS === "android" && envUrl.includes("localhost")) {
    return envUrl.replace("localhost", "10.0.2.2")
  }

  return envUrl
}

const BASE_URL = resolveBaseUrl()

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
