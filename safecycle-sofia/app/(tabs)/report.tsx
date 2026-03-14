import React, { useEffect, useRef, useState } from "react"
import {
  ActivityIndicator,
  Animated as RNAnimated,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native"
import * as Location from "expo-location"
import { MaterialCommunityIcons } from "@expo/vector-icons"
import { useHazardStore } from "../../src/stores/useHazardStore"
import { useNavigationStore } from "../../src/stores/useNavigationStore"
import { HazardTypeGrid } from "../../src/components/HazardTypeGrid"
import { colors, radius, spacing, typography } from "../../src/tokens"
import type { HazardType } from "../../src/types"


export default function ReportScreen() {
  const [selectedType, setSelectedType] = useState<HazardType | null>(null)
  const [description, setDescription] = useState("")
  const [lat, setLat] = useState<number | null>(null)
  const [lon, setLon] = useState<number | null>(null)
  const [submitted, setSubmitted] = useState(false)
  const checkScale = useRef(new RNAnimated.Value(0)).current

  const { submitReport, isSubmitting, submitError, clearSubmitError } = useHazardStore()
  const currentPosition = useNavigationStore((s) => s.currentPosition)

  useEffect(() => {
    if (currentPosition) {
      setLat(currentPosition.lat)
      setLon(currentPosition.lon)
      return
    }
    Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced })
      .then((loc) => {
        setLat(loc.coords.latitude)
        setLon(loc.coords.longitude)
      })
      .catch(() => {})
  }, [currentPosition])

  const staticMapUrl =
    lat !== null && lon !== null
      ? `https://maps.googleapis.com/maps/api/staticmap?center=${lat},${lon}&zoom=16&size=360x120&markers=color:red%7C${lat},${lon}&style=feature:all%7Celement:geometry%7Csaturation:-60&key=REPLACE_WITH_KEY`
      : null

  const handleSubmit = async () => {
    if (!selectedType || lat === null || lon === null) return
    clearSubmitError()

    try {
      await submitReport({
        lat,
        lon,
        type: selectedType,
        description: description.trim() || undefined,
        timestamp: new Date().toISOString(),
      })

      // Success animation
      setSubmitted(true)
      RNAnimated.spring(checkScale, {
        toValue: 1,
        damping: 8,
        stiffness: 120,
        useNativeDriver: true,
      }).start()

      setTimeout(() => {
        setSubmitted(false)
        checkScale.setValue(0)
        setSelectedType(null)
        setDescription("")
      }, 2000)
    } catch {
      // Error is shown via submitError from store
    }
  }

  if (submitted) {
    return (
      <View style={styles.successScreen}>
        <RNAnimated.View
          style={[
            styles.checkCircle,
            { transform: [{ scale: checkScale }] },
          ]}
        >
          <MaterialCommunityIcons name="check" size={48} color={colors.background} />
        </RNAnimated.View>
        <Text style={styles.successTitle}>Hazard Reported!</Text>
        <Text style={styles.successSubtitle}>
          Thank you for keeping Sofia safe 🚲
        </Text>
      </View>
    )
  }

  return (
    <KeyboardAvoidingView
      style={styles.root}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
    >
      <ScrollView
        contentContainerStyle={styles.scroll}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        <Text style={styles.screenTitle}>Report a Hazard</Text>
        <Text style={styles.screenSubtitle}>
          Help other cyclists by reporting road hazards near you.
        </Text>

        {/* Hazard type selector */}
        <Text style={styles.sectionLabel}>Hazard type</Text>
        <HazardTypeGrid selected={selectedType} onSelect={setSelectedType} />

        {/* Location preview */}
        <Text style={styles.sectionLabel}>Location</Text>
        <View style={styles.locationCard}>
          {lat !== null && lon !== null ? (
            <>
              <View style={styles.locationMapPlaceholder}>
                <MaterialCommunityIcons
                  name="map-marker"
                  size={32}
                  color={colors.danger}
                />
                <Text style={styles.locationCoords}>
                  {lat.toFixed(5)}, {lon.toFixed(5)}
                </Text>
              </View>
              <Text style={styles.locationNote}>Current GPS position</Text>
            </>
          ) : (
            <View style={styles.locationLoading}>
              <ActivityIndicator size="small" color={colors.primary} />
              <Text style={styles.locationNote}>Acquiring GPS location...</Text>
            </View>
          )}
        </View>

        {/* Description */}
        <Text style={styles.sectionLabel}>Details (optional)</Text>
        <TextInput
          style={styles.descriptionInput}
          placeholder="Add details — e.g. 'large pothole near tram tracks'"
          placeholderTextColor={colors.textDisabled}
          multiline
          numberOfLines={3}
          value={description}
          onChangeText={setDescription}
          maxLength={300}
        />

        {/* Error */}
        {submitError && (
          <View style={styles.errorBox}>
            <MaterialCommunityIcons
              name="alert-circle"
              size={18}
              color={colors.danger}
              style={{ marginRight: spacing.sm }}
            />
            <Text style={styles.errorText}>{submitError}</Text>
            <TouchableOpacity onPress={handleSubmit} style={styles.retryButton}>
              <Text style={styles.retryText}>Retry</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Submit */}
        <TouchableOpacity
          style={[
            styles.submitButton,
            (!selectedType || lat === null || isSubmitting) && styles.submitButtonDisabled,
          ]}
          onPress={handleSubmit}
          disabled={!selectedType || lat === null || isSubmitting}
        >
          {isSubmitting ? (
            <ActivityIndicator size="small" color={colors.background} />
          ) : (
            <Text style={styles.submitButtonText}>Report Hazard</Text>
          )}
        </TouchableOpacity>

        <Text style={styles.disclaimer}>
          Reports are visible to all SafeCycle users and expire after 10 hours.
        </Text>
      </ScrollView>
    </KeyboardAvoidingView>
  )
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scroll: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.xl + 20,
    paddingBottom: spacing.xxl,
  },
  screenTitle: {
    color: colors.textPrimary,
    fontSize: typography.size.xxl,
    fontWeight: typography.weight.bold,
    marginBottom: spacing.xs,
  },
  screenSubtitle: {
    color: colors.textSecondary,
    fontSize: typography.size.md,
    marginBottom: spacing.xl,
    lineHeight: 22,
  },
  sectionLabel: {
    color: colors.textSecondary,
    fontSize: typography.size.sm,
    fontWeight: typography.weight.semibold,
    textTransform: "uppercase",
    letterSpacing: 0.8,
    marginBottom: spacing.sm,
    marginTop: spacing.lg,
  },
  locationCard: {
    backgroundColor: colors.surfaceElevated,
    borderRadius: radius.lg,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: colors.border,
    minHeight: 80,
    justifyContent: "center",
  },
  locationMapPlaceholder: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  locationCoords: {
    color: colors.textPrimary,
    fontSize: typography.size.sm,
    fontFamily: typography.fontFamily.mono,
  },
  locationNote: {
    color: colors.textSecondary,
    fontSize: typography.size.xs,
    marginTop: spacing.xs,
  },
  locationLoading: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  descriptionInput: {
    backgroundColor: colors.surfaceElevated,
    borderRadius: radius.lg,
    padding: spacing.md,
    color: colors.textPrimary,
    fontSize: typography.size.md,
    borderWidth: 1,
    borderColor: colors.border,
    minHeight: 90,
    textAlignVertical: "top",
  },
  errorBox: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.dangerLight,
    borderRadius: radius.md,
    padding: spacing.md,
    marginTop: spacing.md,
    borderWidth: 1,
    borderColor: colors.danger,
  },
  errorText: {
    flex: 1,
    color: colors.danger,
    fontSize: typography.size.sm,
  },
  retryButton: {
    marginLeft: spacing.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    backgroundColor: colors.danger,
    borderRadius: radius.sm,
  },
  retryText: {
    color: "#FFFFFF",
    fontSize: typography.size.xs,
    fontWeight: typography.weight.bold,
  },
  submitButton: {
    backgroundColor: colors.primary,
    paddingVertical: spacing.md + 2,
    borderRadius: radius.xl,
    alignItems: "center",
    marginTop: spacing.xl,
    marginBottom: spacing.md,
  },
  submitButtonDisabled: {
    backgroundColor: colors.textDisabled,
  },
  submitButtonText: {
    color: colors.background,
    fontSize: typography.size.lg,
    fontWeight: typography.weight.bold,
  },
  disclaimer: {
    color: colors.textDisabled,
    fontSize: typography.size.xs,
    textAlign: "center",
    lineHeight: 16,
  },
  successScreen: {
    flex: 1,
    backgroundColor: colors.background,
    justifyContent: "center",
    alignItems: "center",
    gap: spacing.md,
  },
  checkCircle: {
    width: 96,
    height: 96,
    borderRadius: 48,
    backgroundColor: colors.primary,
    justifyContent: "center",
    alignItems: "center",
    marginBottom: spacing.md,
  },
  successTitle: {
    color: colors.textPrimary,
    fontSize: typography.size.xxl,
    fontWeight: typography.weight.bold,
  },
  successSubtitle: {
    color: colors.textSecondary,
    fontSize: typography.size.md,
  },
})
