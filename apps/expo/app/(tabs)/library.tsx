import { useInfiniteQuery, useMutation, useQuery } from "@tanstack/react-query";
import { useCallback, useMemo, useState } from "react";
import {
  Alert,
  Modal,
  RefreshControl,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  View,
} from "react-native";

import { HeroSection, LibraryGrid, FilterPanel, Text, Button } from "../../components";

import { useDebouncedValue } from "../../lib/hooks";
import { useAuth } from "../../providers/AuthProvider";
import type {
  JobModel,
  LibraryItemModel,
  LibraryItemType,
  LibraryListModel,
  LibraryMetricsModel,
  LibrarySortOption,
  StreamVariantModel,
} from "../../types/api";

const PAGE_SIZE = 25;
const SORT_OPTIONS: { value: LibrarySortOption; label: string }[] = [
  { value: "updated_desc", label: "Güncel ↓" },
  { value: "updated_asc", label: "Güncel ↑" },
  { value: "title_asc", label: "Başlık A-Z" },
  { value: "title_desc", label: "Başlık Z-A" },
  { value: "year_desc", label: "Yıl ↓" },
  { value: "year_asc", label: "Yıl ↑" },
];

interface LibraryDetailModalProps {
  itemId: string | null;
  onClose: () => void;
}

function LibraryDetailModal({ itemId, onClose }: LibraryDetailModalProps) {
  const { session } = useAuth();

  const itemQuery = useQuery({
    queryKey: ["library-item", itemId, session?.baseUrl],
    queryFn: () => session!.client.get<LibraryItemModel>(`/library/${itemId}`),
    enabled: Boolean(session && itemId),
  });

  const regenerateMutation = useMutation({
    mutationFn: () =>
      session!.client.post<JobModel>("/jobs/run", {
        type: "strm_regenerate",
        payload: { item_id: itemId },
      }),
    onSuccess: (job) => {
      // Start polling for job completion
      const pollJobStatus = async () => {
        try {
          const jobStatus = await session!.client.get<JobModel>(`/jobs/${job.id}`);
          if (jobStatus.status === "completed") {
            Alert.alert("STRM Oluşturuldu", "STRM dosyası başarıyla oluşturuldu!");
          } else if (jobStatus.status === "failed") {
            Alert.alert("STRM Oluşturulamadı", "STRM dosyası oluşturulurken hata oluştu.");
          } else if (jobStatus.status === "running" || jobStatus.status === "queued") {
            // Continue polling
            setTimeout(pollJobStatus, 2000);
          }
        } catch (error) {
          console.error("Job status polling error:", error);
        }
      };
      
      Alert.alert("İş Başlatıldı", "STRM dosyası oluşturuluyor...");
      setTimeout(pollJobStatus, 2000);
    },
    onError: (error) => {
      const errorMessage = error instanceof Error ? error.message : "Bilinmeyen hata";
      Alert.alert("STRM Oluşturulamadı", `STRM dosyası oluşturulurken hata oluştu: ${errorMessage}`);
    },
  });

  const playbackMutation = useMutation({
    mutationFn: async (variant: StreamVariantModel) => {
      if (!session) {
        throw new Error("Session missing");
      }
      console.log("Testing playback for URL:", variant.url);
      return session.client.get<unknown>(variant.url);
    },
    onSuccess: (data) => {
      console.log("Playback response:", data);
      if (data === undefined || data === null) {
        Alert.alert("Playback tamamlandı", "Sunucudan yanıt alınmadı ancak istek başarıyla gönderildi.");
        return;
      }
      const normalized = typeof data === "string" ? data : JSON.stringify(data, null, 2);
      Alert.alert("Playback başarılı", normalized);
    },
    onError: (error) => {
      console.error("Playback error:", error);
      const errorMessage = error instanceof Error ? error.message : "Bilinmeyen hata";
      Alert.alert("Playback başarısız", `Akış testi tamamlanamadı: ${errorMessage}`);
    },
  });

  const handleTestPlayback = useCallback(
    (variant: StreamVariantModel) => {
      console.log("Test playback button clicked for variant:", variant);
      if (playbackMutation.isPending) {
        console.log("Playback mutation is already pending, ignoring click");
        return;
      }
      console.log("Starting playback mutation...");
      playbackMutation.mutate(variant);
    },
    [playbackMutation],
  );

  if (!itemId) {
    return null;
  }

  if (itemQuery.isLoading) {
    return (
      <Modal visible animationType="slide" presentationStyle="pageSheet">
        <View style={styles.modalContainer}>
          <View style={styles.modalLoading}>
            <Text variant="body" color="secondary">Yükleniyor...</Text>
          </View>
        </View>
      </Modal>
    );
  }

  if (itemQuery.error || !itemQuery.data) {
    return (
      <Modal visible animationType="slide" presentationStyle="pageSheet">
        <View style={styles.modalContainer}>
          <View style={styles.modalError}>
            <Text variant="body" color="error">Öğe yüklenemedi.</Text>
            <TouchableOpacity style={styles.modalCloseButton} onPress={onClose}>
              <Text variant="body" color="accent">Kapat</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    );
  }

  const item = itemQuery.data;

  return (
    <Modal visible animationType="slide" presentationStyle="pageSheet">
      <View style={styles.modalContainer}>
        <ScrollView style={styles.modalContent}>
          <Text variant="h2" style={styles.modalTitle}>{item.title}</Text>
          <Text variant="body" color="secondary" style={styles.modalMeta}>
            {item.year ?? "Yıl yok"} · {item.site} · {item.item_type}
          </Text>

          {item.variants.length > 0 && (
            <View style={styles.variantsSection}>
              <Text variant="h3" style={styles.sectionTitle}>Akış Varyantları</Text>
              {item.variants.map((variant, index) => (
                <View key={index} style={styles.variantItem}>
                  <View style={styles.variantInfo}>
                    <Text variant="label" color="secondary">
                      {variant.source} - {variant.quality}
                    </Text>
                    <Text variant="bodySmall" color="muted" numberOfLines={1}>
                      {variant.url}
                    </Text>
                  </View>
                  <View style={styles.variantActions}>
                    <Button
                      title="Test et"
                      variant="secondary"
                      size="sm"
                      onPress={() => handleTestPlayback(variant)}
                      loading={playbackMutation.isPending}
                    />
                  </View>
                </View>
              ))}
            </View>
          )}

          <View style={styles.modalActions}>
            <Button
              title="STRM Yeniden Oluştur"
              variant="primary"
              onPress={() => regenerateMutation.mutate()}
              loading={regenerateMutation.isPending}
            />
          </View>
        </ScrollView>

        <TouchableOpacity style={styles.modalCloseButton} onPress={onClose}>
          <Text variant="body" color="accent">Kapat</Text>
        </TouchableOpacity>
      </View>
    </Modal>
  );
}

