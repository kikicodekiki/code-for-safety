/**
 * Web stub for the Map tab.
 *
 * react-native-maps is native-only and cannot run in a browser.
 * Metro resolves index.web.tsx before index.tsx on web, so this file
 * is loaded on web while index.tsx (with the full MapView) is used on
 * iOS/Android — no changes needed to the native build.
 */
import React from "react"
import { StyleSheet, Text, View } from "react-native"
import { MaterialCommunityIcons } from "@expo/vector-icons"
import { colors, spacing, typography, radius } from "../../src/tokens"

export default function MapScreenWeb() {
  return (
    <View style={styles.root}>
      <MaterialCommunityIcons name="bike" size={72} color={colors.primary} />
      <Text style={styles.title}>SafeCycle Sofia</Text>
      <Text style={styles.subtitle}>Open on your phone</Text>
      <Text style={styles.body}>
        The interactive map and safe-route navigation require the iOS or Android
        app. Scan the QR code with Expo Go to run it on your device.
      </Text>
      <View style={styles.badge}>
        <MaterialCommunityIcons name="cellphone" size={16} color={colors.primary} />
        <Text style={styles.badgeText}>iOS &amp; Android only</Text>
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.background,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.xl,
    gap: spacing.md,
  },
  title: {
    color: colors.textPrimary,
    fontSize: typography.size.xxl,
    fontWeight: typography.weight.bold,
    marginTop: spacing.md,
  },
  subtitle: {
    color: colors.primary,
    fontSize: typography.size.lg,
    fontWeight: typography.weight.semibold,
  },
  body: {
    color: colors.textSecondary,
    fontSize: typography.size.md,
    textAlign: "center",
    lineHeight: 24,
    maxWidth: 400,
  },
  badge: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.full,
    borderWidth: 1,
    borderColor: colors.border,
    marginTop: spacing.sm,
  },
  badgeText: {
    color: colors.primary,
    fontSize: typography.size.sm,
    fontWeight: typography.weight.semibold,
  },
})
