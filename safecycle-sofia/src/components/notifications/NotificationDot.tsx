/**
 * NotificationDot — unread count badge for the tab bar or header.
 *
 * Shows a green dot when there are unread notifications,
 * or a numbered badge when the count exceeds 0.
 * Renders nothing when unread count is 0.
 */
import React from "react"
import { StyleSheet, Text, View } from "react-native"
import { colors, typography } from "../../tokens"
import {
  useNotificationStore,
  selectUnreadCount,
} from "../../stores/useNotificationStore"

interface NotificationDotProps {
  /** Override the count (defaults to store unread count) */
  count?: number
}

export function NotificationDot({ count: countProp }: NotificationDotProps) {
  const storeCount = useNotificationStore(selectUnreadCount)
  const count      = countProp ?? storeCount

  if (count === 0) return null

  const label = count > 99 ? "99+" : String(count)

  return (
    <View style={[styles.badge, label.length > 1 && styles.badgeWide]}>
      <Text style={styles.label}>{label}</Text>
    </View>
  )
}

const styles = StyleSheet.create({
  badge: {
    position:        "absolute",
    top:             -4,
    right:           -6,
    minWidth:        16,
    height:          16,
    borderRadius:    8,
    backgroundColor: colors.danger,
    alignItems:      "center",
    justifyContent:  "center",
    paddingHorizontal: 3,
    borderWidth:     1.5,
    borderColor:     colors.background,
  },
  badgeWide: {
    borderRadius: 8,
  },
  label: {
    color:      "#FFFFFF",
    fontSize:   10,
    fontWeight: typography.weight.bold,
    lineHeight: 12,
  },
})
