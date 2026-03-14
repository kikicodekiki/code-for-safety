import axios, { AxiosInstance } from "axios"
import type { Coordinate, Hazard, HazardType, RouteResponse } from "../types"

const BASE_URL = process.env.EXPO_PUBLIC_API_BASE_URL ?? "http://localhost:8000"

interface RouteParams {
  origin_lat: number
  origin_lon: number
  dest_lat: number
  dest_lon: number
}

interface HazardReportBody {
  lat: number
  lon: number
  type: HazardType
  description?: string
}

interface HazardReportResponse {
  id: string
  status: "reported"
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

  async reportHazard(body: HazardReportBody): Promise<HazardReportResponse> {
    const { data } = await this.http.post<HazardReportResponse>("/hazard", body)
    return data
  }

  async getHazards(): Promise<Hazard[]> {
    const { data } = await this.http.get<Hazard[]>("/hazards")
    return data
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

export type { RouteParams, HazardReportBody, HazardReportResponse, DeviceTokenBody }
