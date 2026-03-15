import React from "react"
import { StyleSheet, View } from "react-native"
import { Marker } from "react-native-maps"
import { MaterialCommunityIcons } from "@expo/vector-icons"
import { colors } from "../tokens"
import type { Coordinate } from "../types"

interface CrossroadMarkerProps {
  coordinate: Coordinate
}

export const CrossroadMarker = React.memo(function CrossroadMarker({
  coordinate,
}: CrossroadMarkerProps) {
  return (
    <Marker
      coordinate={{ latitude: coordinate.lat, longitude: coordinate.lon }}
      anchor={{ x: 0.5, y: 0.5 }}
      tracksViewChanges={false}
    >
      <View style={styles.container}>
        <MaterialCommunityIcons name="alert" size={11} color={colors.crossroadBorder} />
      </View>
    </Marker>
  )
})

const styles = StyleSheet.create({
  container: {
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: colors.crossroadFill,
    borderWidth: 2.5,
    borderColor: colors.crossroadBorder,
    justifyContent: "center",
    alignItems: "center",
  },
})
