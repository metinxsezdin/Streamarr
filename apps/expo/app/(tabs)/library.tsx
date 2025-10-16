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
import type { LibraryItemModel, LibraryListModel } from "@/types/api";

function LibraryItem({ item }: { item: LibraryItemModel }): JSX.Element {
  return (
    <View style={styles.itemCard}>
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
    </View>
  );
}

export default function LibraryScreen(): JSX.Element {
  const { session } = useAuth();

  const query = useQuery({
    queryKey: ["library", session?.baseUrl],
    queryFn: () =>
      session!.client.get<LibraryListModel>("/library?page=1&page_size=25"),
    enabled: Boolean(session),
  });

  const refreshing = query.isRefetching;

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
        <Text style={styles.errorText}>Kütüphane yüklenemedi.</Text>
      </View>
    );
  }

  return (
    <FlatList
      data={query.data?.items ?? []}
      keyExtractor={(item) => item.id}
      contentContainerStyle={styles.listContent}
      style={styles.list}
      refreshControl={
        <RefreshControl
          tintColor="#60a5fa"
          refreshing={refreshing}
          onRefresh={() => {
            void query.refetch();
          }}
        />
      }
      ListEmptyComponent={() => (
        <View style={styles.emptyState}>
          <Text style={styles.emptyText}>Henüz kütüphane öğesi bulunmuyor.</Text>
        </View>
      )}
      renderItem={({ item }) => <LibraryItem item={item} />}
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
