/**
 * Notification handler — foreground and background notification routing.
 *
 * Foreground handler: converts received notifications into in-app AlertBanner
 * entries via useNotificationStore.
 *
 * Background tap handler: routes notification taps to the correct screen
 * via deeplink navigation.
 *
 * WebSocket event handler: converts WS proximity events into the same
 * notification model so the AlertQueue renders them uniformly.
 */
import * as Notifications from "expo-notifications"
import type { NotificationResponse } from "expo-notifications"
import type { WSServerEvent } from "../integration/types/api"
import type { InAppNotification } from "../stores/useNotificationStore"
import { handleNotificationDeeplink } from "./deeplink"

export type NotificationType =
  | "crossroad_dismount"
  | "awareness_zone_enter"
  | "hazard_nearby"
  | "road_closed_ahead"
  | "route_safety_degraded"
  | "hazard_confirmed_ahead"
  | "lights_on"

export type NotificationUrgency = "critical" | "high" | "medium" | "low"

// ── Foreground notification handler ──────────────────────────────────────────

/**
 * Converts a received expo-notifications Notification into our internal
 * InAppNotification model. Returns null if the notification should be
 * silently dropped (e.g. unknown type).
 */
export function notificationToInApp(
  notification: Notifications.Notification
): InAppNotification | null {
  const { title, body, data } = notification.request.content
  if (!title || !body) return null

  const type    = (data?.type as NotificationType)    ?? "hazard_nearby"
  const urgency = (data?.urgency as NotificationUrgency) ?? "medium"

  return {
    id:        notification.request.identifier,
    type,
    urgency,
    title:     title,
    body:      body,
    data:      (data ?? {}) as Record<string, unknown>,
    receivedAt: Date.now(),
    read:      false,
  }
}

// ── WebSocket event → InAppNotification ──────────────────────────────────────

const WS_EVENT_TYPE_MAP: Record<WSServerEvent["event"], NotificationType> = {
  crossroad:     "crossroad_dismount",
  awareness_zone: "awareness_zone_enter",
  hazard_nearby: "hazard_nearby",
}

const WS_EVENT_URGENCY_MAP: Record<WSServerEvent["event"], NotificationUrgency> = {
  crossroad:      "high",
  awareness_zone: "medium",
  hazard_nearby:  "high",
}

/**
 * Converts a WebSocket server event into an InAppNotification for display
 * in the AlertQueue. Called from the WS event handler in useNotifications.
 */
export function wsEventToInApp(event: WSServerEvent): InAppNotification {
  const type    = WS_EVENT_TYPE_MAP[event.event]
  const urgency = WS_EVENT_URGENCY_MAP[event.event]

  let title = "Alert"
  let body  = ""

  if (event.event === "crossroad") {
    const dist = (event.payload as { distance_m?: number }).distance_m
    title = "Intersection ahead"
    body  = dist ? `Consider dismounting — intersection ${Math.round(dist)}m ahead` : "Consider dismounting at the upcoming intersection"
  } else if (event.event === "awareness_zone") {
    const p = event.payload as { zone_type?: string; zone_name?: string }
    title = "Awareness zone"
    body  = `Children may be present — ${(p.zone_name ?? p.zone_type ?? "sensitive area").replace(/_/g, " ")}`
  } else if (event.event === "hazard_nearby") {
    const p = event.payload as {
      hazard?: { hazard_type?: string; consensus_severity?: number }
      distance_m?: number
    }
    title = "Hazard ahead"
    const htype = (p.hazard?.hazard_type ?? "hazard").replace(/_/g, " ")
    const dist  = p.distance_m
    body  = dist ? `${htype} — ${Math.round(dist)}m ahead` : htype
  }

  return {
    id:         `ws_${event.event}_${Date.now()}`,
    type,
    urgency,
    title,
    body,
    data:       event.payload as Record<string, unknown>,
    receivedAt: Date.now(),
    read:       false,
  }
}

// ── Notification tap handler ──────────────────────────────────────────────────

/**
 * Called when the user taps a system notification.
 * Navigates to the appropriate screen via handleNotificationDeeplink.
 */
export function setupNotificationResponseHandler(): () => void {
  const subscription = Notifications.addNotificationResponseReceivedListener(
    (response: NotificationResponse) => {
      handleNotificationDeeplink(response.notification)
    }
  )
  return () => subscription.remove()
}

/**
 * Called when a notification arrives while the app is in the foreground.
 * The store handles adding it to the in-app queue.
 */
export function setupForegroundNotificationListener(
  onReceive: (notification: InAppNotification) => void
): () => void {
  const subscription = Notifications.addNotificationReceivedListener(
    (notification) => {
      const inApp = notificationToInApp(notification)
      if (inApp) onReceive(inApp)
    }
  )
  return () => subscription.remove()
}
