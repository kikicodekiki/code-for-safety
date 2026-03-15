/**
 * hooks/useVoiceNotifications.ts
 *
 * Connects to the backend GPS WebSocket, receives NotificationEvent objects,
 * and speaks the voice_text field aloud using expo-speech.
 *
 * Also handles in-app visual toasts for each notification type.
 *
 * Install:
 *   npx expo install expo-speech
 *
 * Usage:
 *   const { events, connected } = useVoiceNotifications({
 *     userId: "user-123",
 *     fcmToken: expoPushToken,
 *     routeId: activeRouteId,
 *   });
 */

import { useEffect, useRef, useCallback, useState } from "react";
import * as Speech from "expo-speech";

// ---------------------------------------------------------------------------
// Types (mirror the backend NotificationEvent Pydantic model)
// ---------------------------------------------------------------------------

export type NotificationType =
  | "dismount"
  | "awareness_zone"
  | "hazard_nearby"
  | "lights_on";

export interface NotificationEvent {
  event_id:          string;
  notification_type: NotificationType;
  title:             string;
  body:              string;
  voice_text:        string;   // ← spoken by expo-speech
  payload:           Record<string, unknown>;
  ts:                string;
}

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const WS_BASE_URL = process.env.EXPO_PUBLIC_WS_URL ?? "ws://localhost:8000";

/** expo-speech language — Bulgarian */
const SPEECH_LANGUAGE = "bg-BG";

/**
 * Notification type → speech rate override.
 * Dismount and hazard warnings are slightly faster (more urgent).
 */
const SPEECH_RATE: Record<NotificationType, number> = {
  dismount:       1.1,
  awareness_zone: 0.95,
  hazard_nearby:  1.1,
  lights_on:      0.9,
};

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

interface Options {
  userId:    string;
  fcmToken?: string | null;
  routeId?:  string | null;
  lat?:      number;
  lon?:      number;
  speedKmh?: number;
  /** Called with each new event so the UI can render toasts / map pins */
  onEvent?:  (event: NotificationEvent) => void;
}

export function useVoiceNotifications({
  userId,
  fcmToken,
  routeId,
  lat,
  lon,
  speedKmh,
  onEvent,
}: Options) {
  const wsRef         = useRef<WebSocket | null>(null);
  const isSpeaking    = useRef(false);
  const speechQueue   = useRef<NotificationEvent[]>([]);
  const [connected, setConnected]   = useState(false);
  const [events, setEvents]         = useState<NotificationEvent[]>([]);

  // -------------------------------------------------------------------------
  // Speech queue — prevents overlapping announcements
  // -------------------------------------------------------------------------

  const drainQueue = useCallback(async () => {
    if (isSpeaking.current || speechQueue.current.length === 0) return;

    const next = speechQueue.current.shift()!;
    isSpeaking.current = true;

    // Stop any in-progress speech first
    await Speech.stop();

    Speech.speak(next.voice_text || next.body, {
      language: SPEECH_LANGUAGE,
      rate:     SPEECH_RATE[next.notification_type] ?? 1.0,
      onDone:   () => { isSpeaking.current = false; drainQueue(); },
      onError:  () => { isSpeaking.current = false; drainQueue(); },
    });
  }, []);

  const enqueueEvent = useCallback(
    (event: NotificationEvent) => {
      speechQueue.current.push(event);
      drainQueue();
    },
    [drainQueue]
  );

  // -------------------------------------------------------------------------
  // WebSocket connection
  // -------------------------------------------------------------------------

  useEffect(() => {
    if (!userId) return;

    const url = `${WS_BASE_URL}/notifications/ws/gps/${encodeURIComponent(userId)}`;
    const ws  = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
    };

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);

        // Connection ACK — not a notification
        if (data.status === "connected") return;

        // Error frame
        if (data.status === "error") {
          console.warn("[SafeCycle WS]", data.detail);
          return;
        }

        const event = data as NotificationEvent;
        setEvents((prev) => [event, ...prev].slice(0, 50)); // keep last 50
        onEvent?.(event);
        enqueueEvent(event);
      } catch (err) {
        console.error("[SafeCycle WS] parse error:", err);
      }
    };

    ws.onerror = (err) => {
      console.error("[SafeCycle WS] error:", err);
    };

    ws.onclose = () => {
      setConnected(false);
    };

    return () => {
      ws.close();
      Speech.stop();
    };
  }, [userId]);  // reconnect only when userId changes

  // -------------------------------------------------------------------------
  // GPS frame sender — called by the parent component on position update
  // -------------------------------------------------------------------------

  const sendGPSFrame = useCallback(
    (position: { lat: number; lon: number; speedKmh?: number; accuracyM?: number; bearingDeg?: number }) => {
      if (wsRef.current?.readyState !== WebSocket.OPEN) return;

      const frame = {
        lat:          position.lat,
        lon:          position.lon,
        speed_kmh:    position.speedKmh ?? 0,
        accuracy_m:   position.accuracyM ?? 10,
        bearing_deg:  position.bearingDeg ?? null,
        route_id:     routeId ?? null,
        fcm_token:    fcmToken ?? null,
        ts:           new Date().toISOString(),
      };

      wsRef.current.send(JSON.stringify(frame));
    },
    [routeId, fcmToken]
  );

  return { connected, events, sendGPSFrame };
}