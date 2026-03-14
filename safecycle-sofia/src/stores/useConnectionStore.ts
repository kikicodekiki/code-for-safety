import { create } from "zustand"
import type { ConnectionStatus } from "../types"

interface ConnectionState {
  status: ConnectionStatus
  setStatus: (status: ConnectionStatus) => void
}

export const useConnectionStore = create<ConnectionState>((set) => ({
  status: "disconnected",
  setStatus: (status) => set({ status }),
}))
