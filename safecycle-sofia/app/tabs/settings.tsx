import React from "react"
import {
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  View,
} from "react-native"
import Slider from "@react-native-community/slider"
import { useSettingsStore } from "../../src/stores/useSettingsStore"
import { colors, radius, spacing, typography } from "../../src/tokens"

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
})
