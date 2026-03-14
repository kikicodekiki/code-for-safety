import React, { useEffect, useRef } from "react"
import { Animated, StyleSheet, Text, View } from "react-native"
import { colors, radius, spacing, typography } from "../tokens"

interface SafetyScoreBarProps {
  score: number // 0.0–1.0
}

function scoreColor(score: number): string {
  if (score < 0.4) return colors.danger
  if (score < 0.7) return colors.caution
  return colors.safe
}

function scoreLabel(score: number): string {
  if (score < 0.4) return "Risky"
  if (score < 0.7) return "Moderate"
  return "Safe"
}

export const SafetyScoreBar = React.memo(function SafetyScoreBar({
  score,
}: SafetyScoreBarProps) {
  const clampedScore = Math.max(0, Math.min(1, score))
  const fillAnim = useRef(new Animated.Value(0)).current

  useEffect(() => {
    Animated.timing(fillAnim, {
      toValue: clampedScore,
      duration: 800,
      useNativeDriver: false,
    }).start()
  }, [clampedScore, fillAnim])

  const widthInterp = fillAnim.interpolate({
    inputRange: [0, 1],
    outputRange: ["0%", "100%"],
  })

  const pct = Math.round(clampedScore * 100)
  const label = scoreLabel(clampedScore)

  return (
    <View style={styles.container}>
      <View style={styles.labelRow}>
        <Text style={styles.labelText}>Safety Score</Text>
        <Text style={[styles.scoreText, { color: scoreColor(clampedScore) }]}>
          {pct}% — {label}
        </Text>
      </View>
      <View style={styles.track}>
        <Animated.View
          style={[
            styles.fill,
            { width: widthInterp, backgroundColor: scoreColor(clampedScore) },
          ]}
        />
      </View>
    </View>
  )
})

const styles = StyleSheet.create({
  container: {
    width: "100%",
  },
  labelRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.sm,
  },
  labelText: {
    color: colors.textSecondary,
    fontSize: typography.size.sm,
    fontWeight: typography.weight.medium,
  },
  scoreText: {
    fontSize: typography.size.sm,
    fontWeight: typography.weight.bold,
  },
  track: {
    height: 10,
    backgroundColor: colors.border,
    borderRadius: radius.full,
    overflow: "hidden",
  },
  fill: {
    height: "100%",
    borderRadius: radius.full,
  },
})
