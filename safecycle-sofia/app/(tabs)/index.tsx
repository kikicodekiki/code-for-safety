import React, { useCallback, useEffect, useRef, useState } from "react"
import {
  ActivityIndicator,
  Animated as RNAnimated,
  Keyboard,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native"
import * as Location from "expo-location"
import { MaterialCommunityIcons } from "@expo/vector-icons"
import { router } from "expo-router"
import { useNavigationStore } from "../../src/stores/useNavigationStore"
import { useHazardStore } from "../../src/stores/useHazardStore"
import { useConnectionStore } from "../../src/stores/useConnectionStore"
import { useRoute } from "../../src/integration/hooks/useRoute"
import { MapWebView, type MapHazard } from "../../src/components/MapWebView"
import { AlertBanner } from "../../src/components/AlertBanner"
import { NavigationHUD } from "../../src/components/NavigationHUD"
import { colors, radius, spacing, typography } from "../../src/tokens"
import { bikePathService } from "../../src/integration/services/bikePathService"
import { HAZARD_COLOURS, HAZARD_ICONS, HAZARD_TYPE_DESCRIPTORS } from "../../src/constants/hazardTypes"
import { SEVERITY_DESCRIPTORS } from "../../src/constants/hazardSeverity"
import type { Coordinate, VeloBGPath } from "../../src/integration/types/api"

const SOFIA_CENTER = { lat: 42.6977, lon: 23.3219 }

// Human-readable "reported N ago" label for a hazard's age in hours.
function formatHazardAge(ageHours: number): string {
  if (ageHours < 1 / 60) return "just now"
  if (ageHours < 1) {
    const mins = Math.round(ageHours * 60)
    return `${mins} minute${mins !== 1 ? "s" : ""} ago`
  }
  const hours = Math.floor(ageHours)
  return `${hours} hour${hours !== 1 ? "s" : ""} ago`
}

interface Banner {
  id: string
  type: "crossroad" | "awareness" | "hazard"
  message: string
}

export default function MapScreen() {
  const cardSlide = useRef(new RNAnimated.Value(0)).current

  const [gpsGranted, setGpsGranted] = useState<boolean | null>(null)
  const [destinationText, setDestinationText] = useState("")
  const [isSearchFocused, setIsSearchFocused] = useState(false)
  const [banners, setBanners] = useState<Banner[]>([])
  const [distanceRemainingM, setDistanceRemainingM] = useState(0)
  const [timeRemainingMin, setTimeRemainingMin] = useState(0)
  const [bikePaths, setBikePaths] = useState<VeloBGPath[]>([])

  const route = useNavigationStore((s) => s.route)
  const isNavigating = useNavigationStore((s) => s.isNavigating)
  const currentPosition = useNavigationStore((s) => s.currentPosition)
  const setOrigin = useNavigationStore((s) => s.setOrigin)
  const setDestination = useNavigationStore((s) => s.setDestination)
  const pendingAlert = useNavigationStore((s) => s.pendingAlert)
  const clearPendingAlert = useNavigationStore((s) => s.clearPendingAlert)
  const connectionStatus = useConnectionStore((s) => s.status)
  const fetchHazards = useHazardStore((s) => s.fetchHazards)
  const confirmHazard = useHazardStore((s) => s.confirmHazard)
  const getActiveHazards = useHazardStore((s) => s.getActiveHazards)

  const { findRoute, isLoading: isLoadingRoute, error: routeError } = useRoute()
  const clearRouteError = useNavigationStore((s) => s.setRouteError)

  // Request foreground location permission and capture initial position.
  // Best-effort only — a slow/failed GPS fix (common on first launch,
  // indoors, or under Expo Go) must not crash the screen. The background
  // GPS task (src/tasks/gpsTask.ts) is the real position source once
  // navigation starts; this just seeds the origin for route search.
  useEffect(() => {
    ; (async () => {
      const { status } = await Location.requestForegroundPermissionsAsync()
      setGpsGranted(status === "granted")
      if (status === "granted") {
        try {
          const loc = await Location.getCurrentPositionAsync({
            accuracy: Location.Accuracy.Balanced,
          })
          setOrigin({ lat: loc.coords.latitude, lon: loc.coords.longitude })
        } catch (err) {
          console.warn("[SafeCycle] Initial GPS fix failed, will retry via background task:", err)
        }
      }
    })()
  }, [setOrigin])

  const pushBanner = useCallback((type: Banner["type"], message: string) => {
    const id = `${type}_${Date.now()}`
    setBanners((prev) => {
      // De-duplicate consecutive same-type banners
      if (prev.length > 0 && prev[prev.length - 1].type === type) return prev
      return [...prev, { id, type, message }]
    })
  }, [])

  // Fetch bike paths on mount
  useEffect(() => {
    ; (async () => {
      try {
        const resp = await bikePathService.getBikePaths()
        setBikePaths(resp.paths)
        if (resp.paths.length > 0) {
          pushBanner("awareness", `Loaded ${resp.paths.length} bike infrastructure paths`)
        } else {
          pushBanner("hazard", "No bike paths found in database")
        }
      } catch (err) {
        console.error("Failed to fetch bike paths:", err)
        pushBanner("hazard", "Connection error: Could not load bike infrastructure")
      }
    })()
  }, [pushBanner])

  // Fetch hazards on mount and refresh every 60 s
  useEffect(() => {
    fetchHazards()
    const interval = setInterval(fetchHazards, 60_000)
    return () => clearInterval(interval)
  }, [fetchHazards])

  // Seed HUD values when navigation starts
  useEffect(() => {
    if (route && isNavigating) {
      setDistanceRemainingM(route.distance_m)
      setTimeRemainingMin(route.duration_min)
    }
  }, [route, isNavigating])

  // Keep card stationary — it's near the top so the keyboard never covers it
  useEffect(() => {
    RNAnimated.timing(cardSlide, {
      toValue: 0,
      duration: 280,
      useNativeDriver: true,
    }).start()
  }, [isSearchFocused, cardSlide])

  const dismissBanner = useCallback((id: string) => {
    setBanners((prev) => prev.filter((b) => b.id !== id))
  }, [])

  // Surface pending alerts from the navigation store as banners
  useEffect(() => {
    if (!pendingAlert) return
    pushBanner(pendingAlert.type, pendingAlert.message)
    clearPendingAlert()
  }, [pendingAlert, clearPendingAlert, pushBanner])

  const handleFindRoute = useCallback(async () => {
    if (!destinationText.trim()) return
    Keyboard.dismiss()

    const pos =
      useNavigationStore.getState().currentPosition ??
      useNavigationStore.getState().origin ?? {
        lat: 42.6977,
        lon: 23.3219,
      }

    // Real geocoding using expo-location
    const searchQuery = `${destinationText.trim()}, Sofia, Bulgaria`
    try {
      const geocodeResults = await Location.geocodeAsync(searchQuery)

      if (!geocodeResults || geocodeResults.length === 0) {
        useNavigationStore.getState().setRouteError({
          type: "not_found",
          message: `Could not find "${destinationText}". Try being more specific or adding a street number.`,
          retryable: false
        })
        return
      }

      const bestResult = geocodeResults[0]
      const destCoord: Coordinate = {
        lat: bestResult.latitude,
        lon: bestResult.longitude
      }

      setDestination(destCoord)

      await findRoute({
        origin_lat: pos.lat,
        origin_lon: pos.lon,
        dest_lat: destCoord.lat,
        dest_lon: destCoord.lon,
      })

      if (!useNavigationStore.getState().routeError) {
        router.push("/route-detail")
      }
    } catch (err) {
      console.error("Geocoding failed:", err)
      useNavigationStore.getState().setRouteError({
        type: "unknown",
        message: "Search service is temporarily unavailable. Please try again later.",
        retryable: true
      })
    }
  }, [destinationText, setDestination, findRoute])

  const activeHazards = getActiveHazards()

  // ── Map data (Leaflet uses [lat, lon]) ─────────────────────────────────────
  const routeCoords = route?.path.coordinates.map(
    ([lon, lat]) => [lat, lon] as [number, number],
  )

  const bikePathSegments = bikePaths.flatMap((path) =>
    bikePathService
      .pathToMapCoordinates(path)
      .map((seg) => seg.map((c) => [c.latitude, c.longitude] as [number, number])),
  )

  const mapZones = route?.awareness_zones.map((zone) => ({
    lat: zone.center.lat,
    lon: zone.center.lon,
    radius: zone.radius_m,
  }))

  const mapCrossroads = route?.crossroad_nodes
    .slice(0, 8)
    .map((node) => ({ lat: node.lat, lon: node.lon }))

  const mapHazards: MapHazard[] = activeHazards.map((h) => ({
    id: h.id,
    lat: h.lat,
    lon: h.lon,
    color: HAZARD_COLOURS[h.hazard_type],
    icon: HAZARD_ICONS[h.hazard_type],
    severity: h.effective_severity,
    reportCount: h.report_count,
    title: HAZARD_TYPE_DESCRIPTORS[h.hazard_type].displayName,
    severityLabel: SEVERITY_DESCRIPTORS[h.effective_severity].label,
    description: h.description ?? undefined,
    ageLabel: formatHazardAge(h.age_hours),
    fresh: h.is_fresh,
  }))

  // ── Permission denied ──────────────────────────────────────────────────────
  if (gpsGranted === false) {
    return (
      <View style={styles.centreScreen}>
        <MaterialCommunityIcons
          name="map-marker-off"
          size={64}
          color={colors.danger}
        />
        <Text style={styles.centreTitle}>Location Access Required</Text>
        <Text style={styles.centreBody}>
          SafeCycle needs your location to calculate safe routes and alert you to
          nearby hazards. Without location access the app cannot function.
        </Text>
        <TouchableOpacity
          style={styles.primaryButton}
          onPress={() => Location.requestForegroundPermissionsAsync()}
        >
          <Text style={styles.primaryButtonText}>Grant Location Access</Text>
        </TouchableOpacity>
      </View>
    )
  }

  // ── Waiting for GPS ────────────────────────────────────────────────────────
  if (gpsGranted === null) {
    return (
      <View style={styles.centreScreen}>
        <ActivityIndicator size="large" color={colors.primary} />
        <Text style={styles.centreBody}>Waiting for GPS signal...</Text>
      </View>
    )
  }

  // ── Main map ───────────────────────────────────────────────────────────────
  return (
    <View style={styles.root}>
      <MapWebView
        initialCenter={SOFIA_CENTER}
        routeCoords={routeCoords}
        bikePaths={bikePathSegments}
        zones={mapZones}
        crossroads={mapCrossroads}
        hazards={mapHazards}
        position={currentPosition ? { lat: currentPosition.lat, lon: currentPosition.lon } : null}
        isNavigating={isNavigating}
        onConfirmHazard={confirmHazard}
      />

      {/* Backend error banner */}
      {routeError && (
        <View style={styles.errorBanner}>
          <Text style={styles.errorBannerText}>{routeError.message}</Text>
          <TouchableOpacity onPress={() => clearRouteError(null)}>
            <MaterialCommunityIcons
              name="close"
              size={18}
              color={colors.textPrimary}
            />
          </TouchableOpacity>
        </View>
      )}

      {/* Destination search card */}
      {!isNavigating && (
        <RNAnimated.View
          style={[
            styles.searchCard,
            { transform: [{ translateY: cardSlide }] },
          ]}
        >
          <View style={styles.inputRow}>
            <MaterialCommunityIcons
              name="crosshairs-gps"
              size={18}
              color={colors.primary}
              style={styles.inputIcon}
            />
            <Text style={styles.originText}>My location</Text>
          </View>
          <View style={styles.separator} />
          <View style={styles.inputRow}>
            <MaterialCommunityIcons
              name="map-marker"
              size={18}
              color={colors.danger}
              style={styles.inputIcon}
            />
            <TextInput
              style={styles.input}
              placeholder="Where to?"
              placeholderTextColor={colors.textDisabled}
              value={destinationText}
              onChangeText={setDestinationText}
              onFocus={() => setIsSearchFocused(true)}
              onBlur={() => setIsSearchFocused(false)}
              returnKeyType="search"
              onSubmitEditing={handleFindRoute}
            />
          </View>
          <TouchableOpacity
            style={[
              styles.findRouteButton,
              (!destinationText.trim() || isLoadingRoute) &&
              styles.findRouteButtonDisabled,
            ]}
            onPress={handleFindRoute}
            disabled={!destinationText.trim() || isLoadingRoute}
          >
            {isLoadingRoute ? (
              <ActivityIndicator size="small" color={colors.background} />
            ) : (
              <>
                <MaterialCommunityIcons
                  name="bike-fast"
                  size={18}
                  color={colors.background}
                  style={{ marginRight: spacing.sm }}
                />
                <Text style={styles.findRouteButtonText}>Find Safe Route</Text>
              </>
            )}
          </TouchableOpacity>
        </RNAnimated.View>
      )}

      {/* Alert banners — one at a time, above HUD */}
      <View style={styles.bannerQueue}>
        {banners.slice(-1).map((banner: Banner) => (
          <AlertBanner
            key={banner.id}
            type={banner.type}
            message={banner.message}
            onDismiss={() => dismissBanner(banner.id)}
          />
        ))}
      </View>

      {/* Navigation HUD */}
      {isNavigating && route && (
        <View style={styles.hudContainer}>
          <NavigationHUD
            route={route}
            distanceRemainingM={distanceRemainingM}
            timeRemainingMin={timeRemainingMin}
          />
        </View>
      )}

      {/* Report FAB — visible only during active navigation */}
      {isNavigating && (
        <TouchableOpacity
          style={styles.reportFab}
          onPress={() => router.push("/(tabs)/report")}
        >
          <MaterialCommunityIcons
            name="alert-plus"
            size={26}
            color={colors.background}
          />
        </TouchableOpacity>
      )}
    </View>
  )
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.background,
  },
  centreScreen: {
    flex: 1,
    backgroundColor: colors.background,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: spacing.xl,
    gap: spacing.md,
  },
  centreTitle: {
    color: colors.textPrimary,
    fontSize: typography.size.xl,
    fontWeight: typography.weight.bold,
    textAlign: "center",
    marginTop: spacing.md,
  },
  centreBody: {
    color: colors.textSecondary,
    fontSize: typography.size.md,
    textAlign: "center",
    lineHeight: 22,
  },
  primaryButton: {
    backgroundColor: colors.primary,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.md,
    borderRadius: radius.xl,
    marginTop: spacing.md,
  },
  primaryButtonText: {
    color: colors.background,
    fontSize: typography.size.md,
    fontWeight: typography.weight.bold,
  },
  searchCard: {
    position: "absolute",
    top: 52,
    left: spacing.md,
    right: spacing.md,
    backgroundColor: colors.surface,
    borderRadius: radius.xl,
    padding: spacing.md,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4,
    shadowRadius: 12,
    elevation: 10,
    borderWidth: 1,
    borderColor: colors.border,
  },
  inputRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: spacing.sm,
  },
  inputIcon: {
    marginRight: spacing.sm,
    width: 22,
  },
  originText: {
    color: colors.textSecondary,
    fontSize: typography.size.md,
  },
  input: {
    flex: 1,
    color: colors.textPrimary,
    fontSize: typography.size.md,
    padding: 0,
  },
  separator: {
    height: 1,
    backgroundColor: colors.border,
    marginVertical: spacing.xs,
    marginLeft: 30,
  },
  findRouteButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.primary,
    borderRadius: radius.lg,
    paddingVertical: spacing.md,
    marginTop: spacing.md,
  },
  findRouteButtonDisabled: {
    backgroundColor: colors.textDisabled,
  },
  findRouteButtonText: {
    color: colors.background,
    fontSize: typography.size.md,
    fontWeight: typography.weight.bold,
  },
  bannerQueue: {
    position: "absolute",
    bottom: 160,
    left: 0,
    right: 0,
  },
  hudContainer: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
  },
  reportFab: {
    position: "absolute",
    bottom: 160,
    right: spacing.lg,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.primary,
    justifyContent: "center",
    alignItems: "center",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4,
    shadowRadius: 8,
    elevation: 8,
  },
  connectionBadge: {
    position: "absolute",
    top: 10,
    right: spacing.md,
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.surfaceElevated,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: radius.full,
    borderWidth: 1,
    borderColor: colors.border,
  },
  connectionDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.danger,
    marginRight: spacing.xs,
  },
  connectionText: {
    color: colors.textSecondary,
    fontSize: typography.size.xs,
  },
  errorBanner: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    backgroundColor: colors.danger,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  errorBannerText: {
    flex: 1,
    color: colors.textPrimary,
    fontSize: typography.size.sm,
  },
})
