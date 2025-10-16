import { useInfiniteQuery, useMutation, useQuery } from "@tanstack/react-query";
import { useCallback, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Modal,
  Platform,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
  Dimensions,
} from "react-native";
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withSpring,
  withTiming,
  interpolate,
  Extrapolate,
} from "react-native-reanimated";

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
const { width: screenWidth, height: screenHeight } = Dimensions.get("window");
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

// Hero Section Component
function HeroSection({ featuredItems }: { featuredItems: LibraryItemModel[] }) {
  const scrollX = useSharedValue(0);
  
  if (featuredItems.length === 0) return null;

  const heroItem = featuredItems[0]; // İlk öğeyi hero olarak kullan

  return (
    <View style={styles.heroContainer}>
      <Animated.View style={[styles.heroCard, styles.floatingCard]}>
        <View style={styles.heroPoster}>
          <View style={styles.heroPosterPlaceholder}>
            <Text style={styles.heroPosterText}>{heroItem.title.charAt(0)}</Text>
          </View>
          <View style={styles.heroOverlay}>
            <View style={styles.heroBadge}>
              <Text style={styles.heroBadgeText}>ÖNE ÇIKAN</Text>
            </View>
            <View style={styles.heroPlayButton}>
              <Text style={styles.heroPlayText}>▶</Text>
            </View>
          </View>
        </View>
        <View style={styles.heroInfo}>
          <Text style={styles.heroTitle} numberOfLines={2}>
            {heroItem.title}
          </Text>
          <Text style={styles.heroMeta}>
            {heroItem.year ?? "Yıl yok"} · {heroItem.site}
          </Text>
          <Text style={styles.heroDescription}>
            {heroItem.variants.length} farklı kalitede kaynak mevcut
          </Text>
        </View>
      </Animated.View>
    </View>
  );
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
    <View style={styles.skeletonPosterCard}>
      <View style={styles.skeletonPoster} />
      <View style={styles.skeletonPosterInfo}>
        <View style={styles.skeletonLine} />
        <View style={styles.skeletonLineShort} />
      </View>
    </View>
  );
}

