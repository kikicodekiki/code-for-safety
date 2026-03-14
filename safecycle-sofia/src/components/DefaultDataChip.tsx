import React, { useState } from "react"
import { Modal, StyleSheet, Text, TouchableOpacity, View } from "react-native"
import { MaterialCommunityIcons } from "@expo/vector-icons"
import { colors, radius, spacing, typography } from "../tokens"

interface DefaultDataChipProps {
  label: string
  tooltip: string
}

export function DefaultDataChip({ label, tooltip }: DefaultDataChipProps) {
  const [tooltipVisible, setTooltipVisible] = useState(false)

  return (
    <>
      <TouchableOpacity
        style={styles.chip}
        onPress={() => setTooltipVisible(true)}
        activeOpacity={0.7}
      >
        <Text style={styles.label}>{label}</Text>
        <MaterialCommunityIcons
          name="information-outline"
          size={14}
          color={colors.defaultDataText}
          style={styles.icon}
        />
      </TouchableOpacity>

      <Modal
        visible={tooltipVisible}
        transparent
        animationType="fade"
        onRequestClose={() => setTooltipVisible(false)}
      >
        <TouchableOpacity
          style={styles.overlay}
          activeOpacity={1}
          onPress={() => setTooltipVisible(false)}
        >
          <View style={styles.tooltipBox}>
            <Text style={styles.tooltipText}>{tooltip}</Text>
            <TouchableOpacity
              style={styles.closeButton}
              onPress={() => setTooltipVisible(false)}
            >
              <Text style={styles.closeText}>Got it</Text>
            </TouchableOpacity>
          </View>
        </TouchableOpacity>
      </Modal>
    </>
  )
}

const styles = StyleSheet.create({
  chip: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.defaultDataChip,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: radius.full,
    alignSelf: "flex-start",
  },
  label: {
    color: colors.defaultDataText,
    fontSize: typography.size.xs,
    fontWeight: typography.weight.medium,
  },
  icon: {
    marginLeft: spacing.xs,
  },
  overlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.6)",
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: spacing.xl,
  },
  tooltipBox: {
    backgroundColor: colors.surfaceElevated,
    borderRadius: radius.lg,
    padding: spacing.lg,
    maxWidth: 320,
    borderWidth: 1,
    borderColor: colors.border,
  },
  tooltipText: {
    color: colors.textPrimary,
    fontSize: typography.size.sm,
    lineHeight: 20,
    marginBottom: spacing.md,
  },
  closeButton: {
    alignSelf: "flex-end",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    backgroundColor: colors.primary,
    borderRadius: radius.md,
  },
  closeText: {
    color: colors.background,
    fontSize: typography.size.sm,
    fontWeight: typography.weight.bold,
  },
})
