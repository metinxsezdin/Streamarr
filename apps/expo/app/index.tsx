import { Redirect } from "expo-router";
import { ActivityIndicator, View } from "react-native";

import { useAuth } from "@/providers/AuthProvider";

export default function Index() {
  const { status } = useAuth();

  if (status === "loading") {
    return (
      <View
        style={{
          flex: 1,
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: "#0f172a",
        }}
      >
        <ActivityIndicator size="large" color="#60a5fa" />
      </View>
    );
  }

  if (status === "needs_setup") {
    return <Redirect href="/(onboarding)/setup" />;
  }

  return <Redirect href="/(tabs)/dashboard" />;
}
