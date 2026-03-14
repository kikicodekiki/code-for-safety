import { create } from "zustand"
import type { Coordinate, RouteResponse, ZoneStatus, WSServerEvent } from "../types"
import type { RouteRequest, RouteError } from "../integration/types/api"

interface PendingAlert {
  type:    "crossroad" | "awareness" | "hazard"
  message: string
}

interface NavigationState {
  // Existing fields
  origin:                   Coordinate | null
  destination:              Coordinate | null
  route:                    RouteResponse | null
  isNavigating:             boolean
  currentPosition:          Coordinate | null
  heading:                  number
  nearestCrossroadDistance: number | null
  currentZoneStatus:        ZoneStatus

  // Integration additions
  isLoading:           boolean
  routeError:          RouteError | null
  lastRouteRequest:    RouteRequest | null
  pendingAlert:        PendingAlert | null
  lastCrossroadAlertAt: number | null

  // Existing actions
  setOrigin:                    (origin: Coordinate | null) => void
  setDestination:               (destination: Coordinate | null) => void
  setRoute:                     (route: RouteResponse) => void
  clearRoute:                   () => void
  startNavigation:              () => void
  stopNavigation:               () => void
  updatePosition:               (pos: Coordinate) => void
  setHeading:                   (heading: number) => void
  setNearestCrossroadDistance:  (distance: number | null) => void
  setZoneStatus:                (status: ZoneStatus) => void

  // Integration actions
  setLoading:           (loading: boolean) => void
  setRouteError:        (error: RouteError | null) => void
  setLastRouteRequest:  (request: RouteRequest) => void
  clearPendingAlert:    () => void
  handleServerEvent:    (event: WSServerEvent) => void
}

export const useNavigationStore = create<NavigationState>((set, get) => ({
  origin:                   null,
  destination:              null,
  route:                    null,
  isNavigating:             false,
  currentPosition:          null,
  heading:                  0,
  nearestCrossroadDistance: null,
  currentZoneStatus:        "safe",
  isLoading:                false,
  routeError:               null,
  lastRouteRequest:         null,
  pendingAlert:             null,
  lastCrossroadAlertAt:     null,

  setOrigin:       (origin)      => set({ origin }),
  setDestination:  (destination) => set({ destination }),
  setRoute:        (route)       => set({ route }),
  clearRoute:      ()            => set({ route: null, isNavigating: false }),
  startNavigation: ()            => set({ isNavigating: true }),
  stopNavigation:  ()            => set({ isNavigating: false, nearestCrossroadDistance: null, currentZoneStatus: "safe" }),
  updatePosition:  (pos)         => set({ currentPosition: pos }),
  setHeading:      (heading)     => set({ heading }),
  setNearestCrossroadDistance: (distance) => set({ nearestCrossroadDistance: distance }),
  setZoneStatus:   (status)      => set({ currentZoneStatus: status }),
  setLoading:      (isLoading)   => set({ isLoading }),
  setRouteError:   (routeError)  => set({ routeError }),
  setLastRouteRequest: (request) => set({ lastRouteRequest: request }),
  clearPendingAlert: ()          => set({ pendingAlert: null }),

  handleServerEvent: (event) => {
    const now = Date.now()
    const state = get()

    switch (event.event) {
      case "crossroad": {
        if (state.lastCrossroadAlertAt && now - state.lastCrossroadAlertAt < 30_000) return
        set({
          currentZoneStatus:    "danger",
          lastCrossroadAlertAt: now,
          pendingAlert: {
            type:    "crossroad",
            message: "Approaching intersection — consider dismounting",
          },
        })
        break
      }
      case "awareness_zone": {
        set({
          currentZoneStatus: "caution",
          pendingAlert: {
            type:    "awareness",
            message: `Heightened awareness zone — ${event.payload.zone.name ?? event.payload.zone.type}`,
          },
        })
        break
      }
      case "hazard_nearby": {
        set({
          currentZoneStatus: "danger",
          pendingAlert: {
            type:    "hazard",
            message: `${event.payload.hazard.type_display_name} ${Math.round(event.payload.distance_m)}m ahead`,
          },
        })
        break
      }
    }
  },
}))
