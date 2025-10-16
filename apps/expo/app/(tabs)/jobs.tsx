import { useMutation, useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Modal,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";

import { resolveWebSocketUrl } from "@/lib/api";
import { useAuth } from "@/providers/AuthProvider";
import type { JobLogModel, JobModel, JobStatus } from "@/types/api";

const STATUS_OPTIONS: { value: JobStatus; label: string }[] = [
  { value: "queued", label: "Kuyrukta" },
  { value: "running", label: "Çalışıyor" },
  { value: "completed", label: "Tamamlandı" },
  { value: "failed", label: "Hata" },
  { value: "cancelled", label: "İptal" },
];

const LOG_LEVEL_COLORS: Record<JobLogModel["level"], string> = {
  debug: "#94a3b8",
  info: "#38bdf8",
  warning: "#facc15",
  error: "#f87171",
};

function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "—";
  }

  return new Date(value).toLocaleString();
}

function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) {
    return "—";
  }

  if (seconds < 60) {
    return `${seconds.toFixed(0)} sn`;
  }

  const minutes = seconds / 60;
  if (minutes < 60) {
    return `${minutes.toFixed(1)} dk`;
  }

  const hours = minutes / 60;
  return `${hours.toFixed(1)} sa`;
}

function isJobActive(status: JobStatus): boolean {
  return status === "queued" || status === "running";
}

interface FilterChipProps {
  label: string;
  selected?: boolean;
  onPress: () => void;
}

function FilterChip({ label, selected, onPress }: FilterChipProps) {
  return (
    <Pressable
      onPress={onPress}
      style={[styles.chip, selected ? styles.chipSelected : styles.chipUnselected]}
    >
      <Text style={[styles.chipText, selected ? styles.chipTextSelected : undefined]}>
        {label}
      </Text>
    </Pressable>
  );
}

function JobSkeleton() {
  return (
    <View style={styles.jobCard}>
      <View style={styles.skeletonLineWide} />
      <View style={styles.skeletonLine} />
      <View style={styles.skeletonProgress} />
      <View style={styles.skeletonLine} />
      <View style={styles.skeletonLine} />
    </View>
  );
}

function JobRow({ job, onPress }: { job: JobModel; onPress: () => void }) {
  const progressPercent = Math.min(100, Math.max(0, Math.round((job.progress ?? 0) * 100)));
  const statusStyleKey = `status${job.status}` as keyof typeof styles;
  const statusStyle = styles[statusStyleKey] ?? styles.statusDefault;

  return (
    <Pressable onPress={onPress} style={styles.jobCard}>
      <View style={styles.jobHeader}>
        <Text style={styles.jobTitle}>{job.type}</Text>
        <Text style={[styles.jobStatus, statusStyle]}>
          {job.status.toUpperCase()}
        </Text>
      </View>
      <Text style={styles.jobMeta}>ID: {job.id}</Text>
      <View style={styles.progressRow}>
        <View style={styles.progressBarTrack}>
          <View style={[styles.progressBarFill, { width: `${progressPercent}%` }]} />
        </View>
        <Text style={styles.progressText}>{progressPercent}%</Text>
      </View>
      <Text style={styles.jobMeta}>Başlangıç: {formatDate(job.started_at)}</Text>
      <Text style={styles.jobMeta}>Bitiş: {formatDate(job.finished_at)}</Text>
      <Text style={styles.jobMeta}>Süre: {formatDuration(job.duration_seconds)}</Text>
      {job.worker_id ? <Text style={styles.jobMeta}>Worker: {job.worker_id}</Text> : null}
      {job.error_message ? (
        <Text style={styles.jobError}>Hata: {job.error_message}</Text>
      ) : null}
    </Pressable>
  );
}

function toJobLogModel(value: unknown, fallbackJobId: string): JobLogModel | null {
  if (!value || typeof value !== "object") {
    return null;
  }

  const candidate = value as Partial<JobLogModel>;
  if (!candidate.message || !candidate.level || !candidate.created_at) {
    return null;
  }

  const id = typeof candidate.id === "number" ? candidate.id : Date.now();
  const jobId = typeof candidate.job_id === "string" ? candidate.job_id : fallbackJobId;
  const level = candidate.level as JobLogModel["level"];

  return {
    id,
    job_id: jobId,
    level,
    message: String(candidate.message),
    context: (candidate.context as Record<string, unknown> | null | undefined) ?? null,
    created_at: String(candidate.created_at),
  };
}

