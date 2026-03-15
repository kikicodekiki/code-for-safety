import React, { useEffect, useRef } from "react"
import {
  Animated as RNAnimated,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native"
import { router } from "expo-router"
import { MaterialCommunityIcons } from "@expo/vector-icons"
import { useNavigationStore } from "../src/stores/useNavigationStore"
import { SafetyScoreBar } from "../src/components/SafetyScoreBar"
import { DefaultDataChip } from "../src/components/DefaultDataChip"
import { startBackgroundLocationTask } from "../src/tasks/gpsTask"
import { colors, radius, spacing, typography } from "../src/tokens"
import type { AwarenessZone } from "../src/types"

const ZONE_ICONS: Record<AwarenessZone["type"], string> = {
  kindergarten: "🏫",
  playground: "🛝",
  bus_stop: "🚌",
  accident_hotspot: "⚠️",
}

const ZONE_LABELS: Record<AwarenessZone["type"], string> = {
  kindergarten: "Kindergarten",
  playground: "Playground",
  bus_stop: "Bus Stop",
  accident_hotspot: "Accident Hotspot",
}

export default function RouteDetailScreen() {
  const route = useNavigationStore((s) => s.route)
  const startNavigation = useNavigationStore((s) => s.startNavigation)
  const slideAnim = useRef(new RNAnimated.Value(400)).current
  const [zonesExpanded, setZonesExpanded] = React.useState(false)

  useEffect(() => {
    RNAnimated.spring(slideAnim, {
      toValue: 0,
      damping: 18,
      stiffness: 120,
      useNativeDriver: true,
    }).start()
  }, [slideAnim])

  if (!route) {
    router.back()
    return null
  }

  const distanceKm = (route.distance_m / 1000).toFixed(1)
  const scorePct = Math.round(route.safety_score * 100)
  const isLowScore = route.safety_score < 0.5

  const handleStart = async () => {
    startNavigation()
    await startBackgroundLocationTask()
    router.back()
  }

  return (
    <View style={styles.root}>
      <TouchableOpacity style={styles.backdrop} onPress={() => router.back()} />
      <RNAnimated.View
        style={[styles.sheet, { transform: [{ translateY: slideAnim }] }]}
      >
        {/* Handle */}
        <View style={styles.handleRow}>
          <View style={styles.handle} />
        </View>

        <ScrollView
          contentContainerStyle={styles.content}
          showsVerticalScrollIndicator={false}
        >
          {/* Header */}
          <View style={styles.headerRow}>
            {isLowScore ? (
              <MaterialCommunityIcons
                name="alert-circle"
                size={24}
                color={colors.caution}
              />
            ) : (
              <MaterialCommunityIcons
                name="check-circle"
                size={24}
                color={colors.primary}
              />
            )}
            <Text style={styles.headerTitle}>
              {isLowScore ? "Warning: limited safe options" : "Safe route found"}
            </Text>
          </View>

          {/* Safety score bar */}
          <View style={styles.section}>
            <SafetyScoreBar score={route.safety_score} />
          </View>

          {/* Stats row */}
          <View style={styles.statsRow}>
            <View style={styles.statPill}>
              <Text style={styles.statIcon}>🚴</Text>
              <Text style={styles.statText}>{distanceKm} km</Text>
            </View>
            <View style={styles.statPill}>
              <Text style={styles.statIcon}>⏱</Text>
              <Text style={styles.statText}>{route.duration_min} min</Text>
            </View>
            <View style={styles.statPill}>
              <Text style={styles.statIcon}>⭐</Text>
              <Text style={styles.statText}>Safety: {scorePct}%</Text>
            </View>
          </View>

          {/* Default data chips */}
          <View style={styles.chipsRow}>
            {route.surface_defaulted && (
              <DefaultDataChip
                label="Asphalt (default)"
                tooltip="Surface data unavailable — assuming standard asphalt. Exercise normal caution."
              />
            )}
            {route.speed_limit_defaulted && (
              <DefaultDataChip
                label="Speed: 50 km/h (default)"
                tooltip="No speed limit data available for this road. SafeCycle defaults to 50 km/h to ensure safe routing."
              />
            )}
          </View>

          {/* Speed limit warning */}
          {route.speed_limit_defaulted && (
            <View style={styles.speedWarning}>
              <MaterialCommunityIcons
                name="speedometer"
                size={18}
                color={colors.caution}
                style={{ marginRight: spacing.sm }}
              />
              <Text style={styles.speedWarningText}>
                Some road segments have no speed limit data — defaulted to 50 km/h. Stay
                alert.
              </Text>
            </View>
          )}

          {/* Crossroads count */}
          <View style={styles.infoRow}>
            <MaterialCommunityIcons
              name="traffic-light"
              size={18}
              color={colors.textSecondary}
            />
            <Text style={styles.infoText}>
              {route.crossroad_nodes.length} intersection
              {route.crossroad_nodes.length !== 1 ? "s" : ""} on this route — dismount
              alerts enabled
            </Text>
          </View>

          {/* Awareness zones */}
          {route.awareness_zones.length > 0 && (
            <View style={styles.section}>
              <TouchableOpacity
                style={styles.collapseHeader}
                onPress={() => setZonesExpanded((v) => !v)}
              >
                <Text style={styles.collapseTitle}>
                  {route.awareness_zones.length} awareness zone
                  {route.awareness_zones.length !== 1 ? "s" : ""} on this route
                </Text>
                <MaterialCommunityIcons
                  name={zonesExpanded ? "chevron-up" : "chevron-down"}
                  size={20}
                  color={colors.textSecondary}
                />
              </TouchableOpacity>
              {zonesExpanded &&
                route.awareness_zones.map((zone, i) => (
                  <View key={i} style={styles.zoneItem}>
                    <Text style={styles.zoneIcon}>{ZONE_ICONS[zone.type]}</Text>
                    <View style={styles.zoneDetails}>
                      <Text style={styles.zoneLabel}>
                        {zone.name ?? ZONE_LABELS[zone.type]}
                      </Text>
                      <Text style={styles.zoneType}>{ZONE_LABELS[zone.type]}</Text>
                    </View>
                  </View>
                ))}
            </View>
          )}

          {/* CTA */}
          <TouchableOpacity style={styles.startButton} onPress={handleStart}>
            <MaterialCommunityIcons
              name="navigation"
              size={22}
              color={colors.background}
              style={{ marginRight: spacing.sm }}
            />
            <Text style={styles.startButtonText}>Start Navigation</Text>
          </TouchableOpacity>

        </ScrollView>
      </RNAnimated.View>
    </View>
  )
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: "transparent",
  },
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "rgba(0,0,0,0.5)",
  },
  sheet: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: colors.surface,
    borderTopLeftRadius: radius.xl,
    borderTopRightRadius: radius.xl,
    maxHeight: "85%",
    borderTopWidth: 1,
    borderColor: colors.border,
  },
  handleRow: {
    alignItems: "center",
    paddingTop: spacing.md,
    paddingBottom: spacing.sm,
  },
  handle: {
    width: 40,
    height: 4,
    borderRadius: radius.full,
    backgroundColor: colors.border,
  },
  content: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.xxl,
  },
  headerRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacing.lg,
    gap: spacing.sm,
  },
  headerTitle: {
    color: colors.textPrimary,
    fontSize: typography.size.lg,
    fontWeight: typography.weight.bold,
    flex: 1,
  },
  section: {
    marginBottom: spacing.lg,
  },
  statsRow: {
    flexDirection: "row",
    gap: spacing.sm,
    marginBottom: spacing.md,
    flexWrap: "wrap",
  },
  statPill: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surfaceElevated,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radius.full,
    borderWidth: 1,
    borderColor: colors.border,
    gap: spacing.xs,
  },
  statIcon: {
    fontSize: typography.size.sm,
  },
  statText: {
    color: colors.textPrimary,
    fontSize: typography.size.sm,
    fontWeight: typography.weight.medium,
  },
  chipsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  speedWarning: {
    flexDirection: "row",
    alignItems: "flex-start",
    backgroundColor: "rgba(245, 166, 35, 0.12)",
    borderRadius: radius.md,
    padding: spacing.md,
    marginBottom: spacing.md,
    borderWidth: 1,
    borderColor: "rgba(245, 166, 35, 0.3)",
  },
  speedWarningText: {
    flex: 1,
    color: colors.caution,
    fontSize: typography.size.sm,
    lineHeight: 18,
  },
  infoRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginBottom: spacing.lg,
  },
  infoText: {
    flex: 1,
    color: colors.textSecondary,
    fontSize: typography.size.sm,
    lineHeight: 18,
  },
  collapseHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderColor: colors.border,
    marginBottom: spacing.sm,
  },
  collapseTitle: {
    color: colors.textPrimary,
    fontSize: typography.size.md,
    fontWeight: typography.weight.semibold,
  },
  zoneItem: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: spacing.sm,
    gap: spacing.md,
  },
  zoneIcon: {
    fontSize: typography.size.xl,
  },
  zoneDetails: {
    flex: 1,
  },
  zoneLabel: {
    color: colors.textPrimary,
    fontSize: typography.size.md,
    fontWeight: typography.weight.medium,
  },
  zoneType: {
    color: colors.textSecondary,
    fontSize: typography.size.sm,
  },
  startButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.primary,
    paddingVertical: spacing.md + 2,
    borderRadius: radius.xl,
    marginTop: spacing.lg,
    marginBottom: spacing.md,
  },
  startButtonText: {
    color: colors.background,
    fontSize: typography.size.lg,
    fontWeight: typography.weight.bold,
  },
  alternativeLink: {
    alignItems: "center",
    paddingVertical: spacing.sm,
  },
  alternativeLinkText: {
    color: colors.textSecondary,
    fontSize: typography.size.md,
    textDecorationLine: "underline",
  },
})
