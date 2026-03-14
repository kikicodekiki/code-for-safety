import { wsManager } from "../websocket/WebSocketManager"
import { useNavigationStore } from "../../stores/useNavigationStore"
import { haversineMetres } from "../utils"
import { integrationConfig } from "../config"
import type { GPSUpdate } from "../types/api"

export function updateGPS(update: GPSUpdate): void {
  const navStore = useNavigationStore.getState()

  navStore.updatePosition({ lat: update.lat, lon: update.lon })
  navStore.setHeading(update.heading)

  wsManager.sendGPS(update)

  // Client-side fallback when WebSocket is offline
  if (wsManager.getConnectionState() !== "connected") {
    _clientSideCrossroadCheck(update, navStore)
    _clientSideZoneCheck(update, navStore)
  }
}

function _clientSideCrossroadCheck(
  update:   GPSUpdate,
  navStore: ReturnType<typeof useNavigationStore.getState>,
): void {
  const route = navStore.route
  if (!route) return
  for (const crossroad of route.crossroad_nodes) {
    const dist = haversineMetres(update.lat, update.lon, crossroad.lat, crossroad.lon)
    if (dist <= integrationConfig.crossroadAlertRadiusM) {
      navStore.handleServerEvent({ event: "crossroad", payload: { distance_m: dist, node: crossroad } })
      break
    }
  }
}

function _clientSideZoneCheck(
  update:   GPSUpdate,
  navStore: ReturnType<typeof useNavigationStore.getState>,
): void {
  const route = navStore.route
  if (!route) return
  for (const zone of route.awareness_zones) {
    const dist = haversineMetres(update.lat, update.lon, zone.center.lat, zone.center.lon)
    if (dist <= zone.radius_m + 10) {
      navStore.handleServerEvent({ event: "awareness_zone", payload: { zone, distance_m: dist } })
      break
    }
  }
}
