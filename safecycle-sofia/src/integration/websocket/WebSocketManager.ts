/**
 * Singleton WebSocket manager for the SafeCycle GPS stream.
 * Replaces src/services/websocket.ts — all imports should use this.
 */
import { integrationConfig } from "../config"
import type { GPSUpdate, WSServerEvent } from "../types/api"

export type ConnectionState =
  | "disconnected"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "error"

type EventHandler<T extends WSServerEvent["event"]> = (
  payload: Extract<WSServerEvent, { event: T }>["payload"],
) => void

type ConnectionStateHandler = (state: ConnectionState) => void

class WebSocketManager {
  private socket:            WebSocket | null = null
  private reconnectAttempts: number = 0
  private reconnectTimer:    ReturnType<typeof setTimeout> | null = null
  private heartbeatTimer:    ReturnType<typeof setInterval> | null = null
  private state:             ConnectionState = "disconnected"
  private shouldBeConnected: boolean = false

  private eventHandlers: {
    crossroad:      Set<EventHandler<"crossroad">>
    awareness_zone: Set<EventHandler<"awareness_zone">>
    hazard_nearby:  Set<EventHandler<"hazard_nearby">>
  } = {
    crossroad:      new Set(),
    awareness_zone: new Set(),
    hazard_nearby:  new Set(),
  }

  private stateHandlers: Set<ConnectionStateHandler> = new Set()

  // ─── Public API ─────────────────────────────────────────────────────────────

  connect(): void {
    this.shouldBeConnected = true
    this.reconnectAttempts = 0
    this._openSocket()
  }

  disconnect(): void {
    this.shouldBeConnected = false
    this._clearTimers()
    if (this.socket) {
      this.socket.close(1000, "Client disconnected")
      this.socket = null
    }
    this._setState("disconnected")
  }

  send(data: GPSUpdate | Record<string, unknown>): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(data))
    }
  }

  /** Convenience alias used by the GPS task. */
  sendGPS(payload: GPSUpdate): void {
    this.send(payload)
  }

  on<T extends WSServerEvent["event"]>(
    event:   T,
    handler: EventHandler<T>,
  ): () => void {
    (this.eventHandlers[event] as Set<EventHandler<T>>).add(handler)
    return () => (this.eventHandlers[event] as Set<EventHandler<T>>).delete(handler)
  }

  /** @deprecated Use on() which returns an unsubscribe function. */
  off<T extends WSServerEvent["event"]>(event: T, handler: EventHandler<T>): void {
    (this.eventHandlers[event] as Set<EventHandler<T>>).delete(handler)
  }

  onConnectionStateChange(handler: ConnectionStateHandler): () => void {
    this.stateHandlers.add(handler)
    return () => this.stateHandlers.delete(handler)
  }

  getConnectionState(): ConnectionState {
    return this.state
  }

  // ─── Private ────────────────────────────────────────────────────────────────

  private _openSocket(): void {
    if (this.socket?.readyState === WebSocket.OPEN) return

    this._setState(this.reconnectAttempts > 0 ? "reconnecting" : "connecting")
    const url = `${integrationConfig.wsBaseUrl}/ws/gps`

    try {
      this.socket = new WebSocket(url)
    } catch {
      this._scheduleReconnect()
      return
    }

    this.socket.onopen = () => {
      this.reconnectAttempts = 0
      this._setState("connected")
      this._startHeartbeat()
      if (integrationConfig.isDevelopment) console.log("[WS] Connected:", url)
    }

    this.socket.onmessage = (event: MessageEvent) => {
      this._handleMessage(event.data as string)
    }

    this.socket.onerror = () => {
      this._setState("error")
    }

    this.socket.onclose = (event: CloseEvent) => {
      this._clearHeartbeat()
      if (this.shouldBeConnected && event.code !== 1000) {
        this._scheduleReconnect()
      } else {
        this._setState("disconnected")
      }
    }
  }

  private _handleMessage(raw: string): void {
    let parsed: WSServerEvent
    try {
      parsed = JSON.parse(raw) as WSServerEvent
    } catch {
      return
    }
    const handlers = this.eventHandlers[parsed.event]
    if (handlers) {
      handlers.forEach((h) => h(parsed.payload as never))
    }
  }

  private _scheduleReconnect(): void {
    this.reconnectAttempts++
    const jitter = Math.random() * 500
    const delay  = Math.min(
      integrationConfig.wsReconnectBaseMs * 2 ** (this.reconnectAttempts - 1) + jitter,
      integrationConfig.wsReconnectMaxMs,
    )
    this._setState("reconnecting")
    this.reconnectTimer = setTimeout(() => this._openSocket(), delay)
  }

  private _startHeartbeat(): void {
    this.heartbeatTimer = setInterval(() => {
      if (this.socket?.readyState === WebSocket.OPEN) {
        this.socket.send(JSON.stringify({ type: "ping" }))
      }
    }, integrationConfig.wsHeartbeatMs)
  }

  private _clearHeartbeat(): void {
    if (this.heartbeatTimer) { clearInterval(this.heartbeatTimer); this.heartbeatTimer = null }
  }

  private _clearTimers(): void {
    this._clearHeartbeat()
    if (this.reconnectTimer) { clearTimeout(this.reconnectTimer); this.reconnectTimer = null }
  }

  private _setState(state: ConnectionState): void {
    if (this.state === state) return
    this.state = state
    this.stateHandlers.forEach((h) => h(state))
  }
}

export const wsManager = new WebSocketManager()
