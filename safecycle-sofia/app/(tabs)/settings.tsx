import React from "react"
import {
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TouchableOpacity,
  View,
} from "react-native"
import Slider from "@react-native-community/slider"
import { useSettingsStore } from "../../src/stores/useSettingsStore"
import { useNotificationStore, type InAppNotification } from "../../src/stores/useNotificationStore"
import * as Speech from "expo-speech"
import { colors, radius, spacing, typography } from "../../src/tokens"

const TEST_ALERTS: InAppNotification[] = [
  {
    id:         "test-crossroad",
    type:       "crossroad_dismount",
    urgency:    "high",
    title:      "Intersection ahead",
    body:       "Consider dismounting — intersection 18m ahead",
    data:       { distance_m: 18 },
    receivedAt: Date.now(),
    read:       false,
  },
  {
    id:         "test-hazard",
    type:       "hazard_nearby",
    urgency:    "high",
    title:      "Hazard ahead",
    body:       "Pothole — 22m ahead",
    data:       { hazard_type: "pothole", distance_m: 22 },
    receivedAt: Date.now(),
    read:       false,
  },
  {
    id:         "test-road-closed",
    type:       "road_closed_ahead",
    urgency:    "high",
    title:      "Road closed on your route",
    body:       "Your route has a road closure. Rerouting recommended.",
    data:       {},
    receivedAt: Date.now(),
    read:       false,
  },
  {
    id:         "test-awareness",
    type:       "awareness_zone_enter",
    urgency:    "medium",
    title:      "Awareness zone",
    body:       "Children may be present — playground",
    data:       { zone_type: "playground" },
    receivedAt: Date.now(),
    read:       false,
  },
  {
    id:         "test-lights",
    type:       "lights_on",
    urgency:    "low",
    title:      "Turn on your lights",
    body:       "Sunset at 18:42 — turn on your front and rear lights",
    data:       { sunset_time: "18:42" },
    receivedAt: Date.now(),
    read:       false,
  },
]

function SectionHeader({ title }: { title: string }) {
  return <Text style={styles.sectionHeader}>{title}</Text>
}

function SettingRow({
  label,
  note,
  children,
}: {
  label: string
  note?: string
  children: React.ReactNode
}) {
  return (
    <View style={styles.row}>
      <View style={styles.rowContent}>
        <Text style={styles.rowLabel}>{label}</Text>
        {note ? <Text style={styles.rowNote}>{note}</Text> : null}
      </View>
      {children}
    </View>
  )
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.infoRow}>
      <Text style={styles.infoLabel}>{label}</Text>
      <Text style={styles.infoValue}>{value}</Text>
    </View>
  )
}

