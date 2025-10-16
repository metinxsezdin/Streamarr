import { StyleSheet, Text, View } from "react-native";

export default function LogsScreen() {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Loglar</Text>
      <Text style={styles.subtitle}>
        Canlı log akışı Phase 3'te eklenecek. Şimdilik CLI üzerinden logları izleyebilirsiniz.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0f172a",
    padding: 24,
    justifyContent: "center",
    alignItems: "center",
    gap: 12,
  },
  title: {
    color: "#f8fafc",
    fontSize: 24,
    fontWeight: "700",
  },
  subtitle: {
    color: "#94a3b8",
    fontSize: 16,
    textAlign: "center",
    lineHeight: 22,
  },
});
