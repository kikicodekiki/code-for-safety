import { create } from "zustand"
import type { ConnectionStatus } from "../types"
import type { ConnectionState } from "../integration/websocket/WebSocketManager"

interface ConnectionStoreState {
  status: ConnectionStatus
  setStatus:  (status: ConnectionStatus) => void
  setWsState: (state: ConnectionState) => void   // maps WS states → ConnectionStatus
}

function toConnectionStatus(state: ConnectionState): ConnectionStatus {
  switch (state) {
    case "connected":    return "connected"
    case "connecting":
    case "reconnecting": return "connecting"
    case "error":        return "error"
    default:             return "disconnected"
  }
}

export const useConnectionStore = create<ConnectionStoreState>((set) => ({
  status: "disconnected",
  setStatus:  (status) => set({ status }),
  setWsState: (state)  => set({ status: toConnectionStatus(state) }),
}))
