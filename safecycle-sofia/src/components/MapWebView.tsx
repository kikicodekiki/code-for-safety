import React, { useCallback, useMemo, useRef } from "react"
import { StyleSheet } from "react-native"
import { WebView, type WebViewMessageEvent } from "react-native-webview"

/**
 * OpenStreetMap map rendered with Leaflet inside a WebView.
 *
 * This replaces react-native-maps, which on Android always uses the Google
 * Maps engine (and therefore needs a Google Maps API key to render at all).
 * Leaflet + OSM raster tiles need no key, no Google, and run identically in
 * Expo Go and in a standalone build.
 *
 * All overlays (route, bike paths, awareness zones, crossroads, hazards,
 * current position) are drawn inside Leaflet from a single data payload that
 * is (re)injected whenever the props change. Hazard confirm/dismiss taps come
 * back to React Native via postMessage.
 */

export interface MapHazard {
  id: string
  lat: number
  lon: number
  color: string
  icon: string
  severity: number
  reportCount: number
  title: string
  severityLabel: string
  description?: string
  ageLabel: string
  fresh: boolean
}

export interface MapWebViewProps {
  routeCoords?: Array<[number, number]> // [lat, lon]
  bikePaths?: Array<Array<[number, number]>> // segments of [lat, lon]
  zones?: Array<{ lat: number; lon: number; radius: number }>
  crossroads?: Array<{ lat: number; lon: number }>
  hazards?: MapHazard[]
  position?: { lat: number; lon: number } | null
  isNavigating?: boolean
  initialCenter?: { lat: number; lon: number }
  onConfirmHazard?: (id: string, action: "confirm" | "dismiss") => void
}

const DEFAULT_CENTER = { lat: 42.6977, lon: 23.3219 }

// Leaflet is loaded from a CDN. The app already requires network access for
// map tiles and the backend, so this adds no new offline constraint.
function buildHtml(center: { lat: number; lon: number }): string {
  return `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  html, body, #map { height: 100%; margin: 0; padding: 0; background: #0D0D0D; }
  .leaflet-container { background: #0D0D0D; font-family: -apple-system, Roboto, sans-serif; }
  .sc-cross {
    width: 22px; height: 22px; border-radius: 11px; background: #FFFFFF;
    border: 2.5px solid #F5A623; display: flex; align-items: center; justify-content: center;
    font-size: 12px; color: #F5A623; font-weight: 700;
  }
  .sc-haz { display: flex; align-items: center; justify-content: center; border-radius: 50%; }
  .sc-badge {
    position: absolute; top: -4px; right: -4px; background: #F5F5F5; color: #0D0D0D;
    border-radius: 8px; min-width: 16px; height: 16px; font-size: 10px; font-weight: 700;
    display: flex; align-items: center; justify-content: center; padding: 0 3px;
  }
  .sc-pos {
    width: 16px; height: 16px; border-radius: 8px; background: #00C97B; border: 2px solid #FFFFFF;
    box-shadow: 0 0 0 4px rgba(0,201,123,0.25);
  }
  .sc-popup { min-width: 200px; }
  .sc-popup h4 { margin: 0 0 4px; font-size: 14px; color: #111; }
  .sc-popup .meta { font-size: 12px; color: #555; margin: 2px 0; }
  .sc-popup .desc { font-size: 12px; color: #333; margin: 4px 0; }
  .sc-popup .actions { display: flex; gap: 6px; margin-top: 8px; }
  .sc-popup button {
    flex: 1; border: none; border-radius: 6px; padding: 7px 4px; font-size: 12px;
    font-weight: 600; cursor: pointer;
  }
  .sc-confirm { background: rgba(0,201,123,0.15); color: #009B60; }
  .sc-dismiss { background: #eee; color: #555; }
  .leaflet-popup-content { margin: 10px 12px; }
</style>
</head>
<body>
<div id="map"></div>
<script>
  var post = function (m) {
    if (window.ReactNativeWebView) window.ReactNativeWebView.postMessage(JSON.stringify(m));
  };
  var map = L.map('map', { zoomControl: false, attributionControl: false })
    .setView([${center.lat}, ${center.lon}], 13);
  L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(map);

  var layers = {
    bike: L.layerGroup().addTo(map),
    zone: L.layerGroup().addTo(map),
    route: L.layerGroup().addTo(map),
    cross: L.layerGroup().addTo(map),
    hazard: L.layerGroup().addTo(map),
    pos: L.layerGroup().addTo(map)
  };

  window.scConfirm = function (id, action) {
    post({ type: 'confirmHazard', id: id, action: action });
  };

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  window.SC_update = function (d) {
    Object.keys(layers).forEach(function (k) { layers[k].clearLayers(); });

    (d.bikePaths || []).forEach(function (seg) {
      if (seg.length > 1) L.polyline(seg, {
        color: d.isNavigating ? 'rgba(39,174,96,0.25)' : '#27ae60',
        weight: d.isNavigating ? 2 : 5, lineJoin: 'round', lineCap: 'round'
      }).addTo(layers.bike);
    });

    (d.zones || []).forEach(function (z) {
      L.circle([z.lat, z.lon], {
        radius: z.radius, color: '#F5A623', weight: 1.5, fillColor: '#F5A623', fillOpacity: 0.18
      }).addTo(layers.zone);
    });

    if (d.routeCoords && d.routeCoords.length > 1) {
      var line = L.polyline(d.routeCoords, {
        color: '#00C97B', weight: 6, lineJoin: 'round', lineCap: 'round'
      }).addTo(layers.route);
      if (d.fit) { try { map.fitBounds(line.getBounds().pad(0.15)); } catch (e) {} }
    }

    (d.crossroads || []).forEach(function (c) {
      L.marker([c.lat, c.lon], {
        icon: L.divIcon({ className: '', html: '<div class="sc-cross">!</div>', iconSize: [22, 22], iconAnchor: [11, 11] })
      }).addTo(layers.cross);
    });

    (d.hazards || []).forEach(function (h) {
      var size = h.severity * 4 + 20;
      var iconSize = h.severity * 2 + 10;
      var html = '<div style="position:relative;width:' + size + 'px;height:' + size + 'px;">'
        + '<div class="sc-haz" style="width:' + size + 'px;height:' + size + 'px;background:' + esc(h.color)
        + ';opacity:' + (0.18 + h.severity * 0.072).toFixed(2) + ';border:' + (1 + h.severity * 0.3).toFixed(1)
        + 'px solid ' + esc(h.color) + ';font-size:' + iconSize + 'px;">' + esc(h.icon) + '</div>'
        + (h.reportCount > 1 ? '<div class="sc-badge">' + h.reportCount + '</div>' : '')
        + '</div>';
      var m = L.marker([h.lat, h.lon], {
        icon: L.divIcon({ className: '', html: html, iconSize: [size, size], iconAnchor: [size / 2, size / 2] })
      }).addTo(layers.hazard);
      var actions = '<div class="actions">'
        + '<button class="sc-confirm" onclick="scConfirm(\\'' + esc(h.id) + '\\',\\'confirm\\')">\\u2713 I see this too</button>'
        + '<button class="sc-dismiss" onclick="scConfirm(\\'' + esc(h.id) + '\\',\\'dismiss\\')">\\u2717 Not there</button>'
        + '</div>';
      m.bindPopup('<div class="sc-popup"><h4>' + esc(h.icon) + ' ' + esc(h.title) + '</h4>'
        + '<div class="meta">\\u26A0 ' + h.severity + '/10 \\u00B7 ' + esc(h.severityLabel) + '</div>'
        + (h.description ? '<div class="desc">' + esc(h.description) + '</div>' : '')
        + '<div class="meta">' + h.reportCount + ' report' + (h.reportCount !== 1 ? 's' : '') + ' \\u00B7 ' + esc(h.ageLabel) + '</div>'
        + actions + '</div>');
    });

    if (d.position) {
      L.marker([d.position.lat, d.position.lon], {
        icon: L.divIcon({ className: '', html: '<div class="sc-pos"></div>', iconSize: [16, 16], iconAnchor: [8, 8] })
      }).addTo(layers.pos);
    }
  };

  post({ type: 'ready' });
</script>
</body>
</html>`
}

