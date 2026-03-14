import { create } from "zustand"
import AsyncStorage from "@react-native-async-storage/async-storage"

const STORAGE_KEY = "safecycle_settings"

interface SettingsState {
  maxSpeedLimit: number
  preferBikePaths: boolean
  avoidCobblestone: boolean
  crossroadAlertsEnabled: boolean
  awarenessZoneAlertsEnabled: boolean
  hazardAlertsEnabled: boolean
  hydrated: boolean
  setMaxSpeedLimit: (value: number) => void
  setPreferBikePaths: (value: boolean) => void
  setAvoidCobblestone: (value: boolean) => void
  setCrossroadAlertsEnabled: (value: boolean) => void
  setAwarenessZoneAlertsEnabled: (value: boolean) => void
  setHazardAlertsEnabled: (value: boolean) => void
  hydrate: () => Promise<void>
}

const defaults = {
  maxSpeedLimit: 50,
  preferBikePaths: true,
  avoidCobblestone: false,
  crossroadAlertsEnabled: true,
  awarenessZoneAlertsEnabled: true,
  hazardAlertsEnabled: true,
}

async function persist(patch: Partial<typeof defaults>) {
  try {
    const existing = await AsyncStorage.getItem(STORAGE_KEY)
    const current = existing ? JSON.parse(existing) : {}
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify({ ...current, ...patch }))
  } catch {
    // Non-fatal: settings will reset on next launch
  }
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
  ...defaults,
  hydrated: false,

  hydrate: async () => {
    try {
      const raw = await AsyncStorage.getItem(STORAGE_KEY)
      if (raw) {
        const saved = JSON.parse(raw)
        set({ ...defaults, ...saved, hydrated: true })
      } else {
        set({ hydrated: true })
      }
    } catch {
      set({ hydrated: true })
    }
  },

  setMaxSpeedLimit: (value) => {
    set({ maxSpeedLimit: value })
    persist({ maxSpeedLimit: value })
  },

  setPreferBikePaths: (value) => {
    set({ preferBikePaths: value })
    persist({ preferBikePaths: value })
  },

  setAvoidCobblestone: (value) => {
    set({ avoidCobblestone: value })
    persist({ avoidCobblestone: value })
  },

  setCrossroadAlertsEnabled: (value) => {
    set({ crossroadAlertsEnabled: value })
    persist({ crossroadAlertsEnabled: value })
  },

  setAwarenessZoneAlertsEnabled: (value) => {
    set({ awarenessZoneAlertsEnabled: value })
    persist({ awarenessZoneAlertsEnabled: value })
  },

  setHazardAlertsEnabled: (value) => {
    set({ hazardAlertsEnabled: value })
    persist({ hazardAlertsEnabled: value })
  },
}))
