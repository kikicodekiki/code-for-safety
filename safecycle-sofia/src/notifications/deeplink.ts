/**
 * Notification tap → in-app navigation.
 *
 * When the user taps a system notification, this module interprets the
 * notification data and navigates to the appropriate in-app screen.
 *
 * Navigation uses expo-router's router.push(). The map screen is the
 * default destination for all safety alerts.
 */
import { router } from "expo-router"
import type { Notification } from "expo-notifications"
import type { NotificationType } from "./handler"

// Maps notification type → destination route in expo-router
const TYPE_TO_ROUTE: Partial<Record<NotificationType, string>> = {
  crossroad_dismount:     "/(app)",        // map screen — focus on crossroad
  awareness_zone_enter:   "/(app)",        // map screen
  hazard_nearby:          "/(app)",        // map screen — focus on hazard
  road_closed_ahead:      "/(app)",        // map screen — trigger reroute
  route_safety_degraded:  "/(app)",        // map screen
  hazard_confirmed_ahead: "/(app)",        // map screen
}

/**
 * Handle a notification tap. Navigates the user to the relevant screen.
 * Called from the Notifications.addNotificationResponseReceivedListener handler.
 */
export function handleNotificationDeeplink(notification: Notification): void {
  const data = notification.request.content.data
  const type = data?.type as NotificationType | undefined

  const route = (type && TYPE_TO_ROUTE[type]) ?? "/(app)"

  // Navigate with the notification data as params so the map can
  // focus/highlight the relevant element
  try {
    router.push({
      pathname: route as never,
      params: {
        notification_type: type ?? "",
        latitude:          data?.latitude  ? String(data.latitude)  : "",
        longitude:         data?.longitude ? String(data.longitude) : "",
      },
    })
  } catch {
    // Router may not be ready if app was killed — navigate to root
    router.push("/(app)" as never)
  }
}

/**
 * Handle a notification action button tap (e.g. "Reroute" on road closed).
 * Returns the action identifier for the caller to act on.
 */
export function getNotificationAction(
  actionIdentifier: string,
  notificationType: NotificationType | undefined
): "reroute" | "confirm_hazard" | "dismiss" | null {
  switch (actionIdentifier) {
    case "reroute":         return "reroute"
    case "confirm_hazard":  return "confirm_hazard"
    case "dismiss":         return "dismiss"
    default:                return null
  }
}
