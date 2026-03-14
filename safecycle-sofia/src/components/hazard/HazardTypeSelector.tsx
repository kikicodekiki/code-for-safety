import React, { useCallback, useRef } from "react"
import {
  Animated,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
  useWindowDimensions,
} from "react-native"
import { HAZARD_TYPE_DESCRIPTORS, HAZARD_TYPES } from "../../constants/hazardTypes"
import { colors, radius, spacing, typography } from "../../tokens"
import type { HazardType } from "../../types"

interface HazardTypeSelectorProps {
  selected: HazardType | null
  onSelect: (type: HazardType) => void
}

function TypeCard({
  type,
  isSelected,
  isOtherSelected,
  onPress,
  cardWidth,
}: {
  type: HazardType
  isSelected: boolean
  isOtherSelected: boolean
  onPress: (type: HazardType) => void
  cardWidth: number
}) {
  const descriptor = HAZARD_TYPE_DESCRIPTORS[type]
  const scale = useRef(new Animated.Value(1)).current
  const opacity = useRef(new Animated.Value(1)).current

  React.useEffect(() => {
    Animated.timing(opacity, {
      toValue: isOtherSelected && !isSelected ? 0.6 : 1,
      duration: 180,
      useNativeDriver: true,
    }).start()
  }, [isOtherSelected, isSelected, opacity])

  return (
    <Animated.View
      style={[styles.cardWrapper, { width: cardWidth, opacity }]}
    >
      <TouchableOpacity
        style={[
          styles.card,
          isSelected && {
            backgroundColor: `${descriptor.colour}1F`,
            borderColor: descriptor.colour,
            borderLeftWidth: 3,
          },
        ]}
        onPress={() => onPress(type)}
        onPressIn={() =>
          Animated.spring(scale, {
            toValue: 0.96,
            damping: 10,
            useNativeDriver: true,
          }).start()
        }
        onPressOut={() =>
          Animated.spring(scale, {
            toValue: 1,
            damping: 10,
            useNativeDriver: true,
          }).start()
        }
        activeOpacity={1}
        accessibilityRole="button"
        accessibilityLabel={descriptor.displayName}
        accessibilityState={{ selected: isSelected }}
      >
        <Animated.View style={{ transform: [{ scale }], flex: 1 }}>
          <View style={styles.cardTopRow}>
            <Text style={styles.cardIcon}>{descriptor.icon}</Text>
            {isSelected && (
              <Text style={[styles.checkmark, { color: descriptor.colour }]}>✓</Text>
            )}
          </View>
          <View style={styles.cardBottomRow}>
            <Text
              style={[
                styles.cardLabel,
                isSelected && { color: descriptor.colour },
              ]}
              numberOfLines={1}
            >
              {descriptor.displayName}
            </Text>
            {descriptor.descriptionRequired && (
              <Text style={styles.requiredBadge}>desc. required</Text>
            )}
          </View>
        </Animated.View>
      </TouchableOpacity>
    </Animated.View>
  )
}

export function HazardTypeSelector({ selected, onSelect }: HazardTypeSelectorProps) {
  const { width } = useWindowDimensions()
  const cardWidth = (width - 48 - spacing.sm) / 2

  const handleSelect = useCallback((type: HazardType) => onSelect(type), [onSelect])

  return (
    <View style={styles.grid}>
      {HAZARD_TYPES.map((descriptor) => (
        <TypeCard
          key={descriptor.key}
          type={descriptor.key}
          isSelected={selected === descriptor.key}
          isOtherSelected={selected !== null && selected !== descriptor.key}
          onPress={handleSelect}
          cardWidth={cardWidth}
        />
      ))}
    </View>
  )
}

const styles = StyleSheet.create({
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  cardWrapper: {
    height: 88,
  },
  card: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    borderLeftWidth: 1,
    padding: spacing.sm,
    justifyContent: "space-between",
  },
  cardTopRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
  },
  cardBottomRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-end",
  },
  cardIcon: {
    fontSize: 28,
  },
  checkmark: {
    fontSize: typography.size.md,
    fontWeight: typography.weight.bold,
  },
  cardLabel: {
    color: colors.textPrimary,
    fontSize: typography.size.sm,
    fontWeight: typography.weight.bold,
    flex: 1,
  },
  requiredBadge: {
    color: colors.textDisabled,
    fontSize: 10,
    marginLeft: spacing.xs,
  },
})
