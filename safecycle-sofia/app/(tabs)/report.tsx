import React, { useEffect, useState } from "react"
import { StyleSheet, Text, View } from "react-native"
import * as Location from "expo-location"
import { useHazardStore } from "../../src/stores/useHazardStore"
import { useNavigationStore } from "../../src/stores/useNavigationStore"
import { HazardFormSheet } from "../../src/components/hazard/HazardFormSheet"
import { colors, spacing, typography } from "../../src/tokens"
import type { HazardType, SeverityLevel } from "../../src/types"

export default function ReportScreen() {
  const [location, setLocation] = useState<{ lat: number; lon: number } | null>(null)
  const currentPosition = useNavigationStore((s) => s.currentPosition)
  const { submitReport } = useHazardStore()

  useEffect(() => {
    if (currentPosition) {
      setLocation(currentPosition)
      return
    }
    Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced })
      .then((loc) => setLocation({ lat: loc.coords.latitude, lon: loc.coords.longitude }))
      .catch(() => {})
  }, [currentPosition])

  const handleSubmit = async (data: {
    type: HazardType
    severity: SeverityLevel
    description?: string
    lat: number
    lon: number
  }) => {
    await submitReport(data)
  }

  return (
    <View style={styles.root}>
      <Text style={styles.title}>Report a Hazard</Text>
      <Text style={styles.subtitle}>
        Help other cyclists by reporting road hazards near you.
      </Text>

      <HazardFormSheet
        visible
        onClose={() => {}}
        onSubmit={handleSubmit}
        initialLocation={location ?? undefined}
      />
    </View>
  )
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.background,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.xl + 20,
  },
  title: {
    color: colors.textPrimary,
    fontSize: typography.size.xxl,
    fontWeight: typography.weight.bold,
    marginBottom: spacing.xs,
  },
  subtitle: {
    color: colors.textSecondary,
    fontSize: typography.size.md,
    lineHeight: 22,
  },
})
