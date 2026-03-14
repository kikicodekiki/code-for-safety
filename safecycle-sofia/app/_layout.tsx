import React, { useEffect } from "react"
import { Stack } from "expo-router"
import { StatusBar } from "expo-status-bar"
import { useSettingsStore } from "../src/stores/useSettingsStore"
import { wsManager } from "../src/services/websocket"
import { colors } from "../src/tokens"

export default function RootLayout() {
  const hydrateSettings = useSettingsStore((s) => s.hydrate)

  useEffect(() => {
    hydrateSettings()
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
