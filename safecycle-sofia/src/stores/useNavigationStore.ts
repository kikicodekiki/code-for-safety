import { create } from "zustand"
import type { Coordinate, RouteResponse, ZoneStatus } from "../types"

interface NavigationState {
  origin: Coordinate | null
  destination: Coordinate | null
  route: RouteResponse | null
  isNavigating: boolean
  currentPosition: Coordinate | null
  heading: number
  nearestCrossroadDistance: number | null
  currentZoneStatus: ZoneStatus
  setOrigin: (origin: Coordinate | null) => void
  setDestination: (destination: Coordinate | null) => void
  setRoute: (route: RouteResponse) => void
  clearRoute: () => void
  startNavigation: () => void
  stopNavigation: () => void
  updatePosition: (pos: Coordinate) => void
  setHeading: (heading: number) => void
  setNearestCrossroadDistance: (distance: number | null) => void
  setZoneStatus: (status: ZoneStatus) => void
}

export const useNavigationStore = create<NavigationState>((set) => ({
  origin: null,
  destination: null,
  route: null,
  isNavigating: false,
  currentPosition: null,
  heading: 0,
  nearestCrossroadDistance: null,
  currentZoneStatus: "safe",

  setOrigin: (origin) => set({ origin }),
  setDestination: (destination) => set({ destination }),

  setRoute: (route) => set({ route }),

  clearRoute: () => set({ route: null, isNavigating: false }),

  startNavigation: () => set({ isNavigating: true }),

  stopNavigation: () =>
    set({
      isNavigating: false,
      nearestCrossroadDistance: null,
      currentZoneStatus: "safe",
    }),

  updatePosition: (pos) => set({ currentPosition: pos }),

  setHeading: (heading) => set({ heading }),

  setNearestCrossroadDistance: (distance) =>
    set({ nearestCrossroadDistance: distance }),

  setZoneStatus: (status) => set({ currentZoneStatus: status }),
}))
