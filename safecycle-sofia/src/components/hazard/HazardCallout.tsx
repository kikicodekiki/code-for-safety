import React, { useEffect, useRef, useState } from "react"
import {
  Animated,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native"
import { Callout } from "react-native-maps"
import { HAZARD_COLOURS, HAZARD_TYPE_DESCRIPTORS } from "../../constants/hazardTypes"
import { SEVERITY_DESCRIPTORS, confidenceLabel } from "../../constants/hazardSeverity"
import { colors, radius, spacing, typography } from "../../tokens"
import type { AggregatedHazardResponse } from "../../types"

interface HazardCalloutProps {
  hazard: AggregatedHazardResponse
  onConfirm?: (id: string, action: "confirm" | "dismiss") => Promise<void>
}

function useRelativeTime(ageHours: number): string {
  const [label, setLabel] = useState(formatAge(ageHours))

  useEffect(() => {
    const interval = setInterval(() => setLabel(formatAge(ageHours)), 60_000)
    return () => clearInterval(interval)
  }, [ageHours])

  return label
}

function formatAge(ageHours: number): string {
  if (ageHours < 1 / 60) return "just now"
  if (ageHours < 1) {
    const mins = Math.round(ageHours * 60)
    return `${mins} minute${mins !== 1 ? "s" : ""} ago`
  }
  const hours = Math.floor(ageHours)
  return `${hours} hour${hours !== 1 ? "s" : ""} ago`
}

export function HazardCallout({ hazard, onConfirm }: HazardCalloutProps) {
  const typeDescriptor = HAZARD_TYPE_DESCRIPTORS[hazard.hazard_type]
  const severityDescriptor = SEVERITY_DESCRIPTORS[hazard.effective_severity]
  const accentColour = HAZARD_COLOURS[hazard.hazard_type]
  const ageLabel = useRelativeTime(hazard.age_hours)

  const [confirmLoading, setConfirmLoading] = useState(false)
  const [confirmDone, setConfirmDone] = useState<"confirm" | "dismiss" | null>(null)

  const confidenceWidth = useRef(new Animated.Value(0)).current

  useEffect(() => {
    Animated.timing(confidenceWidth, {
      toValue: hazard.confidence,
      duration: 600,
      useNativeDriver: false,
    }).start()
  }, [hazard.confidence, confidenceWidth])

  const handleAction = async (action: "confirm" | "dismiss") => {
    if (!onConfirm || confirmDone) return
    setConfirmLoading(true)
    try {
      await onConfirm(hazard.id, action)
      setConfirmDone(action)
    } finally {
      setConfirmLoading(false)
    }
  }

  return (
    <Callout tooltip>
      <View style={styles.container}>
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.icon}>{typeDescriptor.icon}</Text>
          <Text style={styles.typeName}>{typeDescriptor.displayName}</Text>
          <View style={[styles.severityBadge, { backgroundColor: `${severityDescriptor.colour}22` }]}>
            <Text style={[styles.severityBadgeText, { color: severityDescriptor.colour }]}>
              ⚠ {hazard.effective_severity}/10 {severityDescriptor.label}
            </Text>
          </View>
        </View>

        {/* Confidence bar */}
        <View style={styles.confidenceRow}>
          <View style={styles.confidenceBarBg}>
            <Animated.View
              style={[
                styles.confidenceBarFill,
                {
                  backgroundColor: accentColour,
                  width: confidenceWidth.interpolate({
                    inputRange: [0, 1],
                    outputRange: ["0%", "100%"],
                  }),
                },
              ]}
            />
          </View>
          <Text style={styles.confidenceLabel}>
            {hazard.report_count} report{hazard.report_count !== 1 ? "s" : ""} ·{" "}
            {confidenceLabel(hazard.confidence)}
          </Text>
        </View>

        {/* Routing impact */}
        {hazard.routing_excluded ? (
          <View style={[styles.routingChip, styles.routingChipExcluded]}>
            <Text style={styles.routingChipText}>⛔ Edge excluded from routing</Text>
          </View>
        ) : hazard.effective_penalty != null ? (
          <View style={[styles.routingChip, { backgroundColor: colors.surfaceElevated }]}>
            <Text style={[styles.routingChipText, { color: colors.textSecondary }]}>
              −{hazard.effective_penalty.toFixed(1)} routing weight
            </Text>
          </View>
        ) : null}

        {/* Description */}
        {hazard.description ? (
          <Text style={styles.description} numberOfLines={3}>
            {hazard.description}
          </Text>
        ) : null}

        {/* Age */}
        <Text style={styles.age}>Reported {ageLabel}</Text>

        {/* Actions */}
        {onConfirm && (
          <View style={styles.actions}>
            <TouchableOpacity
              style={[
                styles.actionButton,
                styles.confirmButton,
                confirmDone === "confirm" && styles.actionDone,
              ]}
              onPress={() => handleAction("confirm")}
              disabled={confirmLoading || confirmDone !== null}
            >
              <Text style={styles.confirmText}>
                {confirmDone === "confirm" ? "✓ Confirmed" : "✓ I see this too"}
              </Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[
                styles.actionButton,
                styles.dismissButton,
                confirmDone === "dismiss" && styles.actionDone,
              ]}
              onPress={() => handleAction("dismiss")}
              disabled={confirmLoading || confirmDone !== null}
            >
              <Text style={styles.dismissText}>
                {confirmDone === "dismiss" ? "✗ Dismissed" : "✗ No longer there"}
              </Text>
            </TouchableOpacity>
          </View>
        )}
      </View>
    </Callout>
  )
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.surfaceElevated,
    borderRadius: radius.lg,
    padding: spacing.md,
    minWidth: 220,
    maxWidth: 280,
    borderWidth: 1,
    borderColor: colors.border,
    gap: spacing.xs,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    flexWrap: "wrap",
  },
  icon: {
    fontSize: 18,
  },
  typeName: {
    color: colors.textPrimary,
    fontSize: typography.size.md,
    fontWeight: typography.weight.bold,
    flex: 1,
  },
  severityBadge: {
    borderRadius: radius.sm,
    paddingHorizontal: spacing.xs,
    paddingVertical: 2,
  },
  severityBadgeText: {
    fontSize: typography.size.xs,
    fontWeight: typography.weight.semibold,
  },
  confidenceRow: {
    gap: 4,
    marginTop: 2,
  },
  confidenceBarBg: {
    height: 3,
    backgroundColor: colors.border,
    borderRadius: 2,
    overflow: "hidden",
  },
  confidenceBarFill: {
    height: 3,
    borderRadius: 2,
  },
  confidenceLabel: {
    color: colors.textDisabled,
    fontSize: typography.size.xs,
  },
  routingChip: {
    borderRadius: radius.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
    alignSelf: "flex-start",
  },
  routingChipExcluded: {
    backgroundColor: "#3C1A1A",
  },
  routingChipText: {
    color: colors.danger,
    fontSize: typography.size.xs,
    fontWeight: typography.weight.semibold,
  },
  description: {
    color: colors.textSecondary,
    fontSize: typography.size.sm,
    lineHeight: 18,
  },
  age: {
    color: colors.textDisabled,
    fontSize: typography.size.xs,
    marginTop: 2,
  },
  actions: {
    flexDirection: "row",
    gap: spacing.xs,
    marginTop: spacing.xs,
  },
  actionButton: {
    flex: 1,
    paddingVertical: spacing.xs,
    borderRadius: radius.md,
    alignItems: "center",
  },
  confirmButton: {
    backgroundColor: "rgba(0,201,123,0.15)",
  },
  dismissButton: {
    backgroundColor: colors.surface,
  },
  actionDone: {
    opacity: 0.5,
  },
  confirmText: {
    color: colors.primary,
    fontSize: typography.size.xs,
    fontWeight: typography.weight.semibold,
  },
  dismissText: {
    color: colors.textSecondary,
    fontSize: typography.size.xs,
  },
})
