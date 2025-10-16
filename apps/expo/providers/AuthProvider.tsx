import type { PropsWithChildren } from "react";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { createApiClient, type ApiClient } from "@/lib/api";
import {
  clearSession,
  loadSession,
  saveSession,
  type PersistedSession,
} from "@/lib/storage";

interface SessionValue extends PersistedSession {
  client: ApiClient;
}

type AuthState =
  | { status: "loading" }
  | { status: "needs_setup"; lastBackendUrl?: string }
  | { status: "authenticated"; data: PersistedSession };

interface AuthContextValue {
  status: AuthState["status"];
  session: SessionValue | null;
  lastBackendUrl?: string;
  completeSetup: (session: PersistedSession) => Promise<void>;
  updateSession: (updater: (previous: PersistedSession) => PersistedSession) => void;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: PropsWithChildren): JSX.Element {
  const [state, setState] = useState<AuthState>({ status: "loading" });

  useEffect(() => {
    let mounted = true;
    loadSession().then((session) => {
      if (!mounted) {
        return;
      }

      if (session) {
        setState({ status: "authenticated", data: session });
      } else {
        setState({ status: "needs_setup" });
      }
    });

    return () => {
      mounted = false;
    };
  }, []);

  const completeSetup = useCallback(async (sessionData: PersistedSession) => {
    setState({ status: "authenticated", data: sessionData });
    await saveSession(sessionData);
  }, []);

  const updateSession = useCallback(
    (updater: (previous: PersistedSession) => PersistedSession) => {
      setState((current) => {
        if (current.status !== "authenticated") {
          return current;
        }

        const updated = updater(current.data);
        void saveSession(updated);
        return { status: "authenticated", data: updated };
      });
    },
    [],
  );

  const signOut = useCallback(async () => {
    setState((current) => {
      if (current.status === "authenticated") {
        return { status: "needs_setup", lastBackendUrl: current.data.baseUrl };
      }

      if (current.status === "needs_setup") {
        return { status: "needs_setup", lastBackendUrl: current.lastBackendUrl };
      }

      return { status: "needs_setup" };
    });
    await clearSession();
  }, []);

  const sessionValue = useMemo<SessionValue | null>(() => {
    if (state.status !== "authenticated") {
      return null;
    }

    return {
      ...state.data,
      client: createApiClient(state.data.baseUrl, state.data.token),
    };
  }, [state]);

  const lastBackendUrl = useMemo(() => {
    if (state.status === "needs_setup") {
      return state.lastBackendUrl;
    }

    if (state.status === "authenticated") {
      return state.data.baseUrl;
    }

    return undefined;
  }, [state]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status: state.status,
      session: sessionValue,
      lastBackendUrl,
      completeSetup,
      updateSession,
      signOut,
    }),
    [completeSetup, lastBackendUrl, sessionValue, signOut, state.status, updateSession],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }

  return context;
}