export default function LibraryScreen() {
  const { session } = useAuth();
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [selectedSites, setSelectedSites] = useState<string[]>([]);
  const [selectedType, setSelectedType] = useState<LibraryItemType | "all">("all");
  const [sort, setSort] = useState<LibrarySortOption>("updated_desc");

  const debouncedSearch = useDebouncedValue(search, 300);

  const metricsQuery = useQuery({
    queryKey: ["library-metrics", session?.baseUrl],
    queryFn: () => session!.client.get<LibraryMetricsModel>("/library/metrics"),
    enabled: Boolean(session),
    staleTime: 30_000,
  });

  const libraryQuery = useInfiniteQuery({
    queryKey: [
      "library",
      session?.baseUrl,
      debouncedSearch,
      selectedSites,
      selectedType,
      sort,
    ],
    queryFn: ({ pageParam = 1 }) => {
      const params = new URLSearchParams();
      params.set("page", pageParam.toString());
      params.set("page_size", PAGE_SIZE.toString());
      if (debouncedSearch) params.set("query", debouncedSearch);
      if (selectedSites.length > 0) {
        selectedSites.forEach(site => params.append("site", site));
      }
      if (selectedType !== "all") params.set("item_type", selectedType);
      params.set("sort", sort);
      
      return session!.client.get<LibraryListModel>(`/library?${params.toString()}`);
    },
    enabled: Boolean(session),
    initialPageParam: 1,
    getNextPageParam: (lastPage: LibraryListModel) => {
      const totalPages = Math.ceil(lastPage.total / PAGE_SIZE);
      return lastPage.page < totalPages ? lastPage.page + 1 : undefined;
    },
  });

  const items = useMemo(() => {
    return libraryQuery.data?.pages.flatMap((page) => page.items) ?? [];
  }, [libraryQuery.data]);

  const isInitialLoading = libraryQuery.isLoading && !libraryQuery.data;
  const refreshing = libraryQuery.isRefetching && !libraryQuery.isFetchingNextPage;

  // Featured items for hero section
  const featuredItems = useMemo(() => {
    return items.slice(0, 3); // İlk 3 öğeyi featured olarak kullan
  }, [items]);

  const toggleSite = useCallback(
    (site: string) => {
      setSelectedSites((current) => {
        if (current.includes(site)) {
          return current.filter((item) => item !== site);
        }
        return [...current, site];
      });
    },
    [],
  );

  const resetFilters = useCallback(() => {
    setSelectedSites([]);
    setSelectedType("all");
    setSearch("");
    setSort("updated_desc");
  }, []);

  const availableSites = useMemo(() => {
    return Object.keys(metricsQuery.data?.site_counts ?? {});
  }, [metricsQuery.data]);

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text variant="h1" align="center">Kütüphane</Text>
        <Text variant="body" color="secondary" align="center">
          {metricsQuery.data?.total ?? 0} öğe · {availableSites.length} site
        </Text>
      </View>

      {/* Hero Section */}
      <HeroSection featuredItems={featuredItems} />

      {/* Filter Panel */}
      <FilterPanel
        search={search}
        onSearchChange={setSearch}
        selectedSites={selectedSites}
        availableSites={availableSites}
        onSiteToggle={toggleSite}
        selectedType={selectedType}
        onTypeChange={(type: string) => setSelectedType(type as LibraryItemType | "all")}
        onResetFilters={resetFilters}
      />

      {/* Library Grid */}
      <LibraryGrid
        items={items}
        onItemPress={(item: LibraryItemModel) => setSelectedItemId(item.id)}
        onLoadMore={() => libraryQuery.fetchNextPage()}
        isLoading={isInitialLoading}
        isLoadingMore={libraryQuery.isFetchingNextPage}
        emptyMessage="Eşleşen kütüphane öğesi bulunamadı."
      />

      {/* Detail Modal */}
      <LibraryDetailModal
        itemId={selectedItemId}
        onClose={() => setSelectedItemId(null)}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#000000",
  },
  header: {
    paddingHorizontal: 24,
    paddingTop: 20,
    paddingBottom: 10,
    gap: 6,
  },
  modalContainer: {
    flex: 1,
    backgroundColor: "#000000",
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
  },
  modalMeta: {
    color: "#94a3b8",
  },
  variantsSection: {
    gap: 12,
  },
  sectionTitle: {
    color: "#f8fafc",
  },
  variantItem: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: 12,
    backgroundColor: "#111111",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "#333333",
  },
  variantInfo: {
    flex: 1,
    gap: 4,
  },
  variantActions: {
    marginLeft: 12,
  },
  modalActions: {
    gap: 12,
  },
  modalCloseButton: {
    padding: 16,
    alignItems: "center",
    borderTopWidth: 1,
    borderColor: "#333333",
  },
});