function LibraryItemCard({ item, onPress }: { item: LibraryItemModel; onPress: () => void }) {
  const scale = useSharedValue(1);
  const opacity = useSharedValue(1);

  const animatedStyle = useAnimatedStyle(() => {
    return {
      transform: [{ scale: scale.value }],
      opacity: opacity.value,
    };
  });

  const handlePressIn = () => {
    scale.value = withSpring(0.95);
    opacity.value = withTiming(0.8, { duration: 150 });
  };

  const handlePressOut = () => {
    scale.value = withSpring(1);
    opacity.value = withTiming(1, { duration: 150 });
  };

  return (
    <Animated.View style={[styles.posterCard, styles.floatingCard, animatedStyle]}>
      <Pressable 
        onPress={onPress}
        onPressIn={handlePressIn}
        onPressOut={handlePressOut}
        style={styles.posterPressable}
      >
        <View style={styles.posterContainer}>
          {/* Placeholder for poster image - can be replaced with actual poster URL later */}
          <View style={styles.posterPlaceholder}>
            <Text style={styles.posterPlaceholderText}>{item.title.charAt(0)}</Text>
          </View>
          <View style={styles.posterOverlay}>
            <Text style={styles.posterBadge}>{item.item_type.toUpperCase()}</Text>
            {item.variants.length > 0 && (
              <View style={styles.playButton}>
                <Text style={styles.playButtonText}>▶</Text>
              </View>
            )}
          </View>
        </View>
        <View style={styles.posterInfo}>
          <Text style={styles.posterTitle} numberOfLines={2}>
            {item.title}
          </Text>
          <Text style={styles.posterMeta}>
            {item.year ?? "Yıl yok"} · {item.site}
          </Text>
          {item.variants.length > 0 && (
            <Text style={styles.posterSources}>{item.variants.length} kaynak</Text>
          )}
        </View>
      </Pressable>
    </Animated.View>
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
    onError: () => {
      Alert.alert("İş Başarısız", "STRM yeniden oluşturma isteği gönderilemedi.");
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

  const handleRegenerate = useCallback(() => {
    if (!itemId || regenerateMutation.isPending) {
      return;
    }

    regenerateMutation.mutate();
  }, [itemId, regenerateMutation]);

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

  // Responsive grid columns
  const numColumns = useMemo(() => {
    if (Platform.OS === 'web') {
      return 10; // Web'de 10 sütun
    }
    return 2; // Mobile'da 2 sütun
  }, []);

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

  // Featured items for hero section
  const featuredItems = useMemo(() => {
    return items.slice(0, 3); // İlk 3 öğeyi featured olarak kullan
  }, [items]);

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Kütüphane</Text>
        <Text style={styles.subtitle}>
          {metricsQuery.data?.total ?? 0} öğe · {Object.keys(metricsQuery.data?.site_counts ?? {}).length} site
        </Text>
      </View>

      {/* Hero Section */}
      <HeroSection featuredItems={featuredItems} />

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
        contentContainerStyle={styles.gridContent}
        style={styles.list}
        numColumns={numColumns}
        columnWrapperStyle={numColumns > 1 ? styles.gridRow : undefined}
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
              {[...Array(Platform.OS === 'web' ? 30 : 6)].map((_, index) => (
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
  header: {
    paddingHorizontal: Platform.OS === 'web' ? 24 : 16,
    paddingTop: 20,
    paddingBottom: 10,
    gap: 6,
  },
  title: {
    color: "#f8fafc",
    fontSize: Platform.OS === 'web' ? 32 : 28,
    fontWeight: "700",
    textAlign: Platform.OS === 'web' ? 'center' : 'left',
  },
  subtitle: {
    color: "#94a3b8",
    fontSize: Platform.OS === 'web' ? 16 : 14,
    textAlign: Platform.OS === 'web' ? 'center' : 'left',
  },
  list: {
    flex: 1,
  },
  listContent: {
    padding: 24,
    gap: 16,
    paddingBottom: 80,
  },
  gridContent: {
    padding: Platform.OS === 'web' ? 24 : 16,
    paddingBottom: 80,
  },
  gridRow: {
    justifyContent: "space-between",
    marginBottom: 16,
  },
  posterCard: {
    flex: 1,
    marginHorizontal: 2,
    maxWidth: Platform.OS === 'web' ? "9.6%" : "48%", // Web'de 10 sütun, mobile'da 2 sütun
  },
  posterContainer: {
    position: "relative",
    aspectRatio: Platform.OS === 'web' ? 2/3 : 2/3, // Web'de kompakt posterler
    borderRadius: 8,
    overflow: "hidden",
    marginBottom: 6,
  },
  posterPlaceholder: {
    flex: 1,
    backgroundColor: "#1e293b",
    justifyContent: "center",
    alignItems: "center",
  },
  posterPlaceholderText: {
    color: "#60a5fa",
    fontSize: 32,
    fontWeight: "700",
  },
  posterOverlay: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    justifyContent: "space-between",
    padding: 8,
  },
  posterBadge: {
    color: "#0f172a",
    backgroundColor: "#60a5fa",
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    fontSize: 10,
    fontWeight: "600",
    alignSelf: "flex-start",
  },
  playButton: {
    backgroundColor: "rgba(0, 0, 0, 0.7)",
    borderRadius: Platform.OS === 'web' ? 15 : 20,
    width: Platform.OS === 'web' ? 30 : 40,
    height: Platform.OS === 'web' ? 30 : 40,
    justifyContent: "center",
    alignItems: "center",
    alignSelf: "flex-end",
  },
  playButtonText: {
    color: "#f8fafc",
    fontSize: Platform.OS === 'web' ? 12 : 16,
    marginLeft: 2,
  },
  posterInfo: {
    gap: 4,
  },
  posterTitle: {
    color: "#f8fafc",
    fontSize: Platform.OS === 'web' ? 12 : 14,
    fontWeight: "600",
    lineHeight: Platform.OS === 'web' ? 14 : 18,
  },
  posterMeta: {
    color: "#94a3b8",
    fontSize: Platform.OS === 'web' ? 10 : 12,
  },
  posterSources: {
    color: "#60a5fa",
    fontSize: Platform.OS === 'web' ? 9 : 11,
    fontWeight: "500",
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
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
    paddingHorizontal: 16,
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
  skeletonPosterCard: {
    flex: 1,
    marginHorizontal: 2,
    maxWidth: Platform.OS === 'web' ? "9.6%" : "48%",
  },
  skeletonPoster: {
    aspectRatio: Platform.OS === 'web' ? 2/3 : 2/3,
    backgroundColor: "#273548",
    borderRadius: 8,
    marginBottom: 6,
  },
  skeletonPosterInfo: {
    gap: 6,
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
  // Hero Section Styles
  heroContainer: {
    paddingHorizontal: Platform.OS === 'web' ? 24 : 16,
    paddingVertical: 20,
  },
  heroCard: {
    backgroundColor: "#1e293b",
    borderRadius: 20,
    padding: 20,
    flexDirection: Platform.OS === 'web' ? 'row' : 'column',
    alignItems: 'center',
    gap: 20,
  },
  heroPoster: {
    position: "relative",
    aspectRatio: 2/3,
    width: Platform.OS === 'web' ? 200 : 150,
    borderRadius: 16,
    overflow: "hidden",
  },
  heroPosterPlaceholder: {
    flex: 1,
    backgroundColor: "#334155",
    justifyContent: "center",
    alignItems: "center",
  },
  heroPosterText: {
    color: "#f8fafc",
    fontSize: 48,
    fontWeight: "700",
  },
  heroOverlay: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    justifyContent: "space-between",
    padding: 12,
  },
  heroBadge: {
    backgroundColor: "rgba(96, 165, 250, 0.9)",
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    alignSelf: "flex-start",
  },
  heroBadgeText: {
    color: "#0f172a",
    fontSize: 10,
    fontWeight: "700",
  },
  heroPlayButton: {
    backgroundColor: "rgba(0, 0, 0, 0.8)",
    borderRadius: 30,
    width: 60,
    height: 60,
    justifyContent: "center",
    alignItems: "center",
    alignSelf: "flex-end",
  },
  heroPlayText: {
    color: "#f8fafc",
    fontSize: 24,
    marginLeft: 4,
  },
  heroInfo: {
    flex: 1,
    gap: 12,
  },
  heroTitle: {
    color: "#f8fafc",
    fontSize: Platform.OS === 'web' ? 28 : 24,
    fontWeight: "700",
    lineHeight: Platform.OS === 'web' ? 34 : 30,
  },
  heroMeta: {
    color: "#94a3b8",
    fontSize: Platform.OS === 'web' ? 16 : 14,
  },
  heroDescription: {
    color: "#cbd5e1",
    fontSize: Platform.OS === 'web' ? 14 : 12,
    lineHeight: Platform.OS === 'web' ? 20 : 16,
  },
  // Floating Card Effect
  floatingCard: {
    shadowColor: "#000",
    shadowOffset: {
      width: 0,
      height: 8,
    },
    shadowOpacity: 0.25,
    shadowRadius: 16,
    elevation: 12,
  },
  posterPressable: {
    flex: 1,
  },
});
