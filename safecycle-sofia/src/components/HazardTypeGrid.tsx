import React, { useCallback, useRef } from "react"
import { Animated, StyleSheet, Text, TouchableOpacity, View } from "react-native"
import { colors, radius, spacing, typography } from "../tokens"
import type { HazardType } from "../types"

interface HazardTypeGridProps {
  selected: HazardType | null
  onSelect: (type: HazardType) => void
}

interface HazardOption {
  type: HazardType
  icon: string
  label: string
}

const HAZARD_OPTIONS: HazardOption[] = [
  { type: "pothole", icon: "🕳", label: "Pothole" },
  { type: "obstacle", icon: "🚧", label: "Obstacle" },
  { type: "dangerous_traffic", icon: "🚗", label: "Dangerous Traffic" },
  { type: "road_closed", icon: "🚫", label: "Road Closed" },
  { type: "wet_surface", icon: "💧", label: "Wet Surface" },
  { type: "other", icon: "❓", label: "Other" },
]

interface CardProps {
  option: HazardOption
  isSelected: boolean
  onPress: (type: HazardType) => void
}

function HazardCard({ option, isSelected, onPress }: CardProps) {
  const scaleAnim = useRef(new Animated.Value(1)).current

  return (
    <Animated.View style={[styles.cardWrapper, { transform: [{ scale: scaleAnim }] }]}>
      <TouchableOpacity
        style={[styles.card, isSelected && styles.cardSelected]}
        onPress={() => onPress(option.type)}
        onPressIn={() => {
          Animated.spring(scaleAnim, { toValue: 0.96, damping: 10, useNativeDriver: true }).start()
        }}
        onPressOut={() => {
          Animated.spring(scaleAnim, { toValue: 1, damping: 10, useNativeDriver: true }).start()
        }}
        activeOpacity={1}
      >
        <Text style={styles.cardIcon}>{option.icon}</Text>
        <Text style={[styles.cardLabel, isSelected && styles.cardLabelSelected]}>
          {option.label}
        </Text>
      </TouchableOpacity>
    </Animated.View>
  )
}

export function HazardTypeGrid({ selected, onSelect }: HazardTypeGridProps) {
  const handleSelect = useCallback(
    (type: HazardType) => onSelect(type),
    [onSelect]
  )

  return (
    <View style={styles.grid}>
      {HAZARD_OPTIONS.map((option) => (
        <HazardCard
          key={option.type}
          option={option}
          isSelected={selected === option.type}
          onPress={handleSelect}
        />
      ))}
    </View>
  )
}

const styles = StyleSheet.create({
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    marginHorizontal: -spacing.xs,
  },
  cardWrapper: {
    width: "33.33%",
    padding: spacing.xs,
  },
  card: {
    backgroundColor: colors.surfaceElevated,
    borderRadius: radius.lg,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.sm,
    alignItems: "center",
    borderWidth: 2,
    borderColor: colors.border,
    minHeight: 90,
    justifyContent: "center",
  },
  cardSelected: {
    borderColor: colors.primary,
    backgroundColor: "rgba(0, 201, 123, 0.12)",
  },
  cardIcon: {
    fontSize: 26,
    marginBottom: spacing.sm,
  },
  cardLabel: {
    color: colors.textSecondary,
    fontSize: typography.size.xs,
    fontWeight: typography.weight.medium,
    textAlign: "center",
  },
  cardLabelSelected: {
    color: colors.primary,
  },
})