export function MapWebView({
  routeCoords,
  bikePaths,
  zones,
  crossroads,
  hazards,
  position,
  isNavigating,
  initialCenter,
  onConfirmHazard,
}: MapWebViewProps) {
  const ref = useRef<WebView>(null)
  const readyRef = useRef(false)

  const center = initialCenter ?? DEFAULT_CENTER
  // Build the HTML once; data flows in via injected JS, not by re-rendering.
  const html = useMemo(() => buildHtml(center), [center.lat, center.lon])

  const payload = useMemo(
    () =>
      JSON.stringify({
        routeCoords: routeCoords ?? [],
        bikePaths: bikePaths ?? [],
        zones: zones ?? [],
        crossroads: crossroads ?? [],
        hazards: hazards ?? [],
        position: position ?? null,
        isNavigating: !!isNavigating,
        fit: !!(routeCoords && routeCoords.length > 1),
      }),
    [routeCoords, bikePaths, zones, crossroads, hazards, position, isNavigating],
  )

  const push = useCallback(() => {
    if (!readyRef.current) return
    ref.current?.injectJavaScript(`window.SC_update(${payload}); true;`)
  }, [payload])

  // Re-inject whenever the data payload changes.
  React.useEffect(() => {
    push()
  }, [push])

  const onMessage = useCallback(
    (e: WebViewMessageEvent) => {
      let msg: { type?: string; id?: string; action?: "confirm" | "dismiss" }
      try {
        msg = JSON.parse(e.nativeEvent.data)
      } catch {
        return
      }
      if (msg.type === "ready") {
        readyRef.current = true
        ref.current?.injectJavaScript(`window.SC_update(${payload}); true;`)
      } else if (msg.type === "confirmHazard" && msg.id && msg.action) {
        onConfirmHazard?.(msg.id, msg.action)
      }
    },
    [payload, onConfirmHazard],
  )

  return (
    <WebView
      ref={ref}
      style={StyleSheet.absoluteFill}
      originWhitelist={["*"]}
      source={{ html }}
      onMessage={onMessage}
      javaScriptEnabled
      domStorageEnabled
      startInLoadingState={false}
      androidLayerType="hardware"
      // Map gestures shouldn't be hijacked by the outer scroll view.
      scrollEnabled={false}
      overScrollMode="never"
    />
  )
}
