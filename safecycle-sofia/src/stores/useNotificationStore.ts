/**
 * useNotificationStore — Zustand store for notification state and history.
 *
 * Manages:
 * - Active in-app alert queue (shown as AlertBanner overlay)
 * - Notification history (dismissible list in settings/history screen)
 * - Unread badge count
 */
import { create } from "zustand"
import type { NotificationType, NotificationUrgency } from "../notifications/handler"

export interface InAppNotification {
  id:         string
  type:       NotificationType
  urgency:    NotificationUrgency
  title:      string
  body:       string
  data:       Record<string, unknown>
  receivedAt: number   // Date.now() timestamp
  read:       boolean
}

interface NotificationState {
  // Queue of notifications to show as in-app banners (FIFO, max 3)
  queue:   InAppNotification[]
  // Full history (newest first, max 50)
  history: InAppNotification[]

  // Actions
  addNotification:    (n: InAppNotification) => void
  dismissFromQueue:   (id: string) => void
  markAllRead:        () => void
  clearHistory:       () => void

  // Derived
  unreadCount: number
}

const MAX_QUEUE   = 3
const MAX_HISTORY = 50

export const useNotificationStore = create<NotificationState>((set, get) => ({
  queue:       [],
  history:     [],
  unreadCount: 0,

  addNotification: (notification) => {
    set((state) => {
      // Add to front of queue (newest first), cap at MAX_QUEUE
      const newQueue = [notification, ...state.queue].slice(0, MAX_QUEUE)
      // Add to history (newest first), cap at MAX_HISTORY
      const newHistory = [notification, ...state.history].slice(0, MAX_HISTORY)

      return {
        queue:       newQueue,
        history:     newHistory,
        unreadCount: state.unreadCount + 1,
      }
    })
  },

  dismissFromQueue: (id) => {
    set((state) => ({
      queue: state.queue.filter((n) => n.id !== id),
    }))
  },

  markAllRead: () => {
    set((state) => ({
      history:     state.history.map((n) => ({ ...n, read: true })),
      unreadCount: 0,
    }))
  },

  clearHistory: () => {
    set({ history: [], unreadCount: 0 })
  },
}))

// ── Selectors ─────────────────────────────────────────────────────────────────

export const selectNextAlert = (state: NotificationState) =>
  state.queue[0] ?? null

export const selectUnreadCount = (state: NotificationState) =>
  state.unreadCount

export const selectHistory = (state: NotificationState) =>
  state.history

export const selectQueue = (state: NotificationState) =>
  state.queue
