import React, { useEffect } from "react"
import { Stack } from "expo-router"
import { StatusBar } from "expo-status-bar"
import { useSettingsStore } from "../src/stores/useSettingsStore"
import { useWebSocket } from "../src/integration/hooks/useWebSocket"
import { syncHazards } from "../src/integration/sync/hazardSync"
import { deviceService } from "../src/integration/services/deviceService"
import { colors } from "../src/tokens"

export default function RootLayout() {
  const hydrateSettings = useSettingsStore((s) => s.hydrate)

  // Manage WebSocket lifecycle for the entire app session
  useWebSocket({ enabled: true })

  useEffect(() => {
    hydrateSettings()

    // Initial hazard fetch — silent if backend is down
    syncHazards()

    // Register push token — non-blocking, degrades gracefully in Expo Go
    deviceService.registerPushToken()
  }, [hydrateSettings])

  return (
    <>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerShown:  false,
          contentStyle: { backgroundColor: colors.background },
        }}
      >
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen
          name="route-detail"
          options={{ 
            presentation: "transparentModal", 
            animation: "fade",
            contentStyle: { backgroundColor: "transparent" }
          }}
        />
      </Stack>
    </>
  )
}
