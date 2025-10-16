import { useQuery } from "@tanstack/react-query";
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { useAuth } from "@/providers/AuthProvider";
import type { JobModel } from "@/types/api";

function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }

  return new Date(value).toLocaleString();
}

function JobRow({ job }: { job: JobModel }): JSX.Element {
  return (
    <View style={styles.jobCard}>
      <View style={styles.jobHeader}>
        <Text style={styles.jobTitle}>{job.type}</Text>
        <Text style={styles.jobStatus}>{job.status.toUpperCase()}</Text>
      </View>
      <Text style={styles.jobMeta}>ID: {job.id}</Text>
      <Text style={styles.jobMeta}>İlerleme: {(job.progress * 100).toFixed(0)}%</Text>
      <Text style={styles.jobMeta}>Başlangıç: {formatDate(job.started_at)}</Text>
      <Text style={styles.jobMeta}>Bitiş: {formatDate(job.finished_at)}</Text>
      {job.worker_id ? <Text style={styles.jobMeta}>Worker: {job.worker_id}</Text> : null}
      {job.error_message ? (
        <Text style={styles.jobError}>Hata: {job.error_message}</Text>
      ) : null}
    </View>
  );
}

export default function JobsScreen(): JSX.Element {
  const { session } = useAuth();

  const query = useQuery({
    queryKey: ["jobs", session?.baseUrl],
    queryFn: () => session!.client.get<JobModel[]>("/jobs?limit=25"),
    enabled: Boolean(session),
  });

  if (query.isLoading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#60a5fa" />
      </View>
    );
  }

  if (query.error) {
    return (
      <View style={styles.loadingContainer}>
        <Text style={styles.errorText}>İş listesi yüklenemedi.</Text>
      </View>
    );
  }

  return (
    <FlatList
      data={query.data ?? []}
      keyExtractor={(item) => item.id}
      contentContainerStyle={styles.listContent}
      style={styles.list}
      refreshControl={
        <RefreshControl
          tintColor="#60a5fa"
          refreshing={query.isRefetching}
          onRefresh={() => {
            void query.refetch();
          }}
        />
      }
      ListEmptyComponent={() => (
        <View style={styles.emptyState}>
          <Text style={styles.emptyText}>Kuyrukta veya geçmişte iş bulunamadı.</Text>
        </View>
      )}
      renderItem={({ item }) => <JobRow job={item} />}
    />
  );
}

const styles = StyleSheet.create({
  list: {
    flex: 1,
    backgroundColor: "#0f172a",
  },
  listContent: {
    padding: 24,
    gap: 16,
  },
  jobCard: {
    backgroundColor: "#1e293b",
    borderRadius: 16,
    padding: 20,
    gap: 6,
  },
  jobHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  jobTitle: {
    color: "#f8fafc",
    fontSize: 18,
    fontWeight: "700",
  },
  jobStatus: {
    color: "#0f172a",
    backgroundColor: "#facc15",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
    overflow: "hidden",
    fontWeight: "600",
  },
  jobMeta: {
    color: "#94a3b8",
    fontSize: 14,
  },
  jobError: {
    color: "#f87171",
    fontSize: 14,
  },
  emptyState: {
    padding: 32,
    alignItems: "center",
  },
  emptyText: {
    color: "#94a3b8",
    fontSize: 16,
  },
  loadingContainer: {
    flex: 1,
    backgroundColor: "#0f172a",
    alignItems: "center",
    justifyContent: "center",
  },
  errorText: {
    color: "#f87171",
    fontSize: 16,
  },
});
