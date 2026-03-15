/**
 * AlertQueue — renders the in-app notification queue as stacked banners.
 *
 * Shows up to 3 alerts simultaneously. Each banner auto-dismisses after 6s
 * or on tap. New alerts slide in from the top.
 *
 * Placement: render this at the top of the root layout, above the map.
 * It is absolutely positioned so it overlays all screen content.
 */
import React from "react"
import { StyleSheet, View } from "react-native"
import { AlertBanner } from "../AlertBanner"
import {
  useNotificationStore,
  selectQueue,
} from "../../stores/useNotificationStore"

export function AlertQueue() {
  const queue           = useNotificationStore(selectQueue)
  const dismissFromQueue = useNotificationStore((s) => s.dismissFromQueue)

  if (queue.length === 0) return null

  return (
    <View style={styles.container} pointerEvents="box-none">
      {queue.map((notification) => (
        <AlertBanner
          key={notification.id}
          type={notification.type}
          title={notification.title}
          message={notification.body}
          urgency={notification.urgency}
          onDismiss={() => dismissFromQueue(notification.id)}
        />
      ))}
    </View>
  )
}

const styles = StyleSheet.create({
  container: {
    position: "absolute",
    top:      0,
    left:     0,
    right:    0,
    zIndex:   999,
    paddingTop: 52,   // below status bar + safe area
  },
})
