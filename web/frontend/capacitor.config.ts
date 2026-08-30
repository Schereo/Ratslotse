import type { CapacitorConfig } from "@capacitor/cli";

// Remaining Ratslotse Android shell. iOS is built exclusively from /ios.
// The web assets are the static Next export in ./out (produced by
// `npm run build:mobile`); the app calls the backend at an absolute origin.
const config: CapacitorConfig = {
  appId: "de.ratslotse.app",
  appName: "Ratslotse",
  webDir: "out",
  server: {
    // Serve Android from https://localhost so it counts as a secure context
    // (needed for service workers / secure storage parity with iOS).
    androidScheme: "https",
  },
  plugins: {
    PushNotifications: {
      presentationOptions: ["badge", "sound", "alert"],
    },
  },
};

export default config;
