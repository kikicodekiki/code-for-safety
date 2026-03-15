import { LogBox } from "react-native"

// 1. Ignore the specific warning in React Native's standard LogBox
LogBox.ignoreLogs([
  "expo-notifications: Android Push notifications",
  "`expo-notifications` functionality is not fully supported in Expo Go",
])

// 2. Intercept console.error to prevent Expo Router / Metro from picking it up
//    and showing a full-screen red fatal error overlay.
const originalError = console.error
console.error = (...args) => {
  if (typeof args[0] === "string") {
    if (args[0].includes("expo-notifications: Android Push notifications") ||
        args[0].includes("expo-notifications` functionality")) {
      return // Swallow the annoying push notification warning in Expo Go
    }
  }
  originalError(...args)
}

const originalWarn = console.warn
console.warn = (...args) => {
  if (typeof args[0] === "string") {
    if (args[0].includes("expo-notifications: Android Push notifications") ||
        args[0].includes("expo-notifications` functionality")) {
      return
    }
  }
  originalWarn(...args)
}
