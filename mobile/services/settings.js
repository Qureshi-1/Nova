import * as SecureStore from "expo-secure-store";
import { create } from "zustand";

const STORAGE_KEY = "nova_settings";

const DEFAULT_SETTINGS = {
  darkMode: true,
  fontScale: 1.0,
  model: "local",
  mode: "local",
  backendIp: "",
};

export const useSettingsStore = create((set, get) => ({
  ...DEFAULT_SETTINGS,
  loaded: false,
  load: async () => {
    try {
      const raw = await SecureStore.getItemAsync(STORAGE_KEY);
      if (raw) {
        set({ ...JSON.parse(raw), loaded: true });
      } else {
        set({ loaded: true });
      }
    } catch (error) {
      set({ loaded: true });
    }
  },
  persist: () => {
    const state = get();
    const payload = {
      darkMode: state.darkMode,
      fontScale: state.fontScale,
      model: state.model,
      mode: state.mode,
      backendIp: state.backendIp,
    };
    SecureStore.setItemAsync(STORAGE_KEY, JSON.stringify(payload)).catch(() => {});
  },
  setBackendIp: (ip) => {
    set({ backendIp: ip });
    get().persist();
  },
  applyFromResponse: (text) => {
    const lower = (text || "").toLowerCase();
    const patch = {};
    if (/dark mode activated/.test(lower)) patch.darkMode = true;
    if (/dark mode off/.test(lower)) patch.darkMode = false;
    if (/font size increased/.test(lower)) {
      patch.fontScale = Math.min(1.6, Math.round((get().fontScale + 0.2) * 10) / 10);
    }
    if (/font size decreased/.test(lower)) {
      patch.fontScale = Math.max(0.8, Math.round((get().fontScale - 0.2) * 10) / 10);
    }
    if (/switched to local model/.test(lower)) patch.model = "local";
    if (/connecting to cloud/.test(lower)) patch.mode = "cloud";
    if (/api disconnected/.test(lower)) patch.mode = "local";
    if (/api connected/.test(lower)) patch.mode = "cloud";
    const switched = lower.match(/model switched to (.+?)(?:[,.!]| unloaded|$)/);
    if (switched) patch.model = switched[1].trim();
    if (Object.keys(patch).length > 0) {
      set(patch);
      get().persist();
    }
  },
}));
