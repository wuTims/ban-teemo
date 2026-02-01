// frontend/src/hooks/useSettings.ts
import { useState, useCallback, useEffect } from "react";

const STORAGE_KEYS = {
  API_KEY: "ban_teemo_api_key",
  LLM_ENABLED: "ban_teemo_llm_enabled",
} as const;

export interface SettingsState {
  apiKey: string;
  llmEnabled: boolean;
}

export function useSettings() {
  const [apiKey, setApiKeyState] = useState<string>(() => {
    try {
      return localStorage.getItem(STORAGE_KEYS.API_KEY) || "";
    } catch {
      return "";
    }
  });

  const [llmEnabled, setLlmEnabledState] = useState<boolean>(() => {
    try {
      return localStorage.getItem(STORAGE_KEYS.LLM_ENABLED) === "true";
    } catch {
      return false;
    }
  });

  const setApiKey = useCallback((key: string) => {
    setApiKeyState(key);
    try {
      if (key) {
        localStorage.setItem(STORAGE_KEYS.API_KEY, key);
      } else {
        localStorage.removeItem(STORAGE_KEYS.API_KEY);
      }
    } catch (e) {
      console.error("Failed to save API key to localStorage:", e);
    }
  }, []);

  const setLlmEnabled = useCallback((enabled: boolean) => {
    setLlmEnabledState(enabled);
    try {
      localStorage.setItem(STORAGE_KEYS.LLM_ENABLED, String(enabled));
    } catch (e) {
      console.error("Failed to save LLM enabled setting:", e);
    }
  }, []);

  // Sync with localStorage changes from other tabs
  useEffect(() => {
    const handleStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEYS.API_KEY) {
        setApiKeyState(e.newValue || "");
      } else if (e.key === STORAGE_KEYS.LLM_ENABLED) {
        setLlmEnabledState(e.newValue === "true");
      }
    };

    window.addEventListener("storage", handleStorage);
    return () => window.removeEventListener("storage", handleStorage);
  }, []);

  return {
    apiKey,
    llmEnabled,
    setApiKey,
    setLlmEnabled,
    hasApiKey: apiKey.length > 0,
  };
}