export default function SettingsScreen() {
  const { addNotification } = useNotificationStore()

  function fireTest(alert: InAppNotification) {
    addNotification({ ...alert, id: `${alert.id}-${Date.now()}`, receivedAt: Date.now() })
  }

  function fireVoiceTest() {
    Speech.speak(
      "Залезът в София е в 18 часа и 42 минути. Включете предната и задната светлина на колелото.",
      { language: "bg-BG", rate: 0.9 }
    )
  }

  const {
    maxSpeedLimit,
    preferBikePaths,
    avoidCobblestone,
    crossroadAlertsEnabled,
    awarenessZoneAlertsEnabled,
    hazardAlertsEnabled,
    setMaxSpeedLimit,
    setPreferBikePaths,
    setAvoidCobblestone,
    setCrossroadAlertsEnabled,
    setAwarenessZoneAlertsEnabled,
    setHazardAlertsEnabled,
  } = useSettingsStore()

  return (
    <ScrollView
      style={styles.root}
      contentContainerStyle={styles.scroll}
      showsVerticalScrollIndicator={false}
    >
      <Text style={styles.screenTitle}>Settings</Text>

      {/* Notifications */}
      <SectionHeader title="Notifications" />
      <View style={styles.card}>
        <SettingRow label="Crossroad dismount alerts">
          <Switch
            value={crossroadAlertsEnabled}
            onValueChange={setCrossroadAlertsEnabled}
            trackColor={{ false: colors.border, true: colors.primary }}
            thumbColor={colors.textPrimary}
          />
        </SettingRow>
        <View style={styles.cardDivider} />
        <SettingRow label="Awareness zone alerts">
          <Switch
            value={awarenessZoneAlertsEnabled}
            onValueChange={setAwarenessZoneAlertsEnabled}
            trackColor={{ false: colors.border, true: colors.primary }}
            thumbColor={colors.textPrimary}
          />
        </SettingRow>
        <View style={styles.cardDivider} />
        <SettingRow label="Hazard nearby alerts">
          <Switch
            value={hazardAlertsEnabled}
            onValueChange={setHazardAlertsEnabled}
            trackColor={{ false: colors.border, true: colors.primary }}
            thumbColor={colors.textPrimary}
          />
        </SettingRow>
      </View>

      {/* Routing preferences */}
      <SectionHeader title="Routing Preferences" />
      <View style={styles.card}>
        <View style={styles.sliderSection}>
          <View style={styles.sliderLabelRow}>
            <Text style={styles.rowLabel}>
              Avoid roads over {maxSpeedLimit} km/h
            </Text>
            <Text style={styles.sliderValue}>{maxSpeedLimit}</Text>
          </View>
          <Slider
            style={styles.slider}
            minimumValue={30}
            maximumValue={70}
            step={5}
            value={maxSpeedLimit}
            onValueChange={setMaxSpeedLimit}
            minimumTrackTintColor={colors.primary}
            maximumTrackTintColor={colors.border}
            thumbTintColor={colors.primary}
          />
          <Text style={styles.rowNote}>
            Roads with no speed data are treated as 50 km/h.
          </Text>
        </View>

        <View style={styles.cardDivider} />
        <SettingRow label="Prefer bike paths">
          <Switch
            value={preferBikePaths}
            onValueChange={setPreferBikePaths}
            trackColor={{ false: colors.border, true: colors.primary }}
            thumbColor={colors.textPrimary}
          />
        </SettingRow>

        <View style={styles.cardDivider} />
        <SettingRow
          label="Avoid cobblestone surfaces"
          note="Surfaces with no data default to asphalt"
        >
          <Switch
            value={avoidCobblestone}
            onValueChange={setAvoidCobblestone}
            trackColor={{ false: colors.border, true: colors.primary }}
            thumbColor={colors.textPrimary}
          />
        </SettingRow>
      </View>

      {/* Test Notifications */}
      <SectionHeader title="Test Notifications" />
      <View style={styles.card}>
        {TEST_ALERTS.map((alert, index) => (
          <React.Fragment key={alert.id}>
            {index > 0 && <View style={styles.cardDivider} />}
            <TouchableOpacity style={styles.testRow} onPress={() => fireTest(alert)}>
              <Text style={styles.testLabel}>{alert.title}</Text>
              <Text style={styles.testArrow}>›</Text>
            </TouchableOpacity>
          </React.Fragment>
        ))}
        <View style={styles.cardDivider} />
        <TouchableOpacity style={styles.testRow} onPress={fireVoiceTest}>
          <Text style={styles.testLabel}>Voice notification (bg-BG TTS)</Text>
          <Text style={styles.testArrow}>›</Text>
        </TouchableOpacity>
      </View>

      {/* App info */}
      <SectionHeader title="App Info" />
      <View style={styles.card}>
        <InfoRow
          label="Data source"
          value="VeloBG (velobg.org) + OpenStreetMap"
        />
        <View style={styles.cardDivider} />
        <InfoRow label="App version" value="1.0.0" />
        <View style={styles.cardDivider} />
        <InfoRow
          label="Missing speed data treatment"
          value="50 km/h (safe default)"
        />
        <View style={styles.cardDivider} />
        <InfoRow
          label="Missing surface data treatment"
          value="Asphalt (neutral)"
        />
      </View>
    </ScrollView>
  )
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: colors.background,
  },
  scroll: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.xl + 20,
    paddingBottom: spacing.xxl,
  },
  screenTitle: {
    color: colors.textPrimary,
    fontSize: typography.size.xxl,
    fontWeight: typography.weight.bold,
    marginBottom: spacing.xl,
  },
  sectionHeader: {
    color: colors.textSecondary,
    fontSize: typography.size.xs,
    fontWeight: typography.weight.semibold,
    textTransform: "uppercase",
    letterSpacing: 0.8,
    marginBottom: spacing.sm,
    marginTop: spacing.lg,
  },
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: "hidden",
  },
  cardDivider: {
    height: 1,
    backgroundColor: colors.border,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    justifyContent: "space-between",
  },
  rowContent: {
    flex: 1,
    marginRight: spacing.md,
  },
  rowLabel: {
    color: colors.textPrimary,
    fontSize: typography.size.md,
    fontWeight: typography.weight.medium,
  },
  rowNote: {
    color: colors.textSecondary,
    fontSize: typography.size.xs,
    marginTop: spacing.xs,
    lineHeight: 16,
  },
  sliderSection: {
    paddingHorizontal: spacing.md,
    paddingTop: spacing.md,
    paddingBottom: spacing.sm,
  },
  sliderLabelRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.sm,
  },
  sliderValue: {
    color: colors.primary,
    fontSize: typography.size.lg,
    fontWeight: typography.weight.bold,
  },
  slider: {
    width: "100%",
    height: 40,
    marginHorizontal: -spacing.sm,
  },
  infoRow: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
  },
  infoLabel: {
    color: colors.textSecondary,
    fontSize: typography.size.sm,
    marginBottom: spacing.xs,
  },
  infoValue: {
    color: colors.textPrimary,
    fontSize: typography.size.md,
    fontWeight: typography.weight.medium,
  },
  testRow: {
    flexDirection: "row" as const,
    alignItems: "center" as const,
    justifyContent: "space-between" as const,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
  },
  testLabel: {
    color: colors.textPrimary,
    fontSize: typography.size.md,
  },
  testArrow: {
    color: colors.textSecondary,
    fontSize: typography.size.lg,
  },
})
