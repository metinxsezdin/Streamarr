import React from "react";
import { View, StyleSheet, ViewStyle } from "react-native";
import { colors, spacing, borderRadius, shadows } from "../theme";

export interface CardProps {
  children: React.ReactNode;
  variant?: "default" | "elevated" | "outlined";
  padding?: "sm" | "md" | "lg";
  style?: ViewStyle;
}

export function Card({
  children,
  variant = "default",
  padding = "md",
  style,
}: CardProps) {
  const paddingKey = `padding${padding.charAt(0).toUpperCase() + padding.slice(1)}` as keyof typeof styles;
  
  const cardStyle = [
    styles.base,
    styles[variant],
    styles[paddingKey],
    style,
  ];

  return <View style={cardStyle}>{children}</View>;
}

const styles = StyleSheet.create({
  base: {
    borderRadius: borderRadius.xl,
    backgroundColor: colors.surface,
  },
  
  // Variants
  default: {
    backgroundColor: colors.surface,
  },
  elevated: {
    backgroundColor: colors.surface,
    ...shadows.lg,
  },
  outlined: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  
  // Padding
  paddingSm: {
    padding: spacing.md,
  },
  paddingMd: {
    padding: spacing.xl,
  },
  paddingLg: {
    padding: spacing.xxl,
  },
});
