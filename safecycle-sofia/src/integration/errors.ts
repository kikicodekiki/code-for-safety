import type { AxiosError } from "axios"

export class OfflineError extends Error {
  readonly code = "OFFLINE"
  constructor() {
    super("No internet connection. Check your network and try again.")
  }
}

export class ApiError extends Error {
  readonly code = "API_ERROR"
  constructor(
    public readonly status:     number,
    public readonly detail:     string,
    public readonly field?:     string,
    public readonly requestId?: string,
  ) {
    super(detail)
  }
}

export class RouteNotFoundError extends ApiError {
  readonly code = "ROUTE_NOT_FOUND"
}

export class OutsideBboxError extends ApiError {
  readonly code = "OUTSIDE_BBOX"
  constructor(requestId?: string) {
    super(
      422,
      "This location is outside Sofia. SafeCycle only covers Sofia, Bulgaria.",
      undefined,
      requestId,
    )
  }
}

export class BackendUnavailableError extends Error {
  readonly code = "BACKEND_UNAVAILABLE"
  constructor() {
    super("SafeCycle server is temporarily unavailable. Please try again shortly.")
  }
}

export class GraphNotReadyError extends Error {
  readonly code = "GRAPH_NOT_READY"
  constructor() {
    super("The routing engine is still loading. Please wait a moment and try again.")
  }
}

export function normaliseApiError(error: unknown): Error {
  if (error instanceof OfflineError)          return error
  if (error instanceof ApiError)              return error
  if (error instanceof BackendUnavailableError) return error
  if (error instanceof GraphNotReadyError)    return error

  const axiosError = error as AxiosError
  if (!axiosError.response) {
    if (axiosError.code === "ECONNABORTED" || axiosError.code === "ERR_NETWORK") {
      return new BackendUnavailableError()
    }
    return new OfflineError()
  }

  const status    = axiosError.response.status
  const data      = axiosError.response.data as Record<string, unknown>
  const detail    = (data?.detail ?? data?.message ?? "An unexpected error occurred") as string
  const requestId = axiosError.config?.headers?.["X-Request-ID"] as string | undefined

  if (status === 404 && axiosError.config?.url?.includes("/route")) {
    return new RouteNotFoundError(status, String(detail), undefined, requestId)
  }
  if (status === 422) {
    const firstError = Array.isArray(detail) ? detail[0] : null
    if (firstError?.loc?.includes("lat") || firstError?.loc?.includes("lon")) {
      return new OutsideBboxError(requestId)
    }
    const field = firstError?.loc?.join(".") ?? undefined
    return new ApiError(status, firstError?.msg ?? String(detail), field, requestId)
  }
  if (status === 503) return new GraphNotReadyError()
  if (status >= 500)  return new BackendUnavailableError()

  return new ApiError(status, typeof detail === "string" ? detail : JSON.stringify(detail), undefined, requestId)
}
