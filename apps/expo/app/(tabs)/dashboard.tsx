import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import {
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";

import { useAuth } from "@/providers/AuthProvider";
import type { HealthStatus, JobMetricsModel, JobModel } from "@/types/api";

function formatDate(value: string | null): string {
  if (!value) {
    return "—";
  }

  const date = new Date(value);
  return date.toLocaleString();
}

export default function DashboardScreen(): JSX.Element {
  const { session } = useAuth();

  const healthQuery = useQuery({
    queryKey: ["health", session?.baseUrl],
    queryFn: () => session!.client.get<HealthStatus>("/health"),
    enabled: Boolean(session),
    staleTime: 15_000,
  });

  const metricsQuery = useQuery({
    queryKey: ["job-metrics", session?.baseUrl],
    queryFn: () => session!.client.get<JobMetricsModel>("/jobs/metrics"),
    enabled: Boolean(session),
    staleTime: 15_000,
  });

  const pipelineMutation = useMutation({
    mutationFn: () => session!.client.post<JobModel>("/jobs/run", { type: "bootstrap" }),
    onSuccess: () => {
      void metricsQuery.refetch();
    },
  });

  const queueStatus = useMemo(() => {
    if (!healthQuery.data) {
      return "Bilinmiyor";
    }

    return healthQuery.data.queue.status === "ok" ? "Sağlıklı" : "Sorun";
  }, [healthQuery.data]);

  const isLoading = healthQuery.isLoading || metricsQuery.isLoading;

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl
          tintColor="#60a5fa"
          refreshing={healthQuery.isRefetching || metricsQuery.isRefetching}
          onRefresh={() => {
            void healthQuery.refetch();
            void metricsQuery.refetch();
          }}
        />
      }
    >
      <Text style={styles.pageTitle}>Kontrol Paneli</Text>

      <View style={styles.grid}>
        <View style={styles.card}>
          <Text style={styles.cardTitle}>API Sağlığı</Text>
          {healthQuery.error ? (
            <Text style={styles.errorText}>Sağlık bilgisi alınamadı.</Text>
          ) : isLoading ? (
            <ActivityIndicator color="#60a5fa" />
          ) : (
            <>
              <Text style={styles.metricValue}>{queueStatus}</Text>
              <Text style={styles.metricLabel}>Kuyruk durumu</Text>
              {healthQuery.data?.queue.detail ? (
                <Text style={styles.helperText}>{healthQuery.data.queue.detail}</Text>
              ) : null}
            </>
          )}
        </View>

        <View style={styles.card}>
          <Text style={styles.cardTitle}>İş Telemetrisi</Text>
          {metricsQuery.error ? (
            <Text style={styles.errorText}>İş metrikleri yüklenemedi.</Text>
          ) : isLoading ? (
            <ActivityIndicator color="#60a5fa" />
          ) : (
            <>
              <Text style={styles.metricValue}>{metricsQuery.data?.total ?? 0}</Text>
              <Text style={styles.metricLabel}>Toplam iş</Text>
              <Text style={styles.helperText}>
                Kuyrukta: {metricsQuery.data?.queue_depth ?? 0}
              </Text>
              <Text style={styles.helperText}>
                Son biten: {formatDate(metricsQuery.data?.last_finished_at ?? null)}
              </Text>
            </>
          )}
        </View>
      </View>

      <View style={styles.actions}>
        <TouchableOpacity
          style={[styles.primaryButton, pipelineMutation.isPending && styles.buttonDisabled]}
          onPress={() => pipelineMutation.mutate()}
          disabled={pipelineMutation.isPending}
        >
          {pipelineMutation.isPending ? (
            <ActivityIndicator color="#ffffff" />
          ) : (
            <Text style={styles.primaryButtonText}>Pipeline'ı Çalıştır</Text>
          )}
        </TouchableOpacity>
        {pipelineMutation.error ? (
          <Text style={styles.errorText}>İş kuyruğa eklenemedi.</Text>
        ) : null}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0f172a",
  },
  content: {
    padding: 24,
    gap: 24,
  },
  pageTitle: {
    color: "#f8fafc",
    fontSize: 24,
    fontWeight: "700",
  },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 16,
  },
  card: {
    flexBasis: "48%",
    backgroundColor: "#1e293b",
    borderRadius: 16,
    padding: 20,
    minWidth: 150,
    flexGrow: 1,
    gap: 8,
  },
  cardTitle: {
    color: "#cbd5f5",
    fontSize: 16,
    fontWeight: "600",
  },
  metricValue: {
    color: "#f8fafc",
    fontSize: 28,
    fontWeight: "700",
  },
  metricLabel: {
    color: "#94a3b8",
    fontSize: 14,
  },
  helperText: {
    color: "#94a3b8",
    fontSize: 13,
  },
  actions: {
    gap: 12,
  },
  primaryButton: {
    backgroundColor: "#2563eb",
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
  },
  buttonDisabled: {
    opacity: 0.7,
  },
  primaryButtonText: {
    color: "#ffffff",
    fontSize: 16,
    fontWeight: "600",
  },
  errorText: {
    color: "#f87171",
  },
});
