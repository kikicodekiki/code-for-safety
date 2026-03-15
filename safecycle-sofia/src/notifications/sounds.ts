/**
 * Sound asset mapping per notification type.
 *
 * On iOS, custom sounds must be bundled in the app and referenced by filename.
 * On Android, sounds are tied to notification channels (defined in setup.ts).
 *
 * SafeCycle uses system sounds for reliability, with type-specific cues
 * achieved via vibration patterns (defined in the Android channel config).
 */
import type { NotificationType } from "./handler"

// Whether each notification type should play a sound
export const SOUND_ENABLED: Record<NotificationType, boolean> = {
  crossroad_dismount:     true,
  awareness_zone_enter:   false,
  hazard_nearby:          true,
  road_closed_ahead:      true,
  route_safety_degraded:  false,
  hazard_confirmed_ahead: false,
}

/**
 * Returns the sound value for expo-notifications content.
 * true  = system default sound
 * false = no sound
 */
export function getSoundForType(type: NotificationType): boolean {
  return SOUND_ENABLED[type] ?? false
}

// Vibration patterns per urgency (milliseconds: [wait, vibrate, pause, vibrate...])
export const VIBRATION_PATTERNS = {
  critical: [0, 200, 100, 200, 100, 200] as number[],
  high:     [0, 200, 100, 200]          as number[],
  medium:   [0, 150]                    as number[],
  low:      []                          as number[],
} as const
