import React from "react";
import { View, StyleSheet } from "react-native";

import { Card } from "../atoms/Card";
import { Text } from "../atoms/Text";
import { SearchBar } from "../molecules/SearchBar";
import { FilterChip } from "../molecules/FilterChip";
import { Button } from "../atoms/Button";
import { colors, spacing } from "../theme";

export interface FilterPanelProps {
  search: string;
  onSearchChange: (search: string) => void;
  selectedSites: string[];
  availableSites: string[];
  onSiteToggle: (site: string) => void;
  selectedType: string;
  onTypeChange: (type: string) => void;
  onResetFilters: () => void;
}

export function FilterPanel({
  search,
  onSearchChange,
  selectedSites,
  availableSites,
  onSiteToggle,
  selectedType,
  onTypeChange,
  onResetFilters,
}: FilterPanelProps) {
  const typeOptions = [
    { value: "all", label: "Tümü" },
    { value: "movie", label: "Film" },
    { value: "episode", label: "Dizi" },
  ];

  return (
    <Card variant="outlined" padding="lg" style={styles.container}>
      <Text variant="h3" style={styles.title}>Filtreler</Text>
      
      <SearchBar
        value={search}
        onChangeText={onSearchChange}
        placeholder="Başlığa göre ara"
      />

      <View style={styles.section}>
        <Text variant="label" color="secondary" style={styles.sectionTitle}>
          Tür
        </Text>
        <View style={styles.chipContainer}>
          {typeOptions.map((option) => (
            <FilterChip
              key={option.value}
              label={option.label}
              selected={selectedType === option.value}
              onPress={() => onTypeChange(option.value)}
            />
          ))}
        </View>
      </View>

      {availableSites.length > 0 && (
        <View style={styles.section}>
          <Text variant="label" color="secondary" style={styles.sectionTitle}>
            Site ({selectedSites.length}/{availableSites.length})
          </Text>
          <View style={styles.chipContainer}>
            {availableSites.map((site) => (
              <FilterChip
                key={site}
                label={site}
                selected={selectedSites.includes(site)}
                onPress={() => onSiteToggle(site)}
              />
            ))}
          </View>
        </View>
      )}

      <View style={styles.actions}>
        <Button
          title="Filtreleri Sıfırla"
          variant="secondary"
          size="sm"
          onPress={onResetFilters}
        />
      </View>
    </Card>
  );
}

const styles = StyleSheet.create({
  container: {
    marginHorizontal: spacing.lg,
    marginBottom: spacing.lg,
    gap: spacing.lg,
  },
  title: {
    marginBottom: spacing.sm,
  },
  section: {
    gap: spacing.sm,
  },
  sectionTitle: {
    marginBottom: spacing.xs,
  },
  chipContainer: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
  },
  actions: {
    flexDirection: "row",
    justifyContent: "flex-end",
    marginTop: spacing.sm,
  },
});
