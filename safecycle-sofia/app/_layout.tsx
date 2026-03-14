import React, { useEffect } from "react"
import { Stack } from "expo-router"
import { StatusBar } from "expo-status-bar"
import { useSettingsStore } from "../src/stores/useSettingsStore"
import { registerForPushNotifications } from "../src/services/notifications"
import { wsManager } from "../src/services/websocket"
import { colors } from "../src/tokens"

// Register the background location task
import "../src/tasks/gpsTask"

export default function RootLayout() {
  const hydrateSettings = useSettingsStore((s) => s.hydrate)

  useEffect(() => {
    hydrateSettings()
    registerForPushNotifications()
    wsManager.connect()

    return () => {
      wsManager.disconnect()
    }
  }, [hydrateSettings])

  return (
    <>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: colors.background },
          animation: "slide_from_right",
        }}
      >
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen
          name="route-detail"
          options={{
            presentation: "modal",
            animation: "slide_from_bottom",
          }}
        />
      </Stack>
    </>
  )
}
