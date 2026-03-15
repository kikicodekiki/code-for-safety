# SafeCycle Sofia

A cyclist safety navigation app for Sofia, Bulgaria. SafeCycle Sofia helps riders find safer routes through the city by combining real-time GPS tracking, crowd-sourced hazard reporting, and proximity alerts for intersections, schools, and other awareness zones.

## What it does

- *Safety-weighted routing* — A* pathfinding that prioritizes dedicated bike lanes, low-traffic roads, and cyclist-friendly infrastructure across Sofia's road network
- *Real-time alerts* — WebSocket-based notifications for crossroads (15 m), awareness zones like schools and bus stops (30 m), and reported hazards
- *Hazard reporting* — Users submit pothole, obstacle, and traffic reports with severity levels; reports decay over time and cluster to avoid over-weighting
- *Voice alerts* — Bulgarian text-to-speech announcements via the mobile app
- *Sunset reminder* — Notifies cyclists when it gets dark so they can turn on their lights

## Stack

*Backend* — FastAPI, PostgreSQL + PostGIS, Redis, NetworkX/OSMnx, Firebase Admin SDK, Docker Compose

*Mobile* — React Native (Expo SDK 54), expo-router, react-native-maps, zustand, expo-location, expo-notifications, expo-speech

## Running the app

Start the Expo development server:

npx expo start --clear

Start the backend services:

docker compose up
```