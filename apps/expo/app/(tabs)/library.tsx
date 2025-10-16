import { useInfiniteQuery, useMutation, useQuery } from "@tanstack/react-query";
import { useCallback, useMemo, useState } from "react";
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

import { useDebouncedValue } from "@/lib/hooks";
import { useAuth } from "@/providers/AuthProvider";
import type {
  JobModel,
  LibraryItemModel,
  LibraryItemType,
  LibraryListModel,
  LibraryMetricsModel,
  LibrarySortOption,
  StreamVariantModel,
} from "@/types/api";

const PAGE_SIZE = 25;
const SORT_OPTIONS: { value: LibrarySortOption; label: string }[] = [
  { value: "updated_desc", label: "Güncel ↓" },
  { value: "updated_asc", label: "Güncel ↑" },
  { value: "title_asc", label: "Başlık A-Z" },
  { value: "title_desc", label: "Başlık Z-A" },
  { value: "year_desc", label: "Yıl ↓" },
  { value: "year_asc", label: "Yıl ↑" },
];

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

function SkeletonCard() {
  return (
    <View style={styles.skeletonCard}>
      <View style={styles.skeletonTitle} />
      <View style={styles.skeletonLine} />
      <View style={styles.skeletonLine} />
      <View style={styles.skeletonLineShort} />
    </View>
  );
}

function LibraryItemCard({ item, onPress }: { item: LibraryItemModel; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={styles.itemCard}>
      <View style={styles.itemHeader}>
        <Text style={styles.itemTitle}>{item.title}</Text>
        <Text style={styles.itemBadge}>{item.item_type.toUpperCase()}</Text>
      </View>
      <Text style={styles.itemMeta}>
        {item.site} · {item.year ?? "Yıl yok"}
      </Text>
      {item.tmdb_id ? (
        <Text style={styles.itemMeta}>TMDB: {item.tmdb_id}</Text>
      ) : (
        <Text style={styles.itemMeta}>TMDB eşleşmesi yok</Text>
      )}
      <Text style={styles.itemMeta}>Kaynaklar: {item.variants.length}</Text>
    </Pressable>
  );
}

interface LibraryDetailModalProps {
  itemId: string | null;
  onClose: () => void;
}

