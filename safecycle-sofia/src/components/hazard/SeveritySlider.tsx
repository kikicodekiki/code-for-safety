import React, { useEffect, useRef } from "react"
import {
  Animated,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
  useWindowDimensions,
} from "react-native"
import { HAZARD_TYPE_DESCRIPTORS } from "../../constants/hazardTypes"
import { SEVERITY_DESCRIPTORS } from "../../constants/hazardSeverity"
import { colors, radius, spacing, typography } from "../../tokens"
import type { HazardType, SeverityLevel } from "../../types"

interface SeveritySliderProps {
  hazardType: HazardType
  value: SeverityLevel
  onChange: (severity: SeverityLevel) => void
}

const LEVELS: SeverityLevel[] = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
const GAP = 5

function SeveritySquare({
  level,
  isSelected,
  colour,
  squareSize,
  onPress,
}: {
  level: SeverityLevel
  isSelected: boolean
  colour: string
  squareSize: number
  onPress: () => void
}) {
  const scale = useRef(new Animated.Value(isSelected ? 1.08 : 1)).current
  const bgOpacity = useRef(new Animated.Value(isSelected ? 1 : 0.15)).current

  useEffect(() => {
    Animated.parallel([
      Animated.spring(scale, {
        toValue: isSelected ? 1.08 : 1,
        damping: 12,
        stiffness: 180,
        useNativeDriver: true,
      }),
      Animated.timing(bgOpacity, {
        toValue: isSelected ? 1 : 0.15,
        duration: 150,
        useNativeDriver: false,
      }),
    ]).start()
  }, [isSelected, scale, bgOpacity])

  return (
    <TouchableOpacity
      onPress={onPress}
      activeOpacity={0.8}
      accessibilityRole="button"
      accessibilityLabel={`Severity ${level}: ${SEVERITY_DESCRIPTORS[level].label} — ${SEVERITY_DESCRIPTORS[level].routingNote}`}
      accessibilityState={{ selected: isSelected }}
    >
      <Animated.View
        style={[
          styles.square,
          {
            width: squareSize,
            height: squareSize,
            borderRadius: radius.sm,
            transform: [{ scale }],
          },
        ]}
      >
        <Animated.View
          style={[
            StyleSheet.absoluteFill,
            {
              borderRadius: radius.sm,
              backgroundColor: colour,
              opacity: bgOpacity,
            },
          ]}
        />
        <Text
          style={[
            styles.squareNumber,
            { color: isSelected ? "#FFFFFF" : colour },
          ]}
        >
          {level}
        </Text>
      </Animated.View>
    </TouchableOpacity>
  )
}

export function SeveritySlider({ hazardType, value, onChange }: SeveritySliderProps) {
  const { width } = useWindowDimensions()
  const containerWidth = width - spacing.lg * 2
  const squareSize = (containerWidth - GAP * (LEVELS.length - 1)) / LEVELS.length

  const descriptor = SEVERITY_DESCRIPTORS[value]
  const typeDescriptor = HAZARD_TYPE_DESCRIPTORS[hazardType]
  const exampleText = descriptor.examplesByType[hazardType]

  const fadeAnim = useRef(new Animated.Value(0)).current
  const slideAnim = useRef(new Animated.Value(8)).current

  useEffect(() => {
    fadeAnim.setValue(0)
    slideAnim.setValue(8)
    Animated.parallel([
      Animated.timing(fadeAnim, { toValue: 1, duration: 200, useNativeDriver: true }),
      Animated.timing(slideAnim, { toValue: 0, duration: 200, useNativeDriver: true }),
    ]).start()
  }, [hazardType, fadeAnim, slideAnim])

  return (
    <Animated.View
      style={[
        styles.container,
        { opacity: fadeAnim, transform: [{ translateY: slideAnim }] },
      ]}
    >
      <Text style={styles.prompt}>{typeDescriptor.severityPrompt}</Text>

      <View style={[styles.row, { gap: GAP }]}>
        {LEVELS.map((level) => (
          <SeveritySquare
            key={level}
            level={level}
            isSelected={value === level}
            colour={SEVERITY_DESCRIPTORS[level].colour}
            squareSize={squareSize}
            onPress={() => onChange(level)}
          />
        ))}
      </View>

      <View style={styles.helpRow}>
        <Text style={[styles.helpLabel, { color: descriptor.colour }]}>
          {descriptor.label}
        </Text>
        <Text style={styles.routingNote}>{descriptor.routingNote}</Text>
      </View>

      <View style={styles.exampleBox}>
        <Text style={styles.exampleText}>{exampleText}</Text>
      </View>
    </Animated.View>
  )
}

const styles = StyleSheet.create({
  container: {
    marginTop: spacing.md,
  },
  prompt: {
    color: colors.textSecondary,
    fontSize: typography.size.sm,
    marginBottom: spacing.sm,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
  },
  square: {
    justifyContent: "center",
    alignItems: "center",
    overflow: "hidden",
  },
  squareNumber: {
    fontSize: typography.size.sm,
    fontWeight: typography.weight.bold,
  },
  helpRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  helpLabel: {
    fontSize: typography.size.sm,
    fontWeight: typography.weight.bold,
  },
  routingNote: {
    flex: 1,
    color: colors.textSecondary,
    fontSize: typography.size.xs,
  },
  exampleBox: {
    backgroundColor: colors.surfaceElevated,
    borderRadius: radius.md,
    padding: spacing.sm,
    marginTop: spacing.xs,
    borderWidth: 1,
    borderColor: colors.border,
  },
  exampleText: {
    color: colors.textSecondary,
    fontSize: typography.size.sm,
    fontStyle: "italic",
    lineHeight: 18,
  },
})
