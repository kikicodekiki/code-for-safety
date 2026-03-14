import { routeService } from "../services/routeService"
import { useNavigationStore } from "../../stores/useNavigationStore"
import {
  RouteNotFoundError, OutsideBboxError,
  BackendUnavailableError, GraphNotReadyError, OfflineError,
} from "../errors"
import type { RouteRequest, RouteError } from "../types/api"

export async function syncRoute(request: RouteRequest): Promise<void> {
  const store = useNavigationStore.getState()
  store.setLoading(true)
  store.setRouteError(null)

  try {
    const route = await routeService.findSafeRoute(request)
    store.setRoute(route)
  } catch (error) {
    let routeError: RouteError

    if (error instanceof OfflineError) {
      routeError = { type: "offline", message: error.message, retryable: true }
    } else if (error instanceof RouteNotFoundError) {
      routeError = {
        type:      "not_found",
        message:   "No safe cycling route found to this destination. Try a different destination or adjust your settings.",
        retryable: false,
      }
    } else if (error instanceof OutsideBboxError) {
      routeError = {
        type:      "outside_bbox",
        message:   "SafeCycle only covers Sofia, Bulgaria. Please choose a destination within the city.",
        retryable: false,
      }
    } else if (error instanceof GraphNotReadyError) {
      routeError = { type: "graph_loading", message: error.message, retryable: true }
    } else if (error instanceof BackendUnavailableError) {
      routeError = { type: "server_error", message: error.message, retryable: true }
    } else {
      routeError = { type: "unknown", message: "Something went wrong. Please try again.", retryable: true }
    }

    store.setRouteError(routeError)
  } finally {
    store.setLoading(false)
  }
}
