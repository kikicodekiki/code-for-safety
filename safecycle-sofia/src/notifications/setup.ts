/**
 * Notification setup — permission request and FCM token registration.
 *
 * Call setupNotifications() once on app mount (inside _layout.tsx useEffect).
 * It is idempotent — safe to call multiple times.
 */
import * as Notifications from "expo-notifications"
import * as Device from "expo-device"
import { Platform } from "react-native"
import { deviceService } from "../integration/services/deviceService"

// ── Android notification channels ────────────────────────────────────────────
// One channel per urgency level so the OS can apply different importance levels.

const ANDROID_CHANNELS = [
  {
    id:               "safecycle_critical",
    name:             "SafeCycle Critical Alerts",
    importance:       Notifications.AndroidImportance.MAX,
    vibrationPattern: [0, 200, 100, 200, 100, 200], // repeat for CRITICAL
    lightColor:       "#E8453C",
    sound:            "default",
    description:      "Road closures and immediate safety alerts",
  },
  {
    id:               "safecycle_high",
    name:             "SafeCycle Safety Alerts",
    importance:       Notifications.AndroidImportance.HIGH,
    vibrationPattern: [0, 200, 100, 200],
    lightColor:       "#F5A623",
    sound:            "default",
    description:      "Intersections and hazard alerts",
  },
  {
    id:               "safecycle_medium",
    name:             "SafeCycle Awareness Alerts",
    importance:       Notifications.AndroidImportance.DEFAULT,
    vibrationPattern: [0, 150],
    lightColor:       "#3498DB",
    sound:            undefined,
    description:      "Awareness zones and route changes",
  },
] as const

// ── Foreground presentation ───────────────────────────────────────────────────
Notifications.setNotificationHandler({
  handleNotification: async (notification) => {
    const urgency = notification.request.content.data?.urgency as string | undefined
    const isCriticalOrHigh = urgency === "critical" || urgency === "high"
    return {
      shouldShowBanner: true,
      shouldShowList:   true,
      shouldPlaySound:  isCriticalOrHigh,
      shouldSetBadge:   false,
    }
  },
})

export async function setupNotifications(): Promise<string | null> {
  if (!Device.isDevice) {
    // Push notifications require a physical device
    return null
  }

  // ── Request permission ────────────────────────────────────────────────────
  const { status: existing } = await Notifications.getPermissionsAsync()
  let finalStatus = existing

  if (existing !== "granted") {
    const { status } = await Notifications.requestPermissionsAsync()
    finalStatus = status
  }

  if (finalStatus !== "granted") {
    return null
  }

  // ── Android channels ──────────────────────────────────────────────────────
  if (Platform.OS === "android") {
    for (const channel of ANDROID_CHANNELS) {
      await Notifications.setNotificationChannelAsync(channel.id, {
        name:             channel.name,
        importance:       channel.importance,
        vibrationPattern: [...channel.vibrationPattern],
        lightColor:       channel.lightColor,
        sound:            channel.sound ?? null,
        description:      channel.description,
      })
    }
  }

  // ── Get and register push token ───────────────────────────────────────────
  try {
    await deviceService.registerPushToken()

    const tokenData = await Notifications.getExpoPushTokenAsync()
    return tokenData.data
  } catch (err) {
    // Token registration failure is non-fatal — local notifications still work
    console.warn("[SafeCycle] Push token registration failed:", err)
    return null
  }
}

export async function requestNotificationPermissions(): Promise<boolean> {
  if (!Device.isDevice) return false
  const { status: existing } = await Notifications.getPermissionsAsync()
  if (existing === "granted") return true
  const { status } = await Notifications.requestPermissionsAsync()
  return status === "granted"
}
