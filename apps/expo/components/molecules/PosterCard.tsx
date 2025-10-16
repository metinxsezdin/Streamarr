import React from "react";
import {
  Pressable,
  View,
  StyleSheet,
  Platform,
} from "react-native";
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withSpring,
  withTiming,
} from "react-native-reanimated";

import { Text } from "../atoms/Text";
import { Card } from "../atoms/Card";
import { colors, spacing, borderRadius, shadows } from "../theme";
import type { LibraryItemModel } from "@/types/api";

export interface PosterCardProps {
  item: LibraryItemModel;
  onPress: () => void;
  size?: "sm" | "md" | "lg";
}

export function PosterCard({ item, onPress, size = "md" }: PosterCardProps) {
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

  const cardStyle = [
    styles.posterCard,
    styles[size],
    Platform.OS === 'web' && styles.webCard,
  ];

  return (
    <Animated.View style={[cardStyle, animatedStyle]}>
      <Card variant="elevated" padding="sm" style={styles.card}>
        <Pressable
          onPress={onPress}
          onPressIn={handlePressIn}
          onPressOut={handlePressOut}
          style={styles.pressable}
        >
          <View style={styles.posterContainer}>
            <View style={styles.posterPlaceholder}>
              <Text variant="h1" color="accent">
                {item.title.charAt(0)}
              </Text>
            </View>
            <View style={styles.posterOverlay}>
              <View style={styles.badge}>
                <Text variant="labelSmall" color="primary">
                  {item.item_type.toUpperCase()}
                </Text>
              </View>
              {item.variants.length > 0 && (
                <View style={styles.playButton}>
                  <Text variant="body" color="primary">▶</Text>
                </View>
              )}
            </View>
          </View>
          <View style={styles.posterInfo}>
            <Text variant="label" numberOfLines={2} style={styles.title}>
              {item.title}
            </Text>
            <Text variant="bodySmall" color="secondary">
              {item.year ?? "Yıl yok"} · {item.site}
            </Text>
            {item.variants.length > 0 && (
              <Text variant="labelSmall" color="accent">
                {item.variants.length} kaynak
              </Text>
            )}
          </View>
        </Pressable>
      </Card>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  posterCard: {
    flex: 1,
    marginHorizontal: spacing.xs,
  },
  webCard: {
    maxWidth: "9.6%", // 10 columns
  },
  card: {
    padding: 0,
  },
  pressable: {
    flex: 1,
  },
  posterContainer: {
    position: "relative",
    aspectRatio: 2/3,
    borderRadius: borderRadius.lg,
    overflow: "hidden",
    marginBottom: spacing.sm,
  },
  posterPlaceholder: {
    flex: 1,
    backgroundColor: colors.surfaceVariant,
    justifyContent: "center",
    alignItems: "center",
  },
  posterOverlay: {
    position: "absolute",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    justifyContent: "space-between",
    padding: spacing.sm,
  },
  badge: {
    backgroundColor: colors.primary,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.sm,
    alignSelf: "flex-start",
  },
  playButton: {
    backgroundColor: colors.overlay,
    borderRadius: borderRadius.full,
    width: 30,
    height: 30,
    justifyContent: "center",
    alignItems: "center",
    alignSelf: "flex-end",
  },
  posterInfo: {
    gap: spacing.xs,
  },
  title: {
    minHeight: 32, // Ensure consistent height for 2 lines
  },
});
