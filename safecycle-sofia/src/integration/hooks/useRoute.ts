import { useCallback } from "react"
import { useNavigationStore } from "../../stores/useNavigationStore"
import { syncRoute } from "../sync/routeSync"
import type { RouteRequest } from "../types/api"

export function useRoute() {
  const isLoading       = useNavigationStore((s) => s.isLoading)
  const route           = useNavigationStore((s) => s.route)
  const error           = useNavigationStore((s) => s.routeError)
  const lastRequest     = useNavigationStore((s) => s.lastRouteRequest)
  const setLastRequest  = useNavigationStore((s) => s.setLastRouteRequest)
  const clearError      = useNavigationStore((s) => s.setRouteError)

  const findRoute = useCallback(
    async (request: RouteRequest) => {
      setLastRequest(request)
      await syncRoute(request)
    },
    [setLastRequest],
  )

  const retry = useCallback(async () => {
    if (lastRequest) {
      clearError(null)
      await syncRoute(lastRequest)
    }
  }, [lastRequest, clearError])

  return { findRoute, isLoading, route, error, retry }
}
