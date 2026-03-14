import React, { useEffect, useRef, useState } from "react"
import {
  ActivityIndicator,
  Animated,
  KeyboardAvoidingView,
  Modal,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native"
import { MaterialCommunityIcons } from "@expo/vector-icons"
import { HAZARD_TYPE_DESCRIPTORS } from "../../constants/hazardTypes"
import { SEVERITY_DESCRIPTORS } from "../../constants/hazardSeverity"
import { colors, radius, spacing, typography } from "../../tokens"
import type { HazardType, SeverityLevel } from "../../types"
import { HazardTypeSelector } from "./HazardTypeSelector"
import { SeveritySlider } from "./SeveritySlider"

interface HazardFormSheetProps {
  visible: boolean
  onClose: () => void
  onSubmit: (data: {
    type: HazardType
    severity: SeverityLevel
    description?: string
    lat: number
    lon: number
  }) => Promise<void>
  initialLocation?: { lat: number; lon: number }
}

type Stage = 1 | 2 | 3

export function HazardFormSheet({
  visible,
  onClose,
  onSubmit,
  initialLocation,
}: HazardFormSheetProps) {
  const [stage, setStage] = useState<Stage>(1)
  const [selectedType, setSelectedType] = useState<HazardType | null>(null)
  const [severity, setSeverity] = useState<SeverityLevel>(3)
  const [description, setDescription] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [submitted, setSubmitted] = useState(false)

  const slideAnim = useRef(new Animated.Value(300)).current
  const backdropOpacity = useRef(new Animated.Value(0)).current
  const stageSlide = useRef(new Animated.Value(0)).current
  const successScale = useRef(new Animated.Value(0)).current

  // Animate sheet in/out
  useEffect(() => {
    if (visible) {
      Animated.parallel([
        Animated.spring(slideAnim, { toValue: 0, damping: 18, stiffness: 160, useNativeDriver: true }),
        Animated.timing(backdropOpacity, { toValue: 0.6, duration: 250, useNativeDriver: true }),
      ]).start()
    } else {
      Animated.parallel([
        Animated.timing(slideAnim, { toValue: 300, duration: 220, useNativeDriver: true }),
        Animated.timing(backdropOpacity, { toValue: 0, duration: 220, useNativeDriver: true }),
      ]).start(() => {
        resetForm()
      })
    }
  }, [visible])

  function resetForm() {
    setStage(1)
    setSelectedType(null)
    setSeverity(3)
    setDescription("")
    setSubmitError(null)
    setSubmitted(false)
    successScale.setValue(0)
  }

  function handleTypeSelect(type: HazardType) {
    setSelectedType(type)
    const descriptor = HAZARD_TYPE_DESCRIPTORS[type]
    setSeverity(descriptor.defaultSeverity)
    // Small delay so the selection animation finishes before advancing
    setTimeout(() => {
      Animated.timing(stageSlide, { toValue: -30, duration: 150, useNativeDriver: true }).start(
        () => {
          setStage(2)
          stageSlide.setValue(30)
          Animated.timing(stageSlide, { toValue: 0, duration: 200, useNativeDriver: true }).start()
        }
      )
    }, 300)
  }

  function handleBack() {
    Animated.timing(stageSlide, { toValue: 30, duration: 150, useNativeDriver: true }).start(
      () => {
        setStage(1)
        stageSlide.setValue(-30)
        Animated.timing(stageSlide, { toValue: 0, duration: 200, useNativeDriver: true }).start()
      }
    )
  }

  async function handleSubmit() {
    if (!selectedType || !initialLocation) return
    const typeDescriptor = HAZARD_TYPE_DESCRIPTORS[selectedType]
    if (typeDescriptor.descriptionRequired && !description.trim()) {
      setSubmitError("Please add a description for this hazard type.")
      return
    }
    setIsSubmitting(true)
    setSubmitError(null)
    try {
      await onSubmit({
        type: selectedType,
        severity,
        description: description.trim() || undefined,
        lat: initialLocation.lat,
        lon: initialLocation.lon,
      })
      setSubmitted(true)
      Animated.spring(successScale, {
        toValue: 1,
        damping: 8,
        stiffness: 120,
        useNativeDriver: true,
      }).start()
      setTimeout(() => {
        onClose()
      }, 1800)
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Failed to submit. Please try again.")
    } finally {
      setIsSubmitting(false)
    }
  }

  const typeDescriptor = selectedType ? HAZARD_TYPE_DESCRIPTORS[selectedType] : null
  const severityDescriptor = SEVERITY_DESCRIPTORS[severity]
  const canSubmit =
    selectedType !== null &&
    initialLocation != null &&
    (!typeDescriptor?.descriptionRequired || description.trim().length > 0)

  return (
    <Modal
      visible={visible}
      transparent
      animationType="none"
      onRequestClose={onClose}
    >
      <KeyboardAvoidingView
        style={styles.modalRoot}
        behavior={Platform.OS === "ios" ? "padding" : "height"}
      >
        {/* Backdrop */}
        <Animated.View
          style={[styles.backdrop, { opacity: backdropOpacity }]}
          pointerEvents="box-only"
        >
          <TouchableOpacity style={StyleSheet.absoluteFill} onPress={onClose} />
        </Animated.View>

        {/* Sheet */}
        <Animated.View
          style={[styles.sheet, { transform: [{ translateY: slideAnim }] }]}
        >
          <View style={styles.handle} />

          {submitted ? (
            /* Success state */
            <View style={styles.successContainer}>
              <Animated.View
                style={[styles.successCircle, { transform: [{ scale: successScale }] }]}
              >
                <MaterialCommunityIcons name="check" size={40} color={colors.background} />
              </Animated.View>
              <Text style={styles.successTitle}>Hazard Reported!</Text>
              <Text style={styles.successSub}>
                {typeDescriptor?.icon} {typeDescriptor?.displayName} · Severity {severity}/10
              </Text>
              <Text style={styles.successDisclaimer}>
                Thank you for keeping Sofia safe. 🚲
              </Text>
            </View>
          ) : (
            <Animated.View style={{ transform: [{ translateX: stageSlide }] }}>
              <ScrollView
                showsVerticalScrollIndicator={false}
                keyboardShouldPersistTaps="handled"
                contentContainerStyle={styles.scrollContent}
              >
                {/* Stage header */}
                {stage === 1 && (
                  <>
                    <Text style={styles.sheetTitle}>What did you encounter?</Text>
                    <HazardTypeSelector selected={selectedType} onSelect={handleTypeSelect} />
                  </>
                )}

                {stage >= 2 && typeDescriptor && (
                  <>
                    <View style={styles.stageHeader}>
                      <TouchableOpacity onPress={handleBack} style={styles.backButton}>
                        <Text style={styles.backText}>← Back</Text>
                      </TouchableOpacity>
                      <Text style={[styles.stageSubtitle, { color: typeDescriptor.colour }]}>
                        {typeDescriptor.icon} {typeDescriptor.displayName}
                      </Text>
                    </View>

                    <SeveritySlider
                      hazardType={selectedType!}
                      value={severity}
                      onChange={setSeverity}
                    />

                    {/* Description field */}
                    <Text style={styles.sectionLabel}>
                      {typeDescriptor.descriptionRequired ? "Description (required)" : "Details (optional)"}
                    </Text>
                    <TextInput
                      style={[
                        styles.descriptionInput,
                        submitError && typeDescriptor.descriptionRequired && styles.inputError,
                      ]}
                      placeholder={typeDescriptor.descriptionPlaceholder}
                      placeholderTextColor={colors.textDisabled}
                      multiline
                      numberOfLines={3}
                      value={description}
                      onChangeText={(t) => {
                        setDescription(t)
                        if (submitError) setSubmitError(null)
                      }}
                      maxLength={500}
                    />

                    {/* Location */}
                    <Text style={styles.sectionLabel}>Location</Text>
                    <View style={styles.locationRow}>
                      <MaterialCommunityIcons name="map-marker" size={18} color={colors.danger} />
                      <Text style={styles.locationText}>
                        {initialLocation
                          ? `${initialLocation.lat.toFixed(5)}, ${initialLocation.lon.toFixed(5)}`
                          : "Acquiring GPS…"}
                      </Text>
                    </View>

                    {/* Summary card */}
                    <View style={[styles.summaryCard, { borderColor: typeDescriptor.colour + "44" }]}>
                      <Text style={styles.summaryIcon}>{typeDescriptor.icon}</Text>
                      <View style={{ flex: 1 }}>
                        <Text style={styles.summaryType}>{typeDescriptor.displayName}</Text>
                        <Text style={[styles.summarySeverity, { color: severityDescriptor.colour }]}>
                          Severity {severity}/10 — {severityDescriptor.label}
                        </Text>
                        {description.trim() ? (
                          <Text style={styles.summaryDesc} numberOfLines={2}>
                            {description.trim()}
                          </Text>
                        ) : null}
                      </View>
                    </View>

                    {/* Error */}
                    {submitError && (
                      <View style={styles.errorBox}>
                        <MaterialCommunityIcons name="alert-circle" size={16} color={colors.danger} />
                        <Text style={styles.errorText}>{submitError}</Text>
                      </View>
                    )}

                    {/* Submit */}
                    <TouchableOpacity
                      style={[
                        styles.submitButton,
                        { backgroundColor: typeDescriptor.colour },
                        (!canSubmit || isSubmitting) && styles.submitDisabled,
                      ]}
                      onPress={handleSubmit}
                      disabled={!canSubmit || isSubmitting}
                    >
                      {isSubmitting ? (
                        <ActivityIndicator size="small" color="#FFF" />
                      ) : (
                        <Text style={styles.submitText}>Report Hazard</Text>
                      )}
                    </TouchableOpacity>

                    <Text style={styles.disclaimer}>
                      Reports are anonymous and expire automatically. Thank you for keeping Sofia safe. 🚲
                    </Text>
                  </>
                )}
              </ScrollView>
            </Animated.View>
          )}
        </Animated.View>
      </KeyboardAvoidingView>
    </Modal>
  )
}

const styles = StyleSheet.create({
  modalRoot: {
    flex: 1,
    justifyContent: "flex-end",
  },
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "#000",
  },
  sheet: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: radius.xl,
    borderTopRightRadius: radius.xl,
    maxHeight: "88%",
    paddingBottom: Platform.OS === "ios" ? 34 : spacing.lg,
  },
  handle: {
    width: 36,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.border,
    alignSelf: "center",
    marginTop: spacing.sm,
    marginBottom: spacing.xs,
  },
  scrollContent: {
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.xl,
    paddingTop: spacing.xs,
  },
  sheetTitle: {
    color: colors.textPrimary,
    fontSize: typography.size.xl,
    fontWeight: typography.weight.bold,
    marginBottom: spacing.md,
  },
  stageHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: spacing.xs,
  },
  backButton: {
    paddingVertical: spacing.xs,
  },
  backText: {
    color: colors.textSecondary,
    fontSize: typography.size.sm,
  },
  stageSubtitle: {
    fontSize: typography.size.lg,
    fontWeight: typography.weight.bold,
  },
  sectionLabel: {
    color: colors.textSecondary,
    fontSize: typography.size.xs,
    fontWeight: typography.weight.semibold,
    textTransform: "uppercase",
    letterSpacing: 0.8,
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
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
  summaryDesc: {
    color: colors.textSecondary,
    fontSize: typography.size.sm,
    marginTop: 4,
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
  successContainer: {
    alignItems: "center",
    paddingVertical: spacing.xxl,
    paddingHorizontal: spacing.lg,
    gap: spacing.sm,
  },
  successCircle: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: colors.primary,
    justifyContent: "center",
    alignItems: "center",
    marginBottom: spacing.sm,
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
