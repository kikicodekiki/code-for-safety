/**
 * NotificationHistory — dismissible list of recent alerts.
 *
 * Shows the last 50 notifications received during this session.
 * Displays timestamp, icon, title, and body for each.
 * "Mark all read" clears the unread badge count.
 */
import React, { useCallback } from "react"
import {
  FlatList,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native"
import { colors, radius, spacing, typography } from "../../tokens"
import {
  useNotificationStore,
  selectHistory,
  type InAppNotification,
} from "../../stores/useNotificationStore"

const TYPE_ICON: Record<string, string> = {
  crossroad_dismount:     "⚠️",
  awareness_zone_enter:   "👁",
  hazard_nearby:          "🚨",
  road_closed_ahead:      "🚫",
  route_safety_degraded:  "📉",
  hazard_confirmed_ahead: "⚠️",
}

const URGENCY_COLORS: Record<string, string> = {
  critical: "#C0392B",
  high:     colors.danger,
  medium:   "#3498DB",
  low:      "#7F8C8D",
}

function formatTime(ts: number): string {
  const date = new Date(ts)
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
}

function NotificationRow({ item }: { item: InAppNotification }) {
  const accent = URGENCY_COLORS[item.urgency] ?? colors.danger
  const icon   = TYPE_ICON[item.type] ?? "🔔"

  return (
    <View style={[styles.row, !item.read && styles.rowUnread]}>
      <View style={[styles.accent, { backgroundColor: accent }]} />
      <Text style={styles.rowIcon}>{icon}</Text>
      <View style={styles.rowContent}>
        <Text style={styles.rowTitle} numberOfLines={1}>{item.title}</Text>
        <Text style={styles.rowBody}  numberOfLines={2}>{item.body}</Text>
        <Text style={styles.rowTime}>{formatTime(item.receivedAt)}</Text>
      </View>
      {!item.read && <View style={styles.unreadDot} />}
    </View>
  )
}

export function NotificationHistory() {
  const history     = useNotificationStore(selectHistory)
  const markAllRead = useNotificationStore((s) => s.markAllRead)
  const clearHistory = useNotificationStore((s) => s.clearHistory)

  const renderItem = useCallback(
    ({ item }: { item: InAppNotification }) => <NotificationRow item={item} />,
    []
  )

  const keyExtractor = useCallback((item: InAppNotification) => item.id, [])

  if (history.length === 0) {
    return (
      <View style={styles.empty}>
        <Text style={styles.emptyIcon}>🔔</Text>
        <Text style={styles.emptyText}>No alerts yet this ride</Text>
      </View>
    )
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Alerts</Text>
        <View style={styles.headerActions}>
          <TouchableOpacity onPress={markAllRead} style={styles.headerBtn}>
            <Text style={styles.headerBtnText}>Mark read</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={clearHistory} style={styles.headerBtn}>
            <Text style={styles.headerBtnText}>Clear</Text>
          </TouchableOpacity>
        </View>
      </View>
      <FlatList
        data={history}
        renderItem={renderItem}
        keyExtractor={keyExtractor}
        contentContainerStyle={styles.list}
        showsVerticalScrollIndicator={false}
      />
    </View>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  header: {
    flexDirection:   "row",
    alignItems:      "center",
    justifyContent:  "space-between",
    paddingHorizontal: spacing.md,
    paddingVertical:   spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(255,255,255,0.08)",
  },
  headerTitle: {
    color:      "#FFFFFF",
    fontSize:   typography.size.md,
    fontWeight: typography.weight.bold,
  },
  headerActions: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  headerBtn: {
    paddingHorizontal: spacing.sm,
    paddingVertical:   4,
  },
  headerBtnText: {
    color:    colors.primary,
    fontSize: typography.size.sm,
  },
  list: {
    paddingVertical: spacing.sm,
  },
  row: {
    flexDirection:     "row",
    alignItems:        "center",
    marginHorizontal:  spacing.md,
    marginBottom:      spacing.xs ?? 4,
    padding:           spacing.sm,
    backgroundColor:   "rgba(255,255,255,0.05)",
    borderRadius:      radius.md,
  },
  rowUnread: {
    backgroundColor: "rgba(255,255,255,0.09)",
  },
  accent: {
    width:        3,
    alignSelf:    "stretch",
    borderRadius: 2,
    marginRight:  spacing.sm,
  },
  rowIcon: {
    fontSize:    typography.size.lg,
    marginRight: spacing.sm,
  },
  rowContent: {
    flex: 1,
  },
  rowTitle: {
    color:      "#FFFFFF",
    fontSize:   typography.size.sm,
    fontWeight: typography.weight.semibold,
  },
  rowBody: {
    color:     "rgba(255,255,255,0.6)",
    fontSize:  typography.size.xs ?? 11,
    marginTop: 2,
    lineHeight: 15,
  },
  rowTime: {
    color:     "rgba(255,255,255,0.35)",
    fontSize:  typography.size.xs ?? 11,
    marginTop: 3,
  },
  unreadDot: {
    width:        8,
    height:       8,
    borderRadius: 4,
    backgroundColor: colors.primary,
    marginLeft:   spacing.sm,
  },
  empty: {
    flex:           1,
    alignItems:     "center",
    justifyContent: "center",
    gap:            spacing.sm,
  },
  emptyIcon: {
    fontSize: 32,
    opacity:  0.4,
  },
  emptyText: {
    color:    "rgba(255,255,255,0.4)",
    fontSize: typography.size.sm,
  },
})
