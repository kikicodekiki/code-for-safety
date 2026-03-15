/**
 * Notification categories and action definitions.
 *
 * Categories allow the OS to attach action buttons to notifications.
 * Registered at app startup via Notifications.setNotificationCategoryAsync.
 *
 * iOS: action buttons appear in the notification long-press/banner expansion.
 * Android: action buttons appear in the notification drawer.
 */
import * as Notifications from "expo-notifications"

export const CATEGORY_IDS = {
  CROSSROAD:     "safecycle_crossroad",
  HAZARD_NEARBY: "safecycle_hazard_nearby",
  ROAD_CLOSED:   "safecycle_road_closed",
  ROUTE_CHANGED: "safecycle_route_changed",
} as const

export type CategoryId = (typeof CATEGORY_IDS)[keyof typeof CATEGORY_IDS]

/**
 * Registers all notification action categories with the OS.
 * Must be called once at app startup before any notifications are shown.
 */
export async function registerNotificationCategories(): Promise<void> {
  // Crossroad: dismiss-only (no action needed beyond awareness)
  await Notifications.setNotificationCategoryAsync(CATEGORY_IDS.CROSSROAD, [
    {
      identifier: "dismiss",
      buttonTitle: "Got it",
      options:     { isDestructive: false, isAuthenticationRequired: false },
    },
  ])

  // Hazard nearby: confirm the hazard to contribute data
  await Notifications.setNotificationCategoryAsync(CATEGORY_IDS.HAZARD_NEARBY, [
    {
      identifier: "confirm_hazard",
      buttonTitle: "Confirm hazard",
      options:     { isDestructive: false, isAuthenticationRequired: false },
    },
    {
      identifier: "dismiss",
      buttonTitle: "Dismiss",
      options:     { isDestructive: false, isAuthenticationRequired: false },
    },
  ])

  // Road closed: reroute action
  await Notifications.setNotificationCategoryAsync(CATEGORY_IDS.ROAD_CLOSED, [
    {
      identifier: "reroute",
      buttonTitle: "Reroute",
      options:     { isDestructive: false, isAuthenticationRequired: false },
    },
    {
      identifier: "dismiss",
      buttonTitle: "Stay on route",
      options:     { isDestructive: false, isAuthenticationRequired: false },
    },
  ])

  // Route changed: request new route
  await Notifications.setNotificationCategoryAsync(CATEGORY_IDS.ROUTE_CHANGED, [
    {
      identifier: "new_route",
      buttonTitle: "Get new route",
      options:     { isDestructive: false, isAuthenticationRequired: false },
    },
    {
      identifier: "dismiss",
      buttonTitle: "Keep current",
      options:     { isDestructive: false, isAuthenticationRequired: false },
    },
  ])
}