function useJobLogStream(
  baseUrl: string | undefined,
  token: string | undefined,
  jobId: string | null,
): { entries: JobLogModel[]; isConnected: boolean } {
  const [entries, setEntries] = useState<JobLogModel[]>([]);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    if (!jobId) {
      setEntries([]);
      setIsConnected(false);
      return;
    }

    if (!baseUrl) {
      return;
    }

    const socketUrl = resolveWebSocketUrl(baseUrl, `/jobs/${jobId}/logs/stream`);
    const finalUrl = token
      ? `${socketUrl}${socketUrl.includes("?") ? "&" : "?"}token=${encodeURIComponent(token)}`
      : socketUrl;

    let socket: WebSocket | null = null;
    try {
      socket = new WebSocket(finalUrl);
    } catch {
      return;
    }

    let active = true;
    socket.onopen = () => {
      if (!active) {
        return;
      }
      setIsConnected(true);
    };
    socket.onclose = () => {
      if (!active) {
        return;
      }
      setIsConnected(false);
    };
    socket.onerror = () => {
      if (!active) {
        return;
      }
      setIsConnected(false);
    };
    socket.onmessage = (event) => {
      if (!active) {
        return;
      }

      try {
        const parsed = JSON.parse(event.data as string);
        const incoming = Array.isArray(parsed) ? parsed : [parsed];
        setEntries((current) => {
          const next = [...current];
          for (const item of incoming) {
            const log = toJobLogModel(item, jobId);
            if (!log) {
              continue;
            }
            const key = `${log.id}-${log.created_at}`;
            if (next.some((existing) => `${existing.id}-${existing.created_at}` === key)) {
              continue;
            }
            next.push(log);
          }
          return next;
        });
      } catch {
        // Ignore malformed payloads
      }
    };

    return () => {
      active = false;
      setIsConnected(false);
      socket?.close();
    };
  }, [baseUrl, jobId, token]);

  return { entries, isConnected };
}

interface JobDetailModalProps {
  jobId: string | null;
  onClose: () => void;
}

