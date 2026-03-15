import * as Location from "expo-location"
import * as TaskManager from "expo-task-manager"
import Constants from "expo-constants"
import { useNavigationStore } from "../stores/useNavigationStore"
import { useHazardStore } from "../stores/useHazardStore"
import { useSettingsStore } from "../stores/useSettingsStore"
import { wsManager } from "../services/websocket"
import {
  fireCrossroadAlert,
  fireAwarenessZoneAlert,
  fireHazardNearbyAlert,
} from "../services/notifications"
import type { Coordinate } from "../types"

export const BACKGROUND_LOCATION_TASK = "safecycle-gps-task"

const CROSSROAD_ALERT_RADIUS_M = 15
const AWARENESS_ZONE_RADIUS_M = 30
const HAZARD_ALERT_RADIUS_M = 20

// Track last alert times to avoid spamming notifications
const lastAlertTime: Record<string, number> = {}
const ALERT_COOLDOWN_MS = 30_000

function haversineDistanceM(a: Coordinate, b: Coordinate): number {
  const R = 6_371_000
  const toRad = (deg: number) => (deg * Math.PI) / 180
  const dLat = toRad(b.lat - a.lat)
  const dLon = toRad(b.lon - a.lon)
  const sinDLat = Math.sin(dLat / 2)
  const sinDLon = Math.sin(dLon / 2)
  const c =
    2 *
    Math.asin(
      Math.sqrt(
        sinDLat * sinDLat +
          Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * sinDLon * sinDLon
      )
    )
  return R * c
}

function canAlert(key: string): boolean {
  const now = Date.now()
  const last = lastAlertTime[key] ?? 0
  if (now - last > ALERT_COOLDOWN_MS) {
    lastAlertTime[key] = now
    return true
  }
  return false
}

TaskManager.defineTask(BACKGROUND_LOCATION_TASK, async ({ data, error }) => {
  if (error) {
    return
  }

  const { locations } = data as { locations: Location.LocationObject[] }
  const location = locations[0]
  if (!location) return

  const { latitude, longitude, heading, speed } = location.coords
  const pos: Coordinate = { lat: latitude, lon: longitude }

  // 1. Update position in store
  useNavigationStore.getState().updatePosition(pos)
  if (heading !== null) {
    useNavigationStore.getState().setHeading(heading)
  }

  // 2. Send to WebSocket
  wsManager.sendGPS({
    lat: latitude,
    lon: longitude,
    heading: heading ?? 0,
    speed_kmh: speed !== null ? speed * 3.6 : 0,
  })

  const settings = useSettingsStore.getState()
  const navStore = useNavigationStore.getState()
  const route = navStore.route

  if (!route) return

  // 3. Check crossroad proximity
  let nearestCrossroad = Infinity
  for (const node of route.crossroad_nodes) {
    const dist = haversineDistanceM(pos, node)
    if (dist < nearestCrossroad) nearestCrossroad = dist
  }

  useNavigationStore.getState().setNearestCrossroadDistance(
    nearestCrossroad === Infinity ? null : nearestCrossroad
  )

  if (
    nearestCrossroad <= CROSSROAD_ALERT_RADIUS_M &&
    settings.crossroadAlertsEnabled &&
    canAlert("crossroad")
  ) {
    await fireCrossroadAlert()
    useNavigationStore.getState().setZoneStatus("danger")
    return
  }

  // 4. Check awareness zones
  let inAwarenessZone = false
  for (const zone of route.awareness_zones) {
    const dist = haversineDistanceM(pos, zone.center)
    if (dist <= AWARENESS_ZONE_RADIUS_M) {
      inAwarenessZone = true
      if (settings.awarenessZoneAlertsEnabled && canAlert(`zone_${zone.center.lat}_${zone.center.lon}`)) {
        await fireAwarenessZoneAlert()
      }
      break
    }
  }

  if (inAwarenessZone) {
    useNavigationStore.getState().setZoneStatus("caution")
    return
  }

  // 5. Check active hazards
  const activeHazards = useHazardStore.getState().getActiveHazards()
  let inHazardZone = false
  for (const hazard of activeHazards) {
    const hazardPos: Coordinate = { lat: hazard.lat, lon: hazard.lon }
    const dist = haversineDistanceM(pos, hazardPos)
    if (dist <= HAZARD_ALERT_RADIUS_M) {
      inHazardZone = true
      if (settings.hazardAlertsEnabled && canAlert(`hazard_${hazard.id}`)) {
        await fireHazardNearbyAlert(hazard.hazard_type, dist)
      }
      break
    }
  }

  if (inHazardZone) {
    useNavigationStore.getState().setZoneStatus("danger")
  } else {
    useNavigationStore.getState().setZoneStatus("safe")
  }
})

export async function startBackgroundLocationTask(): Promise<void> {
  // Background location is not supported in Expo Go
  if (Constants.executionEnvironment === "storeClient") return

  const { status } = await Location.requestBackgroundPermissionsAsync()
  if (status !== "granted") return

  const isRunning = await Location.hasStartedLocationUpdatesAsync(BACKGROUND_LOCATION_TASK)
  if (isRunning) return

  await Location.startLocationUpdatesAsync(BACKGROUND_LOCATION_TASK, {
    accuracy: Location.Accuracy.BestForNavigation,
    timeInterval: 10_000,
    distanceInterval: 5,
    deferredUpdatesInterval: 10_000,
    showsBackgroundLocationIndicator: true,
    foregroundService: {
      notificationTitle: "SafeCycle is active",
      notificationBody: "Monitoring your route for safety alerts",
      notificationColor: "#00C97B",
    },
  })
}

export async function stopBackgroundLocationTask(): Promise<void> {
  const isRunning = await Location.hasStartedLocationUpdatesAsync(BACKGROUND_LOCATION_TASK)
  if (isRunning) {
    await Location.stopLocationUpdatesAsync(BACKGROUND_LOCATION_TASK)
  }
}
