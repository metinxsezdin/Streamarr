import { QueryClient, QueryClientProvider, focusManager } from "@tanstack/react-query";
import type { PropsWithChildren } from "react";
import { useEffect, useState } from "react";
import { AppState, Platform } from "react-native";

function onAppStateChange(status: string) {
  focusManager.setFocused(status === "active");
}

export function QueryProvider({ children }: PropsWithChildren): JSX.Element {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            retry: 1,
          },
        },
      }),
  );

  useEffect(() => {
    if (Platform.OS === "web") {
      return;
    }

    const subscription = AppState.addEventListener("change", onAppStateChange);
    return () => {
      subscription.remove();
    };
  }, []);

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
