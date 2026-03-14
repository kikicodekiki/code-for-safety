import React, { useEffect, useRef } from "react"
import { Animated, StyleSheet, Text, View } from "react-native"
import { Marker } from "react-native-maps"
import { HAZARD_COLOURS, HAZARD_ICONS } from "../../constants/hazardTypes"
import { colors } from "../../tokens"
import type { AggregatedHazardResponse } from "../../types"
import { HazardCallout } from "./HazardCallout"

interface HazardPinProps {
  hazard: AggregatedHazardResponse
  onConfirm?: (id: string, action: "confirm" | "dismiss") => Promise<void>
}

function HazardPinInner({ hazard, onConfirm }: HazardPinProps) {
  const accentColour = HAZARD_COLOURS[hazard.hazard_type]
  const icon = HAZARD_ICONS[hazard.hazard_type]

  // Pin size scales with severity: severity 1 = 24px, severity 10 = 60px
  const pinDiameter = hazard.effective_severity * 4 + 20

  // Fill opacity scales with severity
  const fillOpacity = 0.18 + hazard.effective_severity * 0.072

  // Border width scales with severity
  const borderWidth = 1 + hazard.effective_severity * 0.3

  // Emoji font size scales with severity
  const iconSize = hazard.effective_severity * 2 + 10

  // Confidence ring radius
  const ringDiameter = pinDiameter * 1.6

  // Pulse animation for fresh reports (age < 15 min)
  const pulseScale = useRef(new Animated.Value(1)).current
  const pulseOpacity = useRef(new Animated.Value(0)).current

  useEffect(() => {
    if (!hazard.is_fresh) return
    const anim = Animated.loop(
      Animated.sequence([
        Animated.parallel([
          Animated.timing(pulseScale, { toValue: 2, duration: 1500, useNativeDriver: true }),
          Animated.timing(pulseOpacity, { toValue: 0.5, duration: 750, useNativeDriver: true }),
        ]),
        Animated.timing(pulseOpacity, { toValue: 0, duration: 750, useNativeDriver: true }),
        Animated.timing(pulseScale, { toValue: 1, duration: 0, useNativeDriver: true }),
      ])
    )
    anim.start()
    return () => anim.stop()
  }, [hazard.is_fresh, pulseScale, pulseOpacity])

  const wrapperSize = ringDiameter + 16

  return (
    <Marker
      coordinate={{ latitude: hazard.lat, longitude: hazard.lon }}
      anchor={{ x: 0.5, y: 0.5 }}
      tracksViewChanges={hazard.is_fresh}
    >
      <View style={[styles.wrapper, { width: wrapperSize, height: wrapperSize }]}>
        {/* Confidence ring */}
        <View
          style={[
            styles.confidenceRing,
            {
              width: ringDiameter,
              height: ringDiameter,
              borderRadius: ringDiameter / 2,
              backgroundColor: accentColour,
              opacity: hazard.confidence * 0.25,
            },
          ]}
        />

        {/* Fresh pulse ring */}
        {hazard.is_fresh && (
          <Animated.View
            style={[
              styles.pulseRing,
              {
                width: pinDiameter,
                height: pinDiameter,
                borderRadius: pinDiameter / 2,
                borderColor: accentColour,
                opacity: pulseOpacity,
                transform: [{ scale: pulseScale }],
              },
            ]}
          />
        )}

        {/* Main pin */}
        <View
          style={[
            styles.pin,
            {
              width: pinDiameter,
              height: pinDiameter,
              borderRadius: pinDiameter / 2,
              backgroundColor: accentColour,
              opacity: fillOpacity,
              borderWidth,
              borderColor: accentColour,
            },
          ]}
        >
          <Text style={{ fontSize: iconSize }}>{icon}</Text>
        </View>

        {/* Report count badge */}
        {hazard.report_count > 1 && (
          <View
            style={[
              styles.badge,
              {
                top: wrapperSize / 2 - pinDiameter / 2,
                right: wrapperSize / 2 - pinDiameter / 2,
              },
            ]}
          >
            <Text style={styles.badgeText}>{hazard.report_count}</Text>
          </View>
        )}
      </View>

      <HazardCallout hazard={hazard} onConfirm={onConfirm} />
    </Marker>
  )
}

export const HazardPin = React.memo(HazardPinInner)

const styles = StyleSheet.create({
  wrapper: {
    justifyContent: "center",
    alignItems: "center",
  },
  confidenceRing: {
    position: "absolute",
  },
  pulseRing: {
    position: "absolute",
    borderWidth: 2,
  },
  pin: {
    position: "absolute",
    justifyContent: "center",
    alignItems: "center",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.5,
    shadowRadius: 4,
    elevation: 5,
  },
  badge: {
    position: "absolute",
    backgroundColor: colors.textPrimary,
    borderRadius: 8,
    minWidth: 16,
    height: 16,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: 3,
  },
  badgeText: {
    color: colors.background,
    fontSize: 10,
    fontWeight: "700",
  },
})
