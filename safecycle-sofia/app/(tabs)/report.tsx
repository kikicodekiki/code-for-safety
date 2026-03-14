import React, { useEffect, useState } from "react"
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
import { HazardTypeSelector } from "../../src/components/hazard/HazardTypeSelector"
import { SeveritySlider } from "../../src/components/hazard/SeveritySlider"
import { HAZARD_TYPE_DESCRIPTORS } from "../../src/constants/hazardTypes"
import { SEVERITY_DESCRIPTORS } from "../../src/constants/hazardSeverity"
import { colors, radius, spacing, typography } from "../../src/tokens"
import type { HazardType, SeverityLevel } from "../../src/types"

type Stage = 1 | 2

export default function ReportScreen() {
  const [stage, setStage] = useState<Stage>(1)
  const [selectedType, setSelectedType] = useState<HazardType | null>(null)
  const [severity, setSeverity] = useState<SeverityLevel>(3)
  const [description, setDescription] = useState("")
  const [location, setLocation] = useState<{ lat: number; lon: number } | null>(null)
  const [submitted, setSubmitted] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const checkScale = React.useRef(new RNAnimated.Value(0)).current
  const { submitReport, isSubmitting } = useHazardStore()
  const currentPosition = useNavigationStore((s) => s.currentPosition)

  useEffect(() => {
    if (currentPosition) {
      setLocation(currentPosition)
      return
    }
    Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced })
      .then((loc) => setLocation({ lat: loc.coords.latitude, lon: loc.coords.longitude }))
      .catch(() => {})
  }, [currentPosition])

  function handleTypeSelect(type: HazardType) {
    setSelectedType(type)
    setSeverity(HAZARD_TYPE_DESCRIPTORS[type].defaultSeverity)
    setTimeout(() => setStage(2), 300)
  }

  function handleBack() {
    setStage(1)
    setSubmitError(null)
  }

  async function handleSubmit() {
    if (!selectedType || !location) return
    const typeDescriptor = HAZARD_TYPE_DESCRIPTORS[selectedType]
    if (typeDescriptor.descriptionRequired && !description.trim()) {
      setSubmitError("Please add a description for this hazard type.")
      return
    }
    setSubmitError(null)
    try {
      await submitReport({ type: selectedType, severity, description: description.trim() || undefined, lat: location.lat, lon: location.lon })
      setSubmitted(true)
      RNAnimated.spring(checkScale, { toValue: 1, damping: 8, stiffness: 120, useNativeDriver: true }).start()
      setTimeout(() => {
        setSubmitted(false)
        checkScale.setValue(0)
        setStage(1)
        setSelectedType(null)
        setSeverity(3)
        setDescription("")
      }, 2000)
    } catch {
      setSubmitError("Failed to submit. Please try again.")
    }
  }

  const typeDescriptor = selectedType ? HAZARD_TYPE_DESCRIPTORS[selectedType] : null
  const severityDescriptor = SEVERITY_DESCRIPTORS[severity]
  const canSubmit = selectedType !== null && location !== null &&
    (!typeDescriptor?.descriptionRequired || description.trim().length > 0)

  if (submitted) {
    return (
      <View style={styles.successScreen}>
        <RNAnimated.View style={[styles.checkCircle, { transform: [{ scale: checkScale }] }]}>
          <MaterialCommunityIcons name="check" size={48} color={colors.background} />
        </RNAnimated.View>
        <Text style={styles.successTitle}>Hazard Reported!</Text>
        <Text style={styles.successSub}>
          {typeDescriptor?.icon} {typeDescriptor?.displayName} · Severity {severity}/10
        </Text>
        <Text style={styles.successDisclaimer}>Thank you for keeping Sofia safe. 🚲</Text>
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
        {stage === 1 ? (
          <>
            <Text style={styles.screenTitle}>Report a Hazard</Text>
            <Text style={styles.screenSubtitle}>
              Help other cyclists by reporting road hazards near you.
            </Text>
            <Text style={styles.sectionLabel}>What did you encounter?</Text>
            <HazardTypeSelector selected={selectedType} onSelect={handleTypeSelect} />
          </>
        ) : (
          <>
            {/* Stage 2 header */}
            <View style={styles.stageHeader}>
              <TouchableOpacity onPress={handleBack} style={styles.backButton}>
                <Text style={styles.backText}>← Back</Text>
              </TouchableOpacity>
              {typeDescriptor && (
                <Text style={[styles.stageTitle, { color: typeDescriptor.colour }]}>
                  {typeDescriptor.icon} {typeDescriptor.displayName}
                </Text>
              )}
            </View>

            {/* Severity */}
            {selectedType && (
              <SeveritySlider hazardType={selectedType} value={severity} onChange={setSeverity} />
            )}

            {/* Description */}
            <Text style={styles.sectionLabel}>
              {typeDescriptor?.descriptionRequired ? "Description (required)" : "Details (optional)"}
            </Text>
            <TextInput
              style={[styles.descriptionInput, submitError && typeDescriptor?.descriptionRequired && styles.inputError]}
              placeholder={typeDescriptor?.descriptionPlaceholder}
              placeholderTextColor={colors.textDisabled}
              multiline
              numberOfLines={3}
              value={description}
              onChangeText={(t) => { setDescription(t); if (submitError) setSubmitError(null) }}
              maxLength={500}
            />

            {/* Location */}
            <Text style={styles.sectionLabel}>Location</Text>
            <View style={styles.locationRow}>
              <MaterialCommunityIcons name="map-marker" size={16} color={colors.danger} />
              <Text style={styles.locationText}>
                {location ? `${location.lat.toFixed(5)}, ${location.lon.toFixed(5)}` : "Acquiring GPS…"}
              </Text>
            </View>

            {/* Summary */}
            {typeDescriptor && (
              <View style={[styles.summaryCard, { borderColor: typeDescriptor.colour + "44" }]}>
                <Text style={styles.summaryIcon}>{typeDescriptor.icon}</Text>
                <View style={{ flex: 1 }}>
                  <Text style={styles.summaryType}>{typeDescriptor.displayName}</Text>
                  <Text style={[styles.summarySeverity, { color: severityDescriptor.colour }]}>
                    Severity {severity}/10 — {severityDescriptor.label}
                  </Text>
                </View>
              </View>
            )}

            {submitError && (
              <View style={styles.errorBox}>
                <MaterialCommunityIcons name="alert-circle" size={16} color={colors.danger} />
                <Text style={styles.errorText}>{submitError}</Text>
              </View>
            )}

            <TouchableOpacity
              style={[
                styles.submitButton,
                typeDescriptor && { backgroundColor: typeDescriptor.colour },
                (!canSubmit || isSubmitting) && styles.submitDisabled,
              ]}
              onPress={handleSubmit}
              disabled={!canSubmit || isSubmitting}
            >
              {isSubmitting
                ? <ActivityIndicator size="small" color="#FFF" />
                : <Text style={styles.submitText}>Report Hazard</Text>
              }
            </TouchableOpacity>

            <Text style={styles.disclaimer}>
              Reports are anonymous and expire automatically. Thank you for keeping Sofia safe. 🚲
            </Text>
          </>
        )}
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
    marginBottom: spacing.lg,
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
  stageHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingTop: spacing.xl + 20,
    marginBottom: spacing.xs,
  },
  backButton: {
    paddingVertical: spacing.xs,
  },
  backText: {
    color: colors.textSecondary,
    fontSize: typography.size.sm,
  },
  stageTitle: {
    fontSize: typography.size.lg,
    fontWeight: typography.weight.bold,
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
  inputError: {
    borderColor: colors.danger,
  },
  locationRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    backgroundColor: colors.surfaceElevated,
    borderRadius: radius.md,
    padding: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border,
  },
  locationText: {
    color: colors.textPrimary,
    fontSize: typography.size.sm,
    fontFamily: typography.fontFamily.mono,
  },
  summaryCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: colors.surfaceElevated,
    borderRadius: radius.lg,
    padding: spacing.md,
    marginTop: spacing.md,
    borderWidth: 1,
  },
  summaryIcon: {
    fontSize: 32,
  },
  summaryType: {
    color: colors.textPrimary,
    fontSize: typography.size.md,
    fontWeight: typography.weight.bold,
  },
  summarySeverity: {
    fontSize: typography.size.sm,
    fontWeight: typography.weight.semibold,
    marginTop: 2,
  },
  errorBox: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    backgroundColor: colors.dangerLight,
    borderRadius: radius.md,
    padding: spacing.sm,
    marginTop: spacing.sm,
    borderWidth: 1,
    borderColor: colors.danger,
  },
  errorText: {
    color: colors.danger,
    fontSize: typography.size.sm,
    flex: 1,
  },
  submitButton: {
    paddingVertical: spacing.md + 2,
    borderRadius: radius.xl,
    alignItems: "center",
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
  },
  submitDisabled: {
    opacity: 0.45,
  },
  submitText: {
    color: "#FFFFFF",
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
    gap: spacing.sm,
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
  successSub: {
    color: colors.textSecondary,
    fontSize: typography.size.md,
  },
  successDisclaimer: {
    color: colors.textDisabled,
    fontSize: typography.size.sm,
    marginTop: spacing.xs,
  },
})