function JobDetailModal({ jobId, onClose }: JobDetailModalProps) {
  const { session } = useAuth();

  const jobQuery = useQuery<JobModel>({
    queryKey: ["jobs", "detail", session?.baseUrl, jobId],
    queryFn: () => session!.client.get<JobModel>(`/jobs/${jobId}`),
    enabled: Boolean(session && jobId),
  });

  const logStream = useJobLogStream(session?.client.baseUrl, session?.client.token, jobId);

  const logsQuery = useQuery<JobLogModel[]>({
    queryKey: ["jobs", "logs", session?.baseUrl, jobId],
    queryFn: () => session!.client.get<JobLogModel[]>(`/jobs/${jobId}/logs?limit=250`),
    enabled: Boolean(session && jobId),
  });

  const job = jobQuery.data ?? null;
  const refetchJob = jobQuery.refetch;
  const refetchLogs = logsQuery.refetch;

  useEffect(() => {
    if (!jobId || !job || !isJobActive(job.status)) {
      return;
    }

    const timer = setInterval(() => {
      void refetchJob();
    }, 4000);

    return () => {
      clearInterval(timer);
    };
  }, [jobId, job?.status, refetchJob]);

  useEffect(() => {
    if (!jobId || !job || !isJobActive(job.status) || logStream.isConnected) {
      return;
    }

    const timer = setInterval(() => {
      void refetchLogs();
    }, 4000);

    return () => {
      clearInterval(timer);
    };
  }, [jobId, job?.status, logStream.isConnected, refetchLogs]);

  const cancelMutation = useMutation({
    mutationFn: async () => {
      if (!session || !jobId) {
        throw new Error("Session missing");
      }
      return session.client.post<JobModel>(`/jobs/${jobId}/cancel`, {});
    },
    onSuccess: () => {
      void jobQuery.refetch();
      void logsQuery.refetch();
      Alert.alert("İptal edildi", "İş iptal isteği gönderildi.");
    },
    onError: () => {
      Alert.alert("İptal başarısız", "İş iptal isteği gönderilemedi.");
    },
  });

  const mergedLogs = useMemo(() => {
    const combined = [...(logsQuery.data ?? [])];
    const seen = new Set(combined.map((entry) => `${entry.id}-${entry.created_at}`));
    for (const entry of logStream.entries) {
      const key = `${entry.id}-${entry.created_at}`;
      if (!seen.has(key)) {
        combined.push(entry);
        seen.add(key);
      }
    }

    return combined.sort((a, b) => {
      const left = new Date(a.created_at).getTime();
      const right = new Date(b.created_at).getTime();
      return left - right;
    });
  }, [logStream.entries, logsQuery.data]);

  const isVisible = Boolean(jobId);
  const isCancelable = job ? isJobActive(job.status) : false;

  const handleCancel = useCallback(() => {
    if (!jobId || cancelMutation.isPending) {
      return;
    }

    Alert.alert("İşi iptal et", "Bu işi iptal etmek istediğinize emin misiniz?", [
      { text: "Vazgeç", style: "cancel" },
      {
        text: "İptal et",
        style: "destructive",
        onPress: () => {
          cancelMutation.mutate();
        },
      },
    ]);
  }, [cancelMutation, jobId]);

  return (
    <Modal visible={isVisible} animationType="slide" onRequestClose={onClose}>
      <View style={styles.modalContainer}>
        {jobQuery.isLoading ? (
          <View style={styles.modalLoading}>
            <ActivityIndicator size="large" color="#60a5fa" />
          </View>
        ) : jobQuery.error ? (
          <View style={styles.modalError}>
            <Text style={styles.errorText}>İş detayları yüklenemedi.</Text>
          </View>
        ) : job ? (
          <ScrollView contentContainerStyle={styles.modalContent}>
            <Text style={styles.modalTitle}>{job.type}</Text>
            <Text style={styles.modalMeta}>Durum: {job.status.toUpperCase()}</Text>
            <Text style={styles.modalMeta}>ID: {job.id}</Text>
            <Text style={styles.modalMeta}>Worker: {job.worker_id ?? "—"}</Text>
            <Text style={styles.modalMeta}>Oluşturulma: {formatDate(job.created_at)}</Text>
            <Text style={styles.modalMeta}>Başlangıç: {formatDate(job.started_at)}</Text>
            <Text style={styles.modalMeta}>Bitiş: {formatDate(job.finished_at)}</Text>
            <Text style={styles.modalMeta}>Süre: {formatDuration(job.duration_seconds)}</Text>
            {job.payload ? (
              <View style={styles.modalSection}>
                <Text style={styles.modalSectionTitle}>Yük</Text>
                <Text style={styles.payloadText}>{JSON.stringify(job.payload, null, 2)}</Text>
              </View>
            ) : null}
            {job.error_message ? (
              <View style={styles.modalSection}>
                <Text style={styles.modalSectionTitle}>Hata</Text>
                <Text style={styles.errorText}>{job.error_message}</Text>
              </View>
            ) : null}

            <View style={styles.modalSection}>
              <Text style={styles.modalSectionTitle}>Loglar</Text>
              <Text style={styles.helperText}>
                Canlı yayın: {logStream.isConnected ? "Bağlı" : "Pasif"}
              </Text>
              {logsQuery.isLoading && mergedLogs.length === 0 ? (
                <ActivityIndicator color="#60a5fa" />
              ) : mergedLogs.length === 0 ? (
                <Text style={styles.helperText}>Log kaydı bulunamadı.</Text>
              ) : (
                mergedLogs.map((entry) => (
                  <View key={`${entry.id}-${entry.created_at}`} style={styles.logLine}>
                    <Text
                      style={[styles.logLevel, { color: LOG_LEVEL_COLORS[entry.level] ?? "#38bdf8" }]}
                    >
                      {entry.level.toUpperCase()}
                    </Text>
                    <View style={styles.logBody}>
                      <Text style={styles.logMessage}>{entry.message}</Text>
                      <Text style={styles.logTimestamp}>{formatDate(entry.created_at)}</Text>
                      {entry.context ? (
                        <Text style={styles.logContext}>{JSON.stringify(entry.context)}</Text>
                      ) : null}
                    </View>
                  </View>
                ))
              )}
            </View>

            {isCancelable ? (
              <TouchableOpacity
                style={styles.destructiveButton}
                onPress={handleCancel}
                disabled={cancelMutation.isPending}
              >
                {cancelMutation.isPending ? (
                  <ActivityIndicator color="#0f172a" />
                ) : (
                  <Text style={styles.destructiveButtonText}>İşi İptal Et</Text>
                )}
              </TouchableOpacity>
            ) : null}
          </ScrollView>
        ) : null}

        <TouchableOpacity style={styles.modalCloseButton} onPress={onClose}>
          <Text style={styles.modalCloseText}>Kapat</Text>
        </TouchableOpacity>
      </View>
    </Modal>
  );
}

