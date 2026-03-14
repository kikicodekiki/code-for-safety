import * as Notifications from "expo-notifications"
import * as Device from "expo-device"
import { Platform } from "react-native"
import { apiClient } from "../api/client"

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
})

export async function requestNotificationPermissions(): Promise<boolean> {
  if (!Device.isDevice) {
    return false
  }

  const { status: existing } = await Notifications.getPermissionsAsync()
  if (existing === "granted") {
    return true
  }

  const { status } = await Notifications.requestPermissionsAsync()
  return status === "granted"
}

export async function registerForPushNotifications(): Promise<string | null> {
  const granted = await requestNotificationPermissions()
  if (!granted) return null

  if (Platform.OS === "android") {
    await Notifications.setNotificationChannelAsync("safecycle-alerts", {
      name: "SafeCycle Safety Alerts",
      importance: Notifications.AndroidImportance.HIGH,
      vibrationPattern: [0, 250, 250, 250],
      lightColor: "#00C97B",
    })
  }

  try {
    const token = await Notifications.getExpoPushTokenAsync()
    await apiClient.registerDeviceToken({
      token: token.data,
      platform: Platform.OS === "ios" ? "ios" : "android",
    })
    return token.data
  } catch {
    return null
  }
}

export async function fireCrossroadAlert(): Promise<void> {
  await Notifications.scheduleNotificationAsync({
    content: {
      title: "⚠️ Intersection ahead",
      body: "Consider dismounting for safety",
      sound: true,
      data: { category: "CROSSROAD_ALERT" },
    },
    trigger: null,
  })
}

export async function fireAwarenessZoneAlert(): Promise<void> {
  await Notifications.scheduleNotificationAsync({
    content: {
      title: "👁 Awareness zone",
      body: "Children may be present nearby",
      sound: false,
      data: { category: "AWARENESS_ZONE" },
    },
    trigger: null,
  })
}

export async function fireHazardNearbyAlert(hazardType: string, distanceM: number): Promise<void> {
  await Notifications.scheduleNotificationAsync({
    content: {
      title: "🚨 Hazard ahead",
      body: `${hazardType} reported ${Math.round(distanceM)} metres ahead`,
      sound: true,
      data: { category: "HAZARD_NEARBY" },
    },
    trigger: null,
  })
}
