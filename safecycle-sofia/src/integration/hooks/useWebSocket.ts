import { useEffect } from "react"
import { wsManager } from "../websocket/WebSocketManager"
import { useNavigationStore } from "../../stores/useNavigationStore"
import { useConnectionStore } from "../../stores/useConnectionStore"

export function useWebSocket(options: { enabled: boolean }) {
  const { enabled } = options
  const handleServerEvent  = useNavigationStore((s) => s.handleServerEvent)
  const setConnectionState = useConnectionStore((s) => s.setWsState)

  useEffect(() => {
    if (!enabled) return

    wsManager.connect()

    const unsubCrossroad = wsManager.on("crossroad",
      (payload) => handleServerEvent({ event: "crossroad", payload }),
    )
    const unsubZone = wsManager.on("awareness_zone",
      (payload) => handleServerEvent({ event: "awareness_zone", payload }),
    )
    const unsubHazard = wsManager.on("hazard_nearby",
      (payload) => handleServerEvent({ event: "hazard_nearby", payload }),
    )
    const unsubState = wsManager.onConnectionStateChange(setConnectionState)

    return () => {
      unsubCrossroad()
      unsubZone()
      unsubHazard()
      unsubState()
      wsManager.disconnect()
    }
  }, [enabled, handleServerEvent, setConnectionState])
}
