/**
 * Local notification scheduler — fires system notifications from the
 * background GPS task when the app is backgrounded.
 *
 * Uses expo-notifications local scheduling (trigger: null = immediate).
 * Each type gets routed to its Android channel for correct importance/sound.
 */
import * as Notifications from "expo-notifications"
import type { NotificationType, NotificationUrgency } from "./handler"

interface LocalNotificationOptions {
  type:     NotificationType
  urgency:  NotificationUrgency
  title:    string
  body:     string
  data?:    Record<string, unknown>
  sound?:   boolean
}

// Map urgency → Android channel ID (defined in setup.ts)
const URGENCY_TO_CHANNEL: Record<NotificationUrgency, string> = {
  critical: "safecycle_critical",
  high:     "safecycle_high",
  medium:   "safecycle_medium",
  low:      "safecycle_medium",
}

/**
 * Schedule an immediate local notification.
 * Safe to call from background tasks — expo-notifications handles it.
 */
export async function scheduleLocalNotification(
  opts: LocalNotificationOptions
): Promise<string> {
  const channelId = URGENCY_TO_CHANNEL[opts.urgency]

  return Notifications.scheduleNotificationAsync({
    content: {
      title:     opts.title,
      body:      opts.body,
      sound:     opts.sound ?? false,
      data:      {
        type:    opts.type,
        urgency: opts.urgency,
        ...(opts.data ?? {}),
      },
      // Android: route to the correct importance channel
      ...(channelId ? { androidChannelId: channelId } : {}),
    },
    trigger: null,  // immediate
  })
}

// ── Per-type convenience functions ────────────────────────────────────────────
// Called from gpsTask.ts for background local push delivery.

export async function scheduleCrossroadAlert(distanceM: number): Promise<void> {
  await scheduleLocalNotification({
    type:    "crossroad_dismount",
    urgency: "high",
    title:   "Intersection ahead",
    body:    `Consider dismounting — intersection ${Math.round(distanceM)}m ahead`,
    sound:   true,
    data:    { distance_m: distanceM },
  })
}

export async function scheduleAwarenessZoneAlert(
  zoneType: string,
  zoneName: string
): Promise<void> {
  await scheduleLocalNotification({
    type:    "awareness_zone_enter",
    urgency: "medium",
    title:   "Awareness zone",
    body:    `Children may be present — ${zoneName.replace(/_/g, " ")}`,
    sound:   false,
    data:    { zone_type: zoneType, zone_name: zoneName },
  })
}

export async function scheduleHazardNearbyAlert(
  hazardType: string,
  distanceM:  number,
  severity?:  number
): Promise<void> {
  const htype = hazardType.replace(/_/g, " ")
  const body  = `${htype} — ${Math.round(distanceM)}m ahead`

  await scheduleLocalNotification({
    type:    "hazard_nearby",
    urgency: "high",
    title:   "Hazard ahead",
    body,
    sound:   true,
    data:    { hazard_type: hazardType, distance_m: distanceM, severity },
  })
}

export async function scheduleRoadClosedAlert(description?: string): Promise<void> {
  const body = description
    ? `Your route has a road closure. Rerouting recommended. ${description}`
    : "Your route has a road closure. Rerouting recommended."

  await scheduleLocalNotification({
    type:    "road_closed_ahead",
    urgency: "critical",
    title:   "Road closed on your route",
    body,
    sound:   true,
  })
}

export async function scheduleRouteDegradedAlert(
  oldScore: number,
  newScore: number
): Promise<void> {
  const pct = (v: number) => `${Math.round(v * 100)}%`
  await scheduleLocalNotification({
    type:    "route_safety_degraded",
    urgency: "medium",
    title:   "Route safety changed",
    body:    `Safety score dropped from ${pct(oldScore)} to ${pct(newScore)}. Consider requesting a new route.`,
    sound:   false,
    data:    { old_score: oldScore, new_score: newScore },
  })
}
