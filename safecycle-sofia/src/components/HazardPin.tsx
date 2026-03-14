import React, { useEffect, useRef } from "react"
import { Animated, StyleSheet, Text, View } from "react-native"
import { Callout, Marker } from "react-native-maps"
import { colors, radius, spacing, typography } from "../tokens"
import type { Hazard, HazardType } from "../types"

interface HazardPinProps {
  hazard: Hazard
}

const HAZARD_COLORS: Record<HazardType, string> = {
  pothole: colors.hazardPothole,
  obstacle: colors.hazardObstacle,
  dangerous_traffic: colors.hazardTraffic,
  road_closed: colors.hazardClosed,
  wet_surface: colors.hazardWet,
  other: colors.hazardOther,
}

const HAZARD_ICONS: Record<HazardType, string> = {
  pothole: "🕳",
  obstacle: "🚧",
  dangerous_traffic: "🚗",
  road_closed: "🚫",
  wet_surface: "💧",
  other: "❓",
}

const HAZARD_LABELS: Record<HazardType, string> = {
  pothole: "Pothole",
  obstacle: "Obstacle",
  dangerous_traffic: "Dangerous Traffic",
  road_closed: "Road Closed",
  wet_surface: "Wet Surface",
  other: "Other",
}

function formatTimeAgo(ageHours: number): string {
  if (ageHours < 1) {
    const minutes = Math.round(ageHours * 60)
    return `${minutes} minute${minutes !== 1 ? "s" : ""} ago`
  }
  const hours = Math.floor(ageHours)
  return `${hours} hour${hours !== 1 ? "s" : ""} ago`
}

function HazardPinInner({ hazard }: HazardPinProps) {
  const pinColor = HAZARD_COLORS[hazard.type]
  const isRecent = hazard.age_hours < 1
  const isExpired = hazard.age_hours >= 10

  const ringAnim = useRef(new Animated.Value(1)).current
  const ringOpacity = useRef(new Animated.Value(isRecent ? 1 : 0)).current

  useEffect(() => {
    if (!isRecent) return
    const pulse = Animated.loop(
      Animated.sequence([
        Animated.parallel([
          Animated.timing(ringAnim, { toValue: 1.8, duration: 800, useNativeDriver: true }),
          Animated.timing(ringOpacity, { toValue: 0, duration: 800, useNativeDriver: true }),
        ]),
        Animated.parallel([
          Animated.timing(ringAnim, { toValue: 1, duration: 800, useNativeDriver: true }),
          Animated.timing(ringOpacity, { toValue: 0.8, duration: 800, useNativeDriver: true }),
        ]),
      ])
    )
    pulse.start()
    return () => pulse.stop()
  }, [isRecent, ringAnim, ringOpacity])

  return (
    <Marker
      coordinate={{ latitude: hazard.lat, longitude: hazard.lon }}
      anchor={{ x: 0.5, y: 0.5 }}
      tracksViewChanges={isRecent}
    >
      <View style={styles.wrapper}>
        {isRecent && (
          <Animated.View
            style={[
              styles.pulseRing,
              { borderColor: pinColor },
              { opacity: ringOpacity, transform: [{ scale: ringAnim }] },
            ]}
          />
        )}
        <View
          style={[
            styles.pin,
            { backgroundColor: pinColor, opacity: isExpired ? 0.3 : 1 },
          ]}
        >
          <Text style={styles.pinIcon}>{HAZARD_ICONS[hazard.type]}</Text>
        </View>
      </View>

      <Callout tooltip>
        <View style={styles.callout}>
          <Text style={styles.calloutTitle}>{HAZARD_LABELS[hazard.type]}</Text>
          {hazard.description ? (
            <Text style={styles.calloutDesc}>{hazard.description}</Text>
          ) : null}
          <Text style={styles.calloutTime}>Reported {formatTimeAgo(hazard.age_hours)}</Text>
        </View>
      </Callout>
    </Marker>
  )
}

export const HazardPin = React.memo(HazardPinInner)

const styles = StyleSheet.create({
  wrapper: {
    width: 44,
    height: 44,
    justifyContent: "center",
    alignItems: "center",
  },
  pulseRing: {
    position: "absolute",
    width: 40,
    height: 40,
    borderRadius: 20,
    borderWidth: 2,
  },
  pin: {
    width: 30,
    height: 30,
    borderRadius: 15,
    justifyContent: "center",
    alignItems: "center",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.4,
    shadowRadius: 4,
    elevation: 4,
  },
  pinIcon: {
    fontSize: 14,
  },
  callout: {
    backgroundColor: colors.surfaceElevated,
    borderRadius: radius.md,
    padding: spacing.md,
    minWidth: 160,
    maxWidth: 220,
    borderWidth: 1,
    borderColor: colors.border,
  },
  calloutTitle: {
    color: colors.textPrimary,
    fontSize: typography.size.md,
    fontWeight: typography.weight.bold,
    marginBottom: spacing.xs,
  },
  calloutDesc: {
    color: colors.textSecondary,
    fontSize: typography.size.sm,
    marginBottom: spacing.xs,
  },
  calloutTime: {
    color: colors.textDisabled,
    fontSize: typography.size.xs,
  },
})