function LibraryDetailModal({ itemId, onClose }: LibraryDetailModalProps) {
  const { session } = useAuth();
  const isVisible = Boolean(itemId);

  const detailQuery = useQuery({
    queryKey: ["library", "detail", session?.baseUrl, itemId],
    queryFn: () => session!.client.get<LibraryItemModel>(`/library/${itemId}`),
    enabled: Boolean(session && itemId),
  });

  const regenerateMutation = useMutation({
    mutationFn: async () => {
      if (!session || !itemId) {
        throw new Error("Session missing");
      }

      return session.client.post<JobModel>("/jobs/run", {
        type: "strm_regenerate",
        payload: { library_item_id: itemId },
      });
    },
    onSuccess: (job) => {
      Alert.alert("İş kuyruğa eklendi", `Job ID: ${job.id}`);
    },
    onError: () => {
      Alert.alert("İş başarısız", "STRM yeniden oluşturma isteği gönderilemedi.");
    },
  });

  const playbackMutation = useMutation({
    mutationFn: async (variant: StreamVariantModel) => {
      if (!session) {
        throw new Error("Session missing");
      }

      return session.client.get<unknown>(variant.url);
    },
    onSuccess: (data) => {
      if (data === undefined || data === null) {
        Alert.alert("Playback tamamlandı", "Sunucudan yanıt alınmadı ancak istek başarıyla gönderildi.");
        return;
      }

      const normalized = typeof data === "string" ? data : JSON.stringify(data, null, 2);
      Alert.alert("Playback başarılı", normalized);
    },
    onError: () => {
      Alert.alert("Playback başarısız", "Akış testi tamamlanamadı.");
    },
  });

  const handleRegenerate = useCallback(() => {
    if (!itemId || regenerateMutation.isPending) {
      return;
    }

    regenerateMutation.mutate();
  }, [itemId, regenerateMutation]);

  const handleTestPlayback = useCallback(
    (variant: StreamVariantModel) => {
      if (playbackMutation.isPending) {
        return;
      }

      playbackMutation.mutate(variant);
    },
    [playbackMutation],
  );

  return (
    <Modal visible={isVisible} animationType="slide" onRequestClose={onClose}>
      <View style={styles.modalContainer}>
        {detailQuery.isLoading ? (
          <View style={styles.modalLoading}>
            <ActivityIndicator size="large" color="#60a5fa" />
          </View>
        ) : detailQuery.error ? (
          <View style={styles.modalError}>
            <Text style={styles.errorText}>Öğe detayları yüklenemedi.</Text>
          </View>
        ) : detailQuery.data ? (
          <ScrollView contentContainerStyle={styles.modalContent}>
            <Text style={styles.modalTitle}>{detailQuery.data.title}</Text>
            <Text style={styles.modalMeta}>
              Tür: {detailQuery.data.item_type} · Site: {detailQuery.data.site}
            </Text>
            <Text style={styles.modalMeta}>Yıl: {detailQuery.data.year ?? "Bilinmiyor"}</Text>
            <Text style={styles.modalMeta}>
              TMDB: {detailQuery.data.tmdb_id ?? "Eşleşme yok"}
            </Text>

            <View style={styles.modalSection}>
              <Text style={styles.modalSectionTitle}>Akış varyantları</Text>
              {detailQuery.data.variants.length === 0 ? (
                <Text style={styles.emptyText}>Akış varyantı bulunamadı.</Text>
              ) : (
                detailQuery.data.variants.map((variant) => (
                  <View key={`${variant.source}-${variant.quality}`} style={styles.variantRow}>
                    <View style={styles.variantInfo}>
                      <Text style={styles.variantTitle}>{variant.source}</Text>
                      <Text style={styles.variantMeta}>{variant.quality}</Text>
                    </View>
                    <TouchableOpacity
                      style={styles.secondaryButton}
                      onPress={() => {
                        handleTestPlayback(variant);
                      }}
                      disabled={playbackMutation.isPending}
                    >
                      {playbackMutation.isPending ? (
                        <ActivityIndicator color="#f8fafc" />
                      ) : (
                        <Text style={styles.secondaryButtonText}>Test et</Text>
                      )}
                    </TouchableOpacity>
                  </View>
                ))
              )}
            </View>

            <View style={styles.modalActions}>
              <TouchableOpacity
                style={styles.primaryButton}
                onPress={() => {
                  handleRegenerate();
                }}
                disabled={regenerateMutation.isPending}
              >
                {regenerateMutation.isPending ? (
                  <ActivityIndicator color="#0f172a" />
                ) : (
                  <Text style={styles.primaryButtonText}>STRM Yeniden Oluştur</Text>
                )}
              </TouchableOpacity>
            </View>
          </ScrollView>
        ) : null}

        <TouchableOpacity style={styles.modalCloseButton} onPress={onClose}>
          <Text style={styles.modalCloseText}>Kapat</Text>
        </TouchableOpacity>
      </View>
    </Modal>
  );
}

