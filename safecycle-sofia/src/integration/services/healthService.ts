import { apiClient } from "../http/client"
import { GraphNotReadyError } from "../errors"
import type { HealthResponse, ReadinessResponse } from "../types/api"
import { sleep } from "../utils"

export const healthService = {
  async ping(): Promise<HealthResponse> {
    const { data } = await apiClient.get<HealthResponse>("/health")
    return data
  },

  async checkReadiness(): Promise<ReadinessResponse> {
    const { data } = await apiClient.get<ReadinessResponse>("/health/ready")
    return data
  },

  async waitUntilReady(timeoutMs = 30_000, intervalMs = 2_000): Promise<void> {
    const deadline = Date.now() + timeoutMs
    while (Date.now() < deadline) {
      try {
        const status = await healthService.checkReadiness()
        if (status.status === "ready") return
      } catch {
        // backend not yet up — keep polling
      }
      await sleep(intervalMs)
    }
    throw new GraphNotReadyError()
  },
}
