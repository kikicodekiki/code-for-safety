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
