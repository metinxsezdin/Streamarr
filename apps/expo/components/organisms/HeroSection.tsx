import React from "react";
import { View, StyleSheet, Platform } from "react-native";
import Animated from "react-native-reanimated";

import { Card } from "../atoms/Card";
import { Text } from "../atoms/Text";
import { colors, spacing, borderRadius, shadows } from "../theme";
import type { LibraryItemModel } from "@/types/api";

export interface HeroSectionProps {
  featuredItems: LibraryItemModel[];
}

export function HeroSection({ featuredItems }: HeroSectionProps) {
  if (featuredItems.length === 0) return null;

  const heroItem = featuredItems[0]; // İlk öğeyi hero olarak kullan

  return (
    <View style={styles.heroContainer}>
      <Animated.View style={[styles.heroCard, shadows.lg]}>
        <Card variant="outlined" padding="lg" style={styles.card}>
          <View style={styles.heroContent}>
            <View style={styles.heroPoster}>
              <View style={styles.heroPosterPlaceholder}>
                <Text variant="h1" color="accent">
                  {heroItem.title.charAt(0)}
                </Text>
              </View>
              <View style={styles.heroOverlay}>
                <View style={styles.heroBadge}>
                  <Text variant="labelSmall" color="primary">
                    ÖNE ÇIKAN
                  </Text>
                </View>
                <View style={styles.heroPlayButton}>
                  <Text variant="h3" color="primary">▶</Text>
                </View>
              </View>
            </View>
            <View style={styles.heroInfo}>
              <Text variant="h2" numberOfLines={2} style={styles.heroTitle}>
                {heroItem.title}
              </Text>
              <Text variant="body" color="secondary" style={styles.heroMeta}>
                {heroItem.year ?? "Yıl yok"} · {heroItem.site}
              </Text>
              <Text variant="bodySmall" color="secondary" style={styles.heroDescription}>
                {heroItem.variants.length} farklı kalitede kaynak mevcut
              </Text>
            </View>
          </View>
        </Card>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  heroContainer: {
    paddingHorizontal: Platform.OS === 'web' ? spacing.xxl : spacing.lg,
    paddingVertical: spacing.xl,
  },
  heroCard: {
    borderRadius: borderRadius.xxl,
    overflow: "hidden",
  },
  card: {
    padding: 0,
    backgroundColor: colors.surface,
    borderColor: colors.border,
  },
  heroContent: {
    flexDirection: Platform.OS === 'web' ? 'row' : 'column',
    alignItems: 'center',
    gap: spacing.xl,
  },
  heroPoster: {
    position: "relative",
    aspectRatio: 2/3,
    width: Platform.OS === 'web' ? 200 : 150,
    borderRadius: borderRadius.xl,
    overflow: "hidden",
  },
  heroPosterPlaceholder: {
    flex: 1,
    backgroundColor: colors.surfaceVariant,
    justifyContent: "center",
    alignItems: "center",
  },
  heroOverlay: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    justifyContent: "space-between",
    padding: spacing.md,
  },
  heroBadge: {
    backgroundColor: colors.primary,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.sm,
    alignSelf: "flex-start",
  },
  heroPlayButton: {
    backgroundColor: colors.overlay,
    borderRadius: borderRadius.full,
    width: 60,
    height: 60,
    justifyContent: "center",
    alignItems: "center",
    alignSelf: "flex-end",
  },
  heroInfo: {
    flex: 1,
    gap: spacing.md,
  },
  heroTitle: {
    lineHeight: Platform.OS === 'web' ? 34 : 30,
  },
  heroMeta: {
    fontSize: Platform.OS === 'web' ? 16 : 14,
  },
  heroDescription: {
    lineHeight: Platform.OS === 'web' ? 20 : 16,
  },
});
