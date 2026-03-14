import { Platform } from "react-native"
import * as Notifications from "expo-notifications"
import { apiClient } from "../http/client"
import type { DeviceTokenCreate } from "../types/api"

export const deviceService = {
  async registerPushToken(): Promise<void> {
    try {
      const tokenData = await Notifications.getExpoPushTokenAsync()
      if (!tokenData?.data) return

      const payload: DeviceTokenCreate = {
        token:    tokenData.data,
        platform: Platform.OS === "ios" ? "ios" : "android",
      }
      await apiClient.post("/device-token", payload)
    } catch {
      // Non-fatal — push notifications degrade gracefully
    }
  },
}
