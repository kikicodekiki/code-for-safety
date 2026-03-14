import { EventEmitter } from "events"
import { apiClient } from "../api/client"
import { useConnectionStore } from "../stores/useConnectionStore"
import type { WSServerEvent } from "../types"

interface GPSPayload {
  lat: number
  lon: number
  heading: number
  speed_kmh: number
}

const BACKOFF_SEQUENCE_MS = [1000, 2000, 4000, 8000, 16000, 30000]

class WebSocketManager extends EventEmitter {
  private socket: WebSocket | null = null
  private retryCount = 0
  private retryTimer: ReturnType<typeof setTimeout> | null = null
  private shouldReconnect = false

  connect(): void {
    if (
      this.socket?.readyState === WebSocket.OPEN ||
      this.socket?.readyState === WebSocket.CONNECTING
    ) {
      return
    }

    this.shouldReconnect = true
    this._open()
  }

  disconnect(): void {
    this.shouldReconnect = false
    this._clearRetry()
    this.socket?.close()
    this.socket = null
    useConnectionStore.getState().setStatus("disconnected")
  }

  send(data: object): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(data))
    }
  }

  sendGPS(payload: GPSPayload): void {
    this.send(payload)
  }

  private _open(): void {
    useConnectionStore.getState().setStatus("connecting")

    try {
      this.socket = new WebSocket(apiClient.getWebSocketUrl())
    } catch {
      this._scheduleReconnect()
      return
    }

    this.socket.onopen = () => {
      this.retryCount = 0
      useConnectionStore.getState().setStatus("connected")
    }

    this.socket.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data as string) as WSServerEvent
        this.emit("event", parsed)
        this.emit(parsed.event, parsed.payload)
      } catch {
        // Malformed message — ignore
      }
    }

    this.socket.onerror = () => {
      useConnectionStore.getState().setStatus("error")
    }

    this.socket.onclose = () => {
      if (this.shouldReconnect) {
        this._scheduleReconnect()
      } else {
        useConnectionStore.getState().setStatus("disconnected")
      }
    }
  }

  private _scheduleReconnect(): void {
    const delayMs =
      BACKOFF_SEQUENCE_MS[Math.min(this.retryCount, BACKOFF_SEQUENCE_MS.length - 1)]
    this.retryCount++
    useConnectionStore.getState().setStatus("disconnected")

    this.retryTimer = setTimeout(() => {
      if (this.shouldReconnect) {
        this._open()
      }
    }, delayMs)
  }

  private _clearRetry(): void {
    if (this.retryTimer !== null) {
      clearTimeout(this.retryTimer)
      this.retryTimer = null
    }
  }
}

export const wsManager = new WebSocketManager()
