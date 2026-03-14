import { useState, useEffect } from "react"
import { healthService } from "../services/healthService"
import type { ReadinessResponse } from "../types/api"

export type BackendReadinessState =
  | { status: "checking" }
  | { status: "ready";    details: ReadinessResponse["checks"] }
  | { status: "degraded"; details: ReadinessResponse["checks"] }
  | { status: "offline" }
  | { status: "timeout" }

export function useBackendReadiness() {
  const [state, setState] = useState<BackendReadinessState>({ status: "checking" })

  useEffect(() => {
    let cancelled = false

    const check = async () => {
      try {
        const result = await healthService.checkReadiness()
        if (cancelled) return
        setState({
          status:  result.status === "ready" ? "ready" : "degraded",
          details: result.checks,
        })
      } catch {
        if (cancelled) return
        // Backend not yet up — silently skip, show offline state
        setState({ status: "offline" })
      }
    }

    const timeout = setTimeout(() => {
      if (!cancelled) setState({ status: "timeout" })
    }, 30_000)

    check()

    return () => {
      cancelled = true
      clearTimeout(timeout)
    }
  }, [])

  return state
}
