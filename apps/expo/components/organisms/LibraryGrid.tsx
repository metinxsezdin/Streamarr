import React, { useMemo } from "react";
import {
  FlatList,
  View,
  StyleSheet,
  Platform,
  ActivityIndicator,
} from "react-native";

import { PosterCard } from "../molecules/PosterCard";
import { Text } from "../atoms/Text";
import { colors, spacing } from "../theme";
import type { LibraryItemModel } from "@/types/api";

export interface LibraryGridProps {
  items: LibraryItemModel[];
  onItemPress: (item: LibraryItemModel) => void;
  onLoadMore?: () => void;
  isLoading?: boolean;
  isLoadingMore?: boolean;
  emptyMessage?: string;
}

export function LibraryGrid({
  items,
  onItemPress,
  onLoadMore,
  isLoading = false,
  isLoadingMore = false,
  emptyMessage = "Eşleşen kütüphane öğesi bulunamadı.",
}: LibraryGridProps) {
  // Responsive grid columns
  const numColumns = useMemo(() => {
    if (Platform.OS === 'web') {
      return 10; // Web'de 10 sütun
    }
    return 2; // Mobile'da 2 sütun
  }, []);

  const renderItem = ({ item }: { item: LibraryItemModel }) => (
    <PosterCard
      item={item}
      onPress={() => onItemPress(item)}
    />
  );

  const renderEmptyComponent = () => (
    <View style={styles.emptyState}>
      <Text variant="body" color="secondary" align="center">
        {emptyMessage}
      </Text>
    </View>
  );

  const renderFooterComponent = () => {
    if (!isLoadingMore) return null;
    
    return (
      <View style={styles.footerLoading}>
        <ActivityIndicator color={colors.primary} />
      </View>
    );
  };

  if (isLoading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator color={colors.primary} size="large" />
        <Text variant="body" color="secondary" align="center" style={styles.loadingText}>
          Kütüphane yükleniyor...
        </Text>
      </View>
    );
  }

  return (
    <FlatList
      data={items}
      keyExtractor={(item) => item.id}
      contentContainerStyle={styles.gridContent}
      style={styles.list}
      numColumns={numColumns}
      columnWrapperStyle={numColumns > 1 ? styles.gridRow : undefined}
      renderItem={renderItem}
      onEndReached={onLoadMore}
      onEndReachedThreshold={0.5}
      ListEmptyComponent={renderEmptyComponent}
      ListFooterComponent={renderFooterComponent}
      showsVerticalScrollIndicator={false}
    />
  );
}

const styles = StyleSheet.create({
  list: {
    flex: 1,
  },
  gridContent: {
    padding: Platform.OS === 'web' ? spacing.xxl : spacing.lg,
    paddingBottom: 80,
  },
  gridRow: {
    justifyContent: "space-between",
    marginBottom: spacing.lg,
  },
  emptyState: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    paddingVertical: spacing.xxxl,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    gap: spacing.lg,
  },
  loadingText: {
    marginTop: spacing.md,
  },
  footerLoading: {
    paddingVertical: spacing.xxl,
    alignItems: "center",
  },
});
