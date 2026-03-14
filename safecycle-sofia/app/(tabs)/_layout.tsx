import React from "react"
import { Tabs } from "expo-router"
import { MaterialCommunityIcons } from "@expo/vector-icons"
import { colors, typography } from "../../src/tokens"

type IconProps = {
  color: string
  size: number
}

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarStyle: {
          backgroundColor: colors.surface,
          borderTopColor: colors.border,
          borderTopWidth: 1,
          height: 60,
          paddingBottom: 8,
        },
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.textDisabled,
        tabBarLabelStyle: {
          fontSize: typography.size.xs,
          fontWeight: typography.weight.medium,
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "Map",
          tabBarIcon: ({ color, size }: IconProps) => (
            <MaterialCommunityIcons name="map" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="report"
        options={{
          title: "Report",
          tabBarIcon: ({ color, size }: IconProps) => (
            <MaterialCommunityIcons name="alert-plus" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          title: "Settings",
          tabBarIcon: ({ color, size }: IconProps) => (
            <MaterialCommunityIcons name="cog" size={size} color={color} />
          ),
        }}
      />
    </Tabs>
  )
}
