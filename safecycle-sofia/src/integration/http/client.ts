import axios, {
  AxiosInstance,
  AxiosError,
  AxiosRequestConfig,
  InternalAxiosRequestConfig,
} from "axios"
import { integrationConfig } from "../config"
import { normaliseApiError } from "../errors"
import { generateRequestId, sleep } from "../utils"

export const apiClient: AxiosInstance = axios.create({
  baseURL: integrationConfig.apiBaseUrl,
  timeout: integrationConfig.httpTimeoutMs,
  headers: {
    "Content-Type": "application/json",
    Accept:         "application/json",
    "X-Client":     "safecycle-mobile",
  },
})

// ─── Request interceptor ──────────────────────────────────────────────────────
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    config.headers["X-Request-ID"] = generateRequestId()

    if (integrationConfig.isDevelopment) {
      console.log(
        `[API →] ${config.method?.toUpperCase()} ${config.url}`,
        config.params ?? config.data ?? "",
      )
    }
    return config
  },
  (error) => Promise.reject(error),
)

// ─── Response interceptor ─────────────────────────────────────────────────────
apiClient.interceptors.response.use(
  (response) => {
    if (integrationConfig.isDevelopment) {
      console.log(`[API ←] ${response.status} ${response.config.url}`)
    }
    return response
  },
  async (error: AxiosError) => {
    const config = error.config as AxiosRequestConfig & { _retryCount?: number }

    if (
      shouldRetry(error) &&
      (config?._retryCount ?? 0) < integrationConfig.maxRetryAttempts
    ) {
      config._retryCount = (config._retryCount ?? 0) + 1
      const delay = integrationConfig.retryBackoffBase * 2 ** (config._retryCount - 1)
      await sleep(delay)
      return apiClient.request(config)
    }

    return Promise.reject(normaliseApiError(error))
  },
)

function shouldRetry(error: AxiosError): boolean {
  if (!error.response) return true
  return error.response.status >= 500 && error.response.status < 600
}