export default function LibraryScreen() {
  const { session } = useAuth();
  const [search, setSearch] = useState("");
  const [selectedSites, setSelectedSites] = useState<string[]>([]);
  const [selectedType, setSelectedType] = useState<LibraryItemType | "all">("all");
  const [tmdbFilter, setTmdbFilter] = useState<"all" | "with" | "without">("all");
  const [year, setYear] = useState("");
  const [yearMin, setYearMin] = useState("");
  const [yearMax, setYearMax] = useState("");
  const [sort, setSort] = useState<LibrarySortOption>("updated_desc");
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);

  const debouncedSearch = useDebouncedValue(search, 400);

  const metricsQuery = useQuery({
    queryKey: ["library", "metrics", session?.baseUrl],
    queryFn: () => session!.client.get<LibraryMetricsModel>("/library/metrics"),
    enabled: Boolean(session),
    staleTime: 60_000,
  });

  const siteOptions = useMemo(() => {
    if (!metricsQuery.data?.site_counts) {
      return [] as string[];
    }

    return Object.keys(metricsQuery.data.site_counts).sort();
  }, [metricsQuery.data]);

  const filterEntries = useMemo(() => {
    const entries: [string, string][] = [];

    const trimmedQuery = debouncedSearch.trim();
    if (trimmedQuery) {
      entries.push(["query", trimmedQuery]);
    }

    const normalizedSites = [...selectedSites].sort();
    for (const site of normalizedSites) {
      entries.push(["site", site]);
    }

    if (selectedType !== "all") {
      entries.push(["item_type", selectedType]);
    }

    if (tmdbFilter === "with") {
      entries.push(["has_tmdb", "true"]);
    } else if (tmdbFilter === "without") {
      entries.push(["has_tmdb", "false"]);
    }

    const normalizedYear = parseInt(year, 10);
    if (!Number.isNaN(normalizedYear)) {
      entries.push(["year", String(normalizedYear)]);
    }

    const minYear = parseInt(yearMin, 10);
    if (!Number.isNaN(minYear)) {
      entries.push(["year_min", String(minYear)]);
    }

    const maxYear = parseInt(yearMax, 10);
    if (!Number.isNaN(maxYear)) {
      entries.push(["year_max", String(maxYear)]);
    }

    entries.push(["sort", sort]);
    entries.push(["page_size", String(PAGE_SIZE)]);

    return entries;
  }, [debouncedSearch, selectedSites, selectedType, tmdbFilter, year, yearMin, yearMax, sort]);

  const libraryQuery = useInfiniteQuery({
    queryKey: ["library", "list", session?.baseUrl, filterEntries],
    queryFn: async ({ pageParam = 1 }) => {
      const params = new URLSearchParams(filterEntries);
      params.set("page", String(pageParam));
      return session!.client.get<LibraryListModel>(`/library?${params.toString()}`);
    },
    initialPageParam: 1,
    getNextPageParam: (lastPage) => {
      const totalPages = Math.ceil(lastPage.total / lastPage.page_size) || 1;
      return lastPage.page < totalPages ? lastPage.page + 1 : undefined;
    },
    enabled: Boolean(session),
  });

  const items = useMemo(() => {
    return libraryQuery.data?.pages.flatMap((page) => page.items) ?? [];
  }, [libraryQuery.data]);

  const isInitialLoading = libraryQuery.isLoading && !libraryQuery.data;
  const refreshing = libraryQuery.isRefetching && !libraryQuery.isFetchingNextPage;

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
    setTmdbFilter("all");
    setYear("");
    setYearMin("");
    setYearMax("");
    setSort("updated_desc");
  }, []);

  return (
    <View style={styles.container}>
      {libraryQuery.error ? (
        <View style={styles.errorContainer}>
          <Text style={styles.errorText}>Kütüphane yüklenemedi.</Text>
          <TouchableOpacity
            style={styles.secondaryButton}
            onPress={() => {
              void libraryQuery.refetch();
            }}
          >
            <Text style={styles.secondaryButtonText}>Tekrar dene</Text>
          </TouchableOpacity>
        </View>
      ) : null}

      <FlatList
        data={items}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.listContent}
        style={styles.list}
        renderItem={({ item }) => (
          <LibraryItemCard
            item={item}
            onPress={() => {
              setSelectedItemId(item.id);
            }}
          />
        )}
        refreshControl={
          <RefreshControl
            tintColor="#60a5fa"
            refreshing={refreshing}
            onRefresh={() => {
              void libraryQuery.refetch();
            }}
          />
        }
        onEndReached={() => {
          if (libraryQuery.hasNextPage && !libraryQuery.isFetchingNextPage) {
            void libraryQuery.fetchNextPage();
          }
        }}
        onEndReachedThreshold={0.5}
        ListHeaderComponent={() => (
          <View style={styles.filtersContainer}>
            <Text style={styles.filtersTitle}>Filtreler</Text>
            <TextInput
              style={styles.searchInput}
              placeholder="Başlığa göre ara"
              placeholderTextColor="#64748b"
              value={search}
              onChangeText={setSearch}
            />

            <View style={styles.filterGroup}>
              <Text style={styles.filterGroupTitle}>Tip</Text>
              <View style={styles.chipRow}>
                <FilterChip
                  label="Hepsi"
                  selected={selectedType === "all"}
                  onPress={() => setSelectedType("all")}
                />
                <FilterChip
                  label="Filmler"
                  selected={selectedType === "movie"}
                  onPress={() => setSelectedType("movie")}
                />
                <FilterChip
                  label="Bölümler"
                  selected={selectedType === "episode"}
                  onPress={() => setSelectedType("episode")}
                />
              </View>
            </View>

            <View style={styles.filterGroup}>
              <Text style={styles.filterGroupTitle}>TMDB</Text>
              <View style={styles.chipRow}>
                <FilterChip
                  label="Hepsi"
                  selected={tmdbFilter === "all"}
                  onPress={() => setTmdbFilter("all")}
                />
                <FilterChip
                  label="Eşleşen"
                  selected={tmdbFilter === "with"}
                  onPress={() => setTmdbFilter("with")}
                />
                <FilterChip
                  label="Eksik"
                  selected={tmdbFilter === "without"}
                  onPress={() => setTmdbFilter("without")}
                />
              </View>
            </View>

            <View style={styles.filterGroup}>
              <Text style={styles.filterGroupTitle}>Siteler</Text>
              {metricsQuery.isLoading ? (
                <ActivityIndicator color="#60a5fa" />
              ) : metricsQuery.error ? (
                <Text style={styles.helperText}>Site verisi yüklenemedi.</Text>
              ) : siteOptions.length === 0 ? (
                <Text style={styles.helperText}>Site verisi bulunmuyor.</Text>
              ) : (
                <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chipScroll}>
                  <View style={styles.chipRow}>
                    {siteOptions.map((site) => (
                      <FilterChip
                        key={site}
                        label={site}
                        selected={selectedSites.includes(site)}
                        onPress={() => toggleSite(site)}
                      />
                    ))}
                  </View>
                </ScrollView>
              )}
            </View>

            <View style={styles.filterGroup}>
              <Text style={styles.filterGroupTitle}>Yıl</Text>
              <View style={styles.yearRow}>
                <TextInput
                  style={styles.yearInput}
                  placeholder="Tam yıl"
                  placeholderTextColor="#64748b"
                  keyboardType="numeric"
                  value={year}
                  onChangeText={setYear}
                />
                <TextInput
                  style={styles.yearInput}
                  placeholder="En erken"
                  placeholderTextColor="#64748b"
                  keyboardType="numeric"
                  value={yearMin}
                  onChangeText={setYearMin}
                />
                <TextInput
                  style={styles.yearInput}
                  placeholder="En geç"
                  placeholderTextColor="#64748b"
                  keyboardType="numeric"
                  value={yearMax}
                  onChangeText={setYearMax}
                />
              </View>
            </View>

            <View style={styles.filterGroup}>
              <Text style={styles.filterGroupTitle}>Sıralama</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chipScroll}>
                <View style={styles.chipRow}>
                  {SORT_OPTIONS.map((option) => (
                    <FilterChip
                      key={option.value}
                      label={option.label}
                      selected={sort === option.value}
                      onPress={() => setSort(option.value)}
                    />
                  ))}
                </View>
              </ScrollView>
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
                <SkeletonCard key={`skeleton-${index}`} />
              ))}
            </View>
          ) : (
            <View style={styles.emptyState}>
              <Text style={styles.emptyText}>Eşleşen kütüphane öğesi bulunamadı.</Text>
            </View>
          )
        }
        ListFooterComponent={
          libraryQuery.isFetchingNextPage ? (
            <View style={styles.footerLoading}>
              <ActivityIndicator color="#60a5fa" />
            </View>
          ) : null
        }
      />

      <LibraryDetailModal
        itemId={selectedItemId}
        onClose={() => {
          setSelectedItemId(null);
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
  itemCard: {
    backgroundColor: "#1e293b",
    borderRadius: 16,
    padding: 20,
    gap: 6,
  },
  itemHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  itemTitle: {
    color: "#f8fafc",
    fontSize: 18,
    fontWeight: "700",
  },
  itemBadge: {
    color: "#0f172a",
    backgroundColor: "#60a5fa",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
    overflow: "hidden",
    fontWeight: "600",
  },
  itemMeta: {
    color: "#94a3b8",
    fontSize: 14,
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
  helperText: {
    color: "#64748b",
    fontSize: 13,
  },
  yearRow: {
    flexDirection: "row",
    gap: 12,
  },
  yearInput: {
    flex: 1,
    backgroundColor: "#1e293b",
    borderRadius: 12,
    paddingHorizontal: 12,
    paddingVertical: 8,
    color: "#f8fafc",
  },
  emptyState: {
    gap: 16,
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 40,
  },
  emptyText: {
    color: "#94a3b8",
    fontSize: 16,
    textAlign: "center",
  },
  skeletonCard: {
    width: "100%",
    backgroundColor: "#1e293b",
    borderRadius: 16,
    padding: 20,
    gap: 12,
  },
  skeletonTitle: {
    height: 18,
    backgroundColor: "#273548",
    borderRadius: 8,
  },
  skeletonLine: {
    height: 12,
    backgroundColor: "#273548",
    borderRadius: 6,
  },
  skeletonLineShort: {
    width: "60%",
    height: 12,
    backgroundColor: "#273548",
    borderRadius: 6,
  },
  footerLoading: {
    paddingVertical: 24,
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
  variantRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: "#1e293b",
    borderRadius: 14,
    padding: 16,
    marginBottom: 8,
  },
  variantInfo: {
    gap: 4,
  },
  variantTitle: {
    color: "#f8fafc",
    fontSize: 16,
    fontWeight: "600",
  },
  variantMeta: {
    color: "#94a3b8",
    fontSize: 13,
  },
  modalActions: {
    gap: 12,
  },
  primaryButton: {
    backgroundColor: "#60a5fa",
    paddingVertical: 14,
    borderRadius: 14,
    alignItems: "center",
  },
  primaryButtonText: {
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