export default function JobsScreen() {
  const { session } = useAuth();
  const [selectedStatuses, setSelectedStatuses] = useState<JobStatus[]>([]);
  const [jobType, setJobType] = useState("");
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);

  const filterEntries = useMemo(() => {
    const entries: [string, string][] = [["limit", "50"]];
    const normalizedStatuses = [...selectedStatuses].sort();
    for (const status of normalizedStatuses) {
      entries.push(["status", status]);
    }
    const trimmedType = jobType.trim();
    if (trimmedType) {
      entries.push(["type", trimmedType]);
    }

    return entries;
  }, [jobType, selectedStatuses]);

  const jobsQuery = useQuery({
    queryKey: ["jobs", "list", session?.baseUrl, filterEntries],
    queryFn: async () => {
      const params = new URLSearchParams(filterEntries);
      return session!.client.get<JobModel[]>(`/jobs?${params.toString()}`);
    },
    enabled: Boolean(session),
    refetchInterval: 10_000,
  });

  const toggleStatus = useCallback((status: JobStatus) => {
    setSelectedStatuses((current) => {
      if (current.includes(status)) {
        return current.filter((item) => item !== status);
      }
      return [...current, status];
    });
  }, []);

  const resetFilters = useCallback(() => {
    setSelectedStatuses([]);
    setJobType("");
  }, []);

  const isInitialLoading = jobsQuery.isLoading && !jobsQuery.data;
  const refreshing = jobsQuery.isRefetching;

  return (
    <View style={styles.container}>
      {jobsQuery.error ? (
        <View style={styles.errorContainer}>
          <Text style={styles.errorText}>İş listesi yüklenemedi.</Text>
          <TouchableOpacity
            style={styles.secondaryButton}
            onPress={() => {
              void jobsQuery.refetch();
            }}
          >
            <Text style={styles.secondaryButtonText}>Tekrar dene</Text>
          </TouchableOpacity>
        </View>
      ) : null}

      <FlatList
        data={jobsQuery.data ?? []}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.listContent}
        style={styles.list}
        renderItem={({ item }) => (
          <JobRow
            job={item}
            onPress={() => {
              setSelectedJobId(item.id);
            }}
          />
        )}
        refreshControl={
          <RefreshControl
            tintColor="#60a5fa"
            refreshing={refreshing}
            onRefresh={() => {
              void jobsQuery.refetch();
            }}
          />
        }
        ListHeaderComponent={() => (
          <View style={styles.filtersContainer}>
            <Text style={styles.filtersTitle}>Filtreler</Text>
            <View style={styles.filterGroup}>
              <Text style={styles.filterGroupTitle}>Durum</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chipScroll}>
                <View style={styles.chipRow}>
                  {STATUS_OPTIONS.map((option) => (
                    <FilterChip
                      key={option.value}
                      label={option.label}
                      selected={selectedStatuses.includes(option.value)}
                      onPress={() => toggleStatus(option.value)}
                    />
                  ))}
                </View>
              </ScrollView>
            </View>

            <View style={styles.filterGroup}>
              <Text style={styles.filterGroupTitle}>İş tipi</Text>
              <TextInput
                style={styles.searchInput}
                placeholder="Ör. collect, export"
                placeholderTextColor="#64748b"
                value={jobType}
                onChangeText={setJobType}
              />
            </View>

            <TouchableOpacity style={styles.secondaryButton} onPress={resetFilters}>
              <Text style={styles.secondaryButtonText}>Filtreleri Sıfırla</Text>
            </TouchableOpacity>
          </View>
        )}
        ListEmptyComponent={
          isInitialLoading ? (
            <View style={styles.emptyState}>
              {[...Array(3)].map((_, index) => (
                <JobSkeleton key={`job-skeleton-${index}`} />
              ))}
            </View>
          ) : (
            <View style={styles.emptyState}>
              <Text style={styles.emptyText}>Kuyrukta veya geçmişte iş bulunamadı.</Text>
            </View>
          )
        }
      />

      <JobDetailModal
        jobId={selectedJobId}
        onClose={() => {
          setSelectedJobId(null);
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0f172a",
  },
  list: {
    flex: 1,
  },
  listContent: {
    padding: 24,
    gap: 16,
    paddingBottom: 80,
  },
  filtersContainer: {
    gap: 16,
    backgroundColor: "#111c2d",
    padding: 20,
    borderRadius: 18,
  },
  filtersTitle: {
    color: "#f8fafc",
    fontSize: 20,
    fontWeight: "700",
  },
  filterGroup: {
    gap: 8,
  },
  filterGroupTitle: {
    color: "#cbd5f5",
    fontSize: 14,
    fontWeight: "600",
  },
  chipRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  chipScroll: {
    marginHorizontal: -4,
  },
  chip: {
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderWidth: 1,
  },
  chipSelected: {
    backgroundColor: "#60a5fa",
    borderColor: "#60a5fa",
  },
  chipUnselected: {
    backgroundColor: "transparent",
    borderColor: "#1f2937",
  },
  chipText: {
    fontSize: 13,
    color: "#94a3b8",
    fontWeight: "600",
  },
  chipTextSelected: {
    color: "#0f172a",
  },
  searchInput: {
    backgroundColor: "#1e293b",
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 10,
    color: "#f8fafc",
    fontSize: 16,
  },
  jobCard: {
    backgroundColor: "#1e293b",
    borderRadius: 16,
    padding: 20,
    gap: 8,
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
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
    overflow: "hidden",
    fontWeight: "600",
    fontSize: 12,
  },
  statusqueued: {
    backgroundColor: "#facc15",
    color: "#0f172a",
  },
  statusrunning: {
    backgroundColor: "#38bdf8",
    color: "#0f172a",
  },
  statuscompleted: {
    backgroundColor: "#22c55e",
    color: "#0f172a",
  },
  statusfailed: {
    backgroundColor: "#f87171",
    color: "#0f172a",
  },
  statuscancelled: {
    backgroundColor: "#94a3b8",
    color: "#0f172a",
  },
  statusDefault: {
    backgroundColor: "#64748b",
    color: "#0f172a",
  },
  jobMeta: {
    color: "#94a3b8",
    fontSize: 14,
  },
  jobError: {
    color: "#f87171",
    fontSize: 14,
  },
  skeletonLineWide: {
    height: 16,
    backgroundColor: "#273548",
    borderRadius: 8,
    width: "60%",
  },
  skeletonLine: {
    height: 12,
    backgroundColor: "#273548",
    borderRadius: 8,
    width: "80%",
  },
  skeletonProgress: {
    height: 6,
    backgroundColor: "#273548",
    borderRadius: 999,
    width: "100%",
  },
  progressRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  progressBarTrack: {
    flex: 1,
    height: 6,
    borderRadius: 999,
    backgroundColor: "#273548",
    overflow: "hidden",
  },
  progressBarFill: {
    height: 6,
    backgroundColor: "#60a5fa",
  },
  progressText: {
    color: "#f8fafc",
    fontSize: 12,
    fontWeight: "600",
  },
  emptyState: {
    paddingVertical: 40,
    alignItems: "center",
    gap: 16,
  },
  emptyText: {
    color: "#94a3b8",
    fontSize: 16,
    textAlign: "center",
  },
  modalContainer: {
    flex: 1,
    backgroundColor: "#0f172a",
  },
  modalLoading: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  modalError: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  modalContent: {
    padding: 24,
    gap: 16,
  },
  modalTitle: {
    color: "#f8fafc",
    fontSize: 24,
    fontWeight: "700",
  },
  modalMeta: {
    color: "#94a3b8",
    fontSize: 14,
  },
  modalSection: {
    gap: 12,
  },
  modalSectionTitle: {
    color: "#e2e8f0",
    fontSize: 18,
    fontWeight: "600",
  },
  payloadText: {
    backgroundColor: "#1e293b",
    borderRadius: 12,
    padding: 12,
    color: "#e2e8f0",
    fontFamily: "monospace",
  },
  helperText: {
    color: "#64748b",
    fontSize: 13,
  },
  logLine: {
    flexDirection: "row",
    gap: 12,
    backgroundColor: "#1e293b",
    borderRadius: 14,
    padding: 12,
  },
  logLevel: {
    fontWeight: "700",
    fontSize: 12,
    width: 70,
  },
  logBody: {
    flex: 1,
    gap: 4,
  },
  logMessage: {
    color: "#f8fafc",
    fontSize: 14,
  },
  logTimestamp: {
    color: "#94a3b8",
    fontSize: 12,
  },
  logContext: {
    color: "#cbd5f5",
    fontSize: 12,
    fontFamily: "monospace",
  },
  destructiveButton: {
    backgroundColor: "#f87171",
    paddingVertical: 14,
    borderRadius: 14,
    alignItems: "center",
  },
  destructiveButtonText: {
    color: "#0f172a",
    fontWeight: "700",
    fontSize: 16,
  },
  secondaryButton: {
    backgroundColor: "#1e293b",
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 14,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#334155",
  },
  secondaryButtonText: {
    color: "#f8fafc",
    fontWeight: "600",
  },
  modalCloseButton: {
    padding: 16,
    alignItems: "center",
    borderTopWidth: 1,
    borderColor: "#1f2a3b",
  },
  modalCloseText: {
    color: "#60a5fa",
    fontSize: 16,
    fontWeight: "600",
  },
  errorContainer: {
    paddingHorizontal: 24,
    paddingTop: 16,
    gap: 12,
  },
  errorText: {
    color: "#f87171",
    fontSize: 16,
  },
});
