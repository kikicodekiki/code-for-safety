import React from "react"
import { Circle } from "react-native-maps"
import { colors } from "../tokens"
import type { Coordinate } from "../types"

interface AwarenessZoneCircleProps {
  center: Coordinate
  radius?: number
}

export const AwarenessZoneCircle = React.memo(function AwarenessZoneCircle({
  center,
  radius = 30,
}: AwarenessZoneCircleProps) {
  return (
    <Circle
      center={{ latitude: center.lat, longitude: center.lon }}
      radius={radius}
      fillColor={colors.awarenessZoneAlpha}
      strokeColor={colors.awarenessZone}
      strokeWidth={1.5}
    />
  )
})
