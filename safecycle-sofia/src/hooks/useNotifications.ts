/**
 * useNotifications — single hook surface for all notification logic.
 *
 * Responsibilities:
 * 1. Initialise push notification permissions and FCM token on mount
 * 2. Register notification action categories
 * 3. Listen for foreground system notifications → add to store queue
 * 4. Listen for notification tap responses → deeplink navigation
 * 5. Subscribe to WebSocket proximity events → add to store queue
 * 6. Expose the notification store state for components
 *
 * Usage:
 *   // In _layout.tsx or root component:
 *   useNotifications()
 *
 *   // In components that need the state:
 *   const { unreadCount, queue } = useNotifications()
 */
import { useEffect, useRef } from "react"
import { wsManager } from "../services/websocket"
import { setupNotifications } from "../notifications/setup"
import { registerNotificationCategories } from "../notifications/categories"
import {
  setupForegroundNotificationListener,
  setupNotificationResponseHandler,
  wsEventToInApp,
} from "../notifications/handler"
import {
  useNotificationStore,
  selectQueue,
  selectUnreadCount,
  selectHistory,
  type InAppNotification,
} from "../stores/useNotificationStore"
import type { WSServerEvent } from "../integration/types/api"

export interface UseNotificationsResult {
  queue:       InAppNotification[]
  history:     InAppNotification[]
  unreadCount: number
  markAllRead: () => void
}

export function useNotifications(): UseNotificationsResult {
  const addNotification = useNotificationStore((s) => s.addNotification)
  const markAllRead     = useNotificationStore((s) => s.markAllRead)
  const queue           = useNotificationStore(selectQueue)
  const history         = useNotificationStore(selectHistory)
  const unreadCount     = useNotificationStore(selectUnreadCount)

  // Prevent double-setup on re-renders
  const initialised = useRef(false)

  useEffect(() => {
    if (initialised.current) return
    initialised.current = true

    // ── 1. Permission + FCM token setup ──────────────────────────────────────
    setupNotifications().catch(console.warn)

    // ── 2. Notification categories (action buttons) ───────────────────────────
    registerNotificationCategories().catch(console.warn)

    // ── 3. Foreground system notification listener ────────────────────────────
    const removeForegroundListener = setupForegroundNotificationListener(
      (notification) => addNotification(notification)
    )

    // ── 4. Notification tap → deeplink handler ────────────────────────────────
    const removeTapHandler = setupNotificationResponseHandler()

    // ── 5. WebSocket event → in-app alert ────────────────────────────────────
    const removeWsCrossroad = wsManager.on("crossroad", (payload) => {
      const event: WSServerEvent = { event: "crossroad", payload }
      addNotification(wsEventToInApp(event))
    })

    const removeWsZone = wsManager.on("awareness_zone", (payload) => {
      const event: WSServerEvent = { event: "awareness_zone", payload }
      addNotification(wsEventToInApp(event))
    })

    const removeWsHazard = wsManager.on("hazard_nearby", (payload) => {
      const event: WSServerEvent = { event: "hazard_nearby", payload }
      addNotification(wsEventToInApp(event))
    })

    return () => {
      removeForegroundListener()
      removeTapHandler()
      removeWsCrossroad()
      removeWsZone()
      removeWsHazard()
    }
  }, [addNotification])

  return { queue, history, unreadCount, markAllRead }
}
