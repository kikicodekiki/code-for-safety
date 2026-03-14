import React from "react"
import { StyleSheet, Text, View } from "react-native"
import { HAZARD_COLOURS } from "../../constants/hazardTypes"
import { typography } from "../../tokens"
import type { HazardType, SeverityLevel } from "../../types"

interface HazardClusterPinProps {
  count: number
  dominantType: HazardType
  maxSeverity: SeverityLevel
}

export function HazardClusterPin({ count, dominantType, maxSeverity }: HazardClusterPinProps) {
  const size = Math.min(44 + count * 2, 64)
  const accentColour = HAZARD_COLOURS[dominantType]
  const fillOpacity = 0.5 + (maxSeverity / 10) * 0.4

  return (
    <View style={[styles.container, { width: size, height: size }]}>
      {/* Outer ring */}
      <View
        style={[
          styles.outerRing,
          {
            width: size,
            height: size,
            borderRadius: size / 2,
            borderColor: accentColour,
          },
        ]}
      />
      {/* Filled centre */}
      <View
        style={[
          styles.inner,
          {
            width: size - 8,
            height: size - 8,
            borderRadius: (size - 8) / 2,
            backgroundColor: accentColour,
            opacity: fillOpacity,
          },
        ]}
      />
      {/* Labels */}
      <View style={StyleSheet.absoluteFill} pointerEvents="none">
        <View style={styles.labelWrap}>
          <Text style={[styles.countText, { fontSize: count > 9 ? 13 : 16 }]}>{count}</Text>
          <Text style={styles.subLabel}>hazards</Text>
        </View>
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  container: {
    justifyContent: "center",
    alignItems: "center",
  },
  outerRing: {
    position: "absolute",
    borderWidth: 2,
  },
  inner: {
    position: "absolute",
  },
  labelWrap: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  countText: {
    color: "#FFFFFF",
    fontWeight: typography.weight.black,
    lineHeight: 18,
  },
  subLabel: {
    color: "#FFFFFF",
    fontSize: 9,
    fontWeight: typography.weight.semibold,
    opacity: 0.9,
  },
})
