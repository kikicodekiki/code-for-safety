# SafeCycle Sofia — Deployment Fixes & Changes

This document describes the work done to take SafeCycle Sofia from a local hackathon build to a working deployed system: a FastAPI backend running on Railway, and a mobile app distributed as a standalone Android APK plus an Expo Go build for iOS testing. For each change: what the problem was, why it happened, and what the fix does.

---

## Backend (Railway deployment)

### 1. Docker build & deploy configuration
**Problem:** The initial Docker build was heavy and the service failed Railway's health checks.
**Fix:** Rewrote the Dockerfile to use prebuilt geospatial wheels (shapely, pyproj, pyogrio) instead of compiling GDAL from source, cutting build time and image size significantly. Fixed the healthcheck to hit `/health` and bind to Railway's dynamic `$PORT` instead of a hardcoded port. Pinned Railway to build from the committed Dockerfile via `railway.json` rather than relying on auto-detected build settings.

### 2. API-key authentication, CORS lockdown, rate limiting
**Problem:** The backend was deployed with no authentication and a wide-open CORS policy — anyone with the URL could read/write hazard data or hit the routing engine.
**Fix:** Added `X-API-Key` header authentication on every data route (`app/core/security.py`), using constant-time comparison to avoid timing attacks. Locked CORS down to an explicit origin allow-list (empty by default — native apps aren't affected by CORS at all). Added a per-IP in-process rate limiter (120 req/min) to blunt abuse. Interactive API docs (`/docs`, `/redoc`) are now off by default in production so the API schema isn't public.

### 3. Database wiring (PostgreSQL + PostGIS + Redis)
**Problem:** The schema requires the PostGIS extension for spatial queries (hazard geometry, awareness-zone lookups), but Railway's default "Add PostgreSQL" plugin doesn't include it — attempting to enable it fails silently.
**Fix:** Used Railway's dedicated PostGIS template instead of the plain Postgres addon. Added a `DATABASE_URL` normalizer (`app/config.py`) so Railway's `postgres://` connection string is automatically rewritten to the `postgresql+asyncpg://` scheme the async engine needs, and strips the `sslmode` parameter (unsupported by asyncpg). Added an idempotent SQL-migration runner that executes on every startup — linking a fresh database now self-provisions its schema (tables, PostGIS extension, seed data) with zero manual SQL.

### 4. GPS WebSocket bug — the real "backend won't connect" issue
**Problem:** Real-time GPS proximity alerts (crossroad/hazard/awareness-zone notifications) never worked — every WebSocket connection attempt failed with a generic 500 error, with no indication of why.
**Root cause:** A dependency-injection function, `get_sunset_service()`, constructed a `SunsetService()` object with no arguments, but the class requires a `redis` client to be passed in. Every WebSocket handshake crashed while FastAPI was resolving dependencies — before the connection was even accepted — which is why the failure looked like an infrastructure problem rather than an application bug.
**Fix:** Corrected the function to read the already-properly-constructed `SunsetService` instance off the app's shared state, the same pattern used by the other dependency functions. Verified by reproducing the exact bug locally against the real application and confirming a clean connection afterward.

---

## Mobile app (Expo / React Native)

### 5. Map rendering — replaced Google Maps with OpenStreetMap
**Problem:** The map showed blank on Android with a small Google logo in the corner. `react-native-maps` always uses the Google Maps rendering engine on Android, regardless of configuration — and without a paid Google Maps API key, that engine fails to initialize.
**Fix:** Replaced `react-native-maps` entirely with a self-contained map component built on Leaflet running inside a WebView (`src/components/MapWebView.tsx`), using free OpenStreetMap tiles. No Google dependency, no API key, no billing account required. All existing map features — the route line, bike-path overlays, hazard pins, awareness-zone circles, and live position marker — were reimplemented on top of Leaflet with equivalent styling and interaction (including tap-to-confirm/dismiss on hazard pins).
**Note:** this is a temporary fix until we have a Google Maps API key. Once one is available, the map can be switched back to `react-native-maps`/Google (or kept on Leaflet, if preferred) — this isn't meant to be the permanent solution.

### 6. Critical bug: the app was never actually reaching the backend
**Problem:** Every backend-dependent feature — route search, hazard viewing/reporting, bike-path loading, the GPS WebSocket — failed in the installed app, even though the backend itself was confirmed healthy and fast when tested directly.
**Root cause:** The app's environment-variable configuration (`src/integration/config.ts`, which backs every network call in the app) read values through an intermediate variable: `const env = process.env; env.EXPO_PUBLIC_API_BASE_URL`. Expo's build system only inlines environment variables when they're accessed as the literal expression `process.env.EXPO_PUBLIC_X` directly — it cannot trace through an aliased reference. As a result, every compiled build silently fell back to hardcoded defaults (`http://localhost:8000` — the phone itself, and an empty API key) instead of the real backend URL. This was confirmed by extracting the actual compiled app bundle and finding the real backend address was completely absent from it.
**Fix:** Removed the intermediate variable so each environment variable is read directly at its point of use, matching the pattern Expo's build tooling requires. Verified by rebuilding and confirming the real backend URLs are now present in the compiled bundle.

### 7. Crash on slow/failed GPS fix
**Problem:** Occasionally the app would show a generic "Unknown error / request timed out" message on launch, which looked like a backend connectivity issue but wasn't.
**Root cause:** The initial GPS location request on the map screen had no error handling. A slow or failed first GPS fix (common on first launch or indoors) threw an unhandled error that surfaced as a confusing native error dialog.
**Fix:** Wrapped the initial GPS request so a slow/failed fix degrades quietly instead of crashing the screen — the app already has a separate background location task that supplies the real position once navigation starts, so the initial fix is only a best-effort convenience, not a hard requirement.

### 8. Dependency security updates
**Problem:** A routine security audit (`npm audit`) flagged 28 vulnerabilities in the mobile app's dependencies, including 1 critical and 7 high-severity issues.
**Fix:** Applied all non-breaking fixes, resolving the critical issue and all 7 high-severity issues (28 → 14 remaining) with zero changes to the app's declared dependencies — only transitive/lockfile updates. The 14 remaining findings (all moderate severity) trace to exactly two CVEs in Expo's own build-time tooling (`postcss`, `uuid`) — code that runs only during the build process and is never shipped in the app itself. The only available fix for those is a major Expo SDK upgrade (54 → 57) that would itself break the app (SDK 57 rejects environment variables that look like API keys, which this app intentionally uses). Recommendation: defer that upgrade to a planned migration rather than force it for a build-time-only, non-shipping risk.

---

## Summary

| Area | Problem | Fix |
|---|---|---|
| Docker build | Slow build, failed healthchecks | Lightweight prebuilt-wheel image, correct healthcheck/port binding |
| Backend security | No auth, open CORS, no rate limiting | API-key auth, CORS allow-list, per-IP rate limiting, docs gated off in prod |
| Database | PostGIS missing, manual migrations | PostGIS-enabled Postgres, auto-normalized connection string, self-provisioning migrations on startup |
| GPS WebSocket | Every connection failed (500) | Fixed a dependency-injection bug (`get_sunset_service`) crashing the handshake |
| Map rendering | Blank map, needs paid Google key | Replaced with Leaflet/OpenStreetMap — free, no Google dependency |
| App connectivity | App never reached the real backend | Fixed an environment-variable inlining bug in the app's config module |
| GPS crash | Misleading "connection" error on launch | Made the initial GPS fetch fail gracefully instead of crashing |
| Dependencies | 28 npm vulnerabilities | Fixed all critical/high (28→14); remaining are non-shipping build-tooling only |
