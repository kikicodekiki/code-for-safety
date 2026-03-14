import React from "react"
import { StyleSheet, Text, TouchableOpacity, View } from "react-native"
import { MaterialCommunityIcons } from "@expo/vector-icons"
import { colors, radius, spacing, typography } from "../tokens"
import { useNavigationStore } from "../stores/useNavigationStore"
import type { RouteResponse, ZoneStatus } from "../types"

interface NavigationHUDProps {
  route: RouteResponse
  distanceRemainingM: number
  timeRemainingMin: number
}

const STATUS_CONFIG: Record<ZoneStatus, { label: string; color: string; icon: string }> = {
  safe: { label: "Safe path", color: colors.safe, icon: "🟢" },
  caution: { label: "Caution zone", color: colors.caution, icon: "🟡" },
  danger: { label: "Danger ahead", color: colors.danger, icon: "🔴" },
}

function formatDistance(metres: number): string {
  if (metres >= 1000) return `${(metres / 1000).toFixed(1)} km`
  return `${Math.round(metres)} m`
}

function formatTime(minutes: number): string {
  if (minutes < 1) return "<1 min"
  if (minutes < 60) return `${Math.round(minutes)} min`
  const h = Math.floor(minutes / 60)
  const m = Math.round(minutes % 60)
  return m > 0 ? `${h}h ${m}m` : `${h}h`
}

export const NavigationHUD = React.memo(function NavigationHUD({
  distanceRemainingM,
  timeRemainingMin,
}: NavigationHUDProps) {
  const zoneStatus = useNavigationStore((s) => s.currentZoneStatus)
  const clearRoute = useNavigationStore((s) => s.clearRoute)
  const config = STATUS_CONFIG[zoneStatus]

  return (
    <View style={styles.container}>
      <TouchableOpacity style={styles.closeButton} onPress={clearRoute}>
        <MaterialCommunityIcons name="close" size={20} color={colors.textSecondary} />
      </TouchableOpacity>
      <View style={styles.row}>
        <View style={styles.metricBlock}>
          <Text style={styles.metricValue}>{formatDistance(distanceRemainingM)}</Text>
          <Text style={styles.metricLabel}>Remaining</Text>
        </View>
        <View style={styles.divider} />
        <View style={styles.metricBlock}>
          <Text style={styles.metricValue}>{formatTime(timeRemainingMin)}</Text>
          <Text style={styles.metricLabel}>ETA</Text>
        </View>
        <View style={styles.divider} />
        <View style={styles.statusBlock}>
          <Text style={styles.statusIcon}>{config.icon}</Text>
          <Text style={[styles.statusLabel, { color: config.color }]}>{config.label}</Text>
        </View>
      </View>
    </View>
  )
})

const styles = StyleSheet.create({
  container: {
    backgroundColor: "rgba(13, 13, 13, 0.92)",
    borderTopLeftRadius: radius.xl,
    borderTopRightRadius: radius.xl,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.xl,
    borderTopWidth: 1,
    borderColor: colors.border,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
  },
  closeButton: {
    position: "absolute",
    top: spacing.md,
    right: spacing.md,
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.surfaceElevated,
    justifyContent: "center",
    alignItems: "center",
    borderWidth: 1,
    borderColor: colors.border,
    zIndex: 10,
  },
  metricBlock: {
    flex: 1,
    alignItems: "center",
  },
  metricValue: {
    color: colors.textPrimary,
    fontSize: typography.size.xxl,
    fontWeight: typography.weight.black,
  },
  metricLabel: {
    color: colors.textSecondary,
    fontSize: typography.size.xs,
    marginTop: spacing.xs,
  },
  divider: {
    width: 1,
    height: 40,
    backgroundColor: colors.border,
    marginHorizontal: spacing.sm,
  },
  statusBlock: {
    flex: 1.2,
    alignItems: "center",
  },
  statusIcon: {
    fontSize: typography.size.xl,
    marginBottom: spacing.xs,
  },
  statusLabel: {
    fontSize: typography.size.sm,
    fontWeight: typography.weight.semibold,
    textAlign: "center",
  },
})
