import React from "react"
import { StyleSheet, Text, View } from "react-native"
import Svg, { Polygon } from "react-native-svg"
import { HAZARD_COLOURS } from "../../constants/hazardTypes"
import { typography } from "../../tokens"
import type { HazardType, SeverityLevel } from "../../types"

interface HazardClusterPinProps {
  count: number
  dominantType: HazardType
  maxSeverity: SeverityLevel
}

function hexagonPoints(cx: number, cy: number, r: number): string {
  return Array.from({ length: 6 }, (_, i) => {
    const angle = (Math.PI / 3) * i - Math.PI / 6
    return `${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`
  }).join(" ")
}

export function HazardClusterPin({ count, dominantType, maxSeverity }: HazardClusterPinProps) {
  const size = Math.min(44 + count * 2, 64)
  const radius = size * 0.45
  const cx = size / 2
  const cy = size / 2
  const accentColour = HAZARD_COLOURS[dominantType]
  const opacity = 0.5 + (maxSeverity / 10) * 0.4

  return (
    <View style={[styles.container, { width: size, height: size + 14 }]}>
      <Svg width={size} height={size}>
        <Polygon
          points={hexagonPoints(cx, cy, radius)}
          fill={accentColour}
          fillOpacity={opacity}
          stroke={accentColour}
          strokeWidth={1.5}
        />
      </Svg>
      <View style={[StyleSheet.absoluteFill, styles.labelContainer, { bottom: 14 }]}>
        <Text style={[styles.countText, { fontSize: count > 9 ? 13 : 16 }]}>{count}</Text>
      </View>
      <Text style={styles.subLabel}>hazards</Text>
    </View>
  )
}

const styles = StyleSheet.create({
  container: {
    alignItems: "center",
  },
  labelContainer: {
    justifyContent: "center",
    alignItems: "center",
  },
  countText: {
    color: "#FFFFFF",
    fontWeight: typography.weight.black,
  },
  subLabel: {
    color: "#FFFFFF",
    fontSize: 9,
    fontWeight: typography.weight.semibold,
    opacity: 0.9,
    marginTop: -2,
  },
})
