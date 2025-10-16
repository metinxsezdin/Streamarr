import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";

import type { ConfigModel } from "@/types/api";

const SESSION_STORAGE_KEY = "streamarr_manager_session";
const LEGACY_BROWSER_KEYS = ["streamarr-manager/session"];

export interface PersistedSession {
  baseUrl: string;
  token?: string;
  config?: ConfigModel;
}

function getBrowserStorage(): Storage | null {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    return window.localStorage ?? null;
  } catch {
    return null;
  }
}

async function secureStoreAvailable(): Promise<boolean> {
  if (Platform.OS === "web") {
    return false;
  }

  try {
    return await SecureStore.isAvailableAsync();
  } catch {
    return false;
  }
}

export async function saveSession(session: PersistedSession): Promise<void> {
  const payload = JSON.stringify(session);

  if (await secureStoreAvailable()) {
    await SecureStore.setItemAsync(SESSION_STORAGE_KEY, payload);
    return;
  }

  const storage = getBrowserStorage();
  if (storage) {
    storage.setItem(SESSION_STORAGE_KEY, payload);
  }
}

export async function loadSession(): Promise<PersistedSession | null> {
  if (await secureStoreAvailable()) {
    const value = await SecureStore.getItemAsync(SESSION_STORAGE_KEY);
    if (!value) {
      return null;
    }

    try {
      return JSON.parse(value) as PersistedSession;
    } catch {
      await SecureStore.deleteItemAsync(SESSION_STORAGE_KEY);
      return null;
    }
  }

  const storage = getBrowserStorage();
  if (!storage) {
    return null;
  }

  const value =
    storage.getItem(SESSION_STORAGE_KEY) ??
    LEGACY_BROWSER_KEYS.map((key) => storage.getItem(key)).find(
      (item): item is string => item !== null,
    ) ??
    null;
  if (!value) {
    return null;
  }

  try {
    return JSON.parse(value) as PersistedSession;
  } catch {
    storage.removeItem(SESSION_STORAGE_KEY);
    LEGACY_BROWSER_KEYS.forEach((key) => storage.removeItem(key));
    return null;
  }
}

export async function clearSession(): Promise<void> {
  if (await secureStoreAvailable()) {
    await SecureStore.deleteItemAsync(SESSION_STORAGE_KEY);
  }

  const storage = getBrowserStorage();
  if (storage) {
    storage.removeItem(SESSION_STORAGE_KEY);
    LEGACY_BROWSER_KEYS.forEach((key) => storage.removeItem(key));
  }
}
