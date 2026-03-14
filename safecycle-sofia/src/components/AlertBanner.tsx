import React, { useEffect, useRef } from "react"
import { StyleSheet, Text, TouchableOpacity, View } from "react-native"
import Animated, {
  runOnJS,
  useAnimatedStyle,
  useSharedValue,
  withSpring,
  withTiming,
} from "react-native-reanimated"
import { colors, radius, spacing, typography } from "../tokens"

type BannerType = "crossroad" | "awareness" | "hazard"

interface AlertBannerProps {
  type: BannerType
  message: string
  onDismiss: () => void
}

const BANNER_CONFIG: Record<
  BannerType,
  { background: string; icon: string }
> = {
  crossroad: { background: colors.caution, icon: "" },
  awareness: { background: "#3498DB", icon: "" },
  hazard: { background: colors.danger, icon: "" },
}

const AUTO_DISMISS_MS = 6000

export const AlertBanner = React.memo(function AlertBanner({
  type,
  message,
  onDismiss,
}: AlertBannerProps) {
  const translateY = useSharedValue(-120)
  const opacity = useSharedValue(0)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const { background, icon } = BANNER_CONFIG[type]

  const dismiss = () => {
    opacity.value = withTiming(0, { duration: 300 })
    translateY.value = withTiming(-120, { duration: 300 }, (finished) => {
      if (finished) runOnJS(onDismiss)()
    })
  }

  useEffect(() => {
    translateY.value = withSpring(0, { damping: 16, stiffness: 120 })
    opacity.value = withTiming(1, { duration: 250 })

    timerRef.current = setTimeout(() => {
      dismiss()
    }, AUTO_DISMISS_MS)

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const animatedStyle = useAnimatedStyle(() => ({
    transform: [{ translateY: translateY.value }],
    opacity: opacity.value,
  }))

  return (
    <Animated.View style={[styles.container, { backgroundColor: background }, animatedStyle]}>
      <Text style={styles.icon}>{icon}</Text>
      <Text style={styles.message} numberOfLines={2}>
        {message}
      </Text>
      <TouchableOpacity
        onPress={() => {
          if (timerRef.current) clearTimeout(timerRef.current)
          dismiss()
        }}
        hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
      >
        <Text style={styles.dismiss}>×</Text>
      </TouchableOpacity>
    </Animated.View>
  )
})

const styles = StyleSheet.create({
  container: {
    flexDirection: "row",
    alignItems: "center",
    marginHorizontal: spacing.md,
    marginBottom: spacing.sm,
    padding: spacing.md,
    borderRadius: radius.lg,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
  },
  icon: {
    fontSize: typography.size.lg,
    marginRight: spacing.sm,
  },
  message: {
    flex: 1,
    color: "#FFFFFF",
    fontSize: typography.size.sm,
    fontWeight: typography.weight.semibold,
    lineHeight: 18,
  },
  dismiss: {
    color: "#FFFFFF",
    fontSize: typography.size.xl,
    fontWeight: typography.weight.bold,
    marginLeft: spacing.sm,
    lineHeight: 22,
  },
})