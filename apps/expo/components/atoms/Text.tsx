import React from "react";
import { Text as RNText, TextProps as RNTextProps, StyleSheet } from "react-native";
import { colors, typography } from "../theme";

export interface TextProps extends RNTextProps {
  variant?: "h1" | "h2" | "h3" | "body" | "bodySmall" | "label" | "labelSmall";
  color?: "primary" | "secondary" | "muted" | "accent" | "success" | "warning" | "error";
  align?: "left" | "center" | "right";
}

export function Text({
  variant = "body",
  color = "primary",
  align = "left",
  style,
  children,
  ...props
}: TextProps) {
  const textStyle = [
    styles.base,
    styles[variant],
    styles[color],
    styles[align],
    style,
  ];

  return (
    <RNText style={textStyle} {...props}>
      {children}
    </RNText>
  );
}

const styles = StyleSheet.create({
  base: {
    color: colors.text,
  },
  
  // Variants
  h1: typography.h1,
  h2: typography.h2,
  h3: typography.h3,
  body: typography.body,
  bodySmall: typography.bodySmall,
  label: typography.label,
  labelSmall: typography.labelSmall,
  
  // Colors
  primary: {
    color: colors.text,
  },
  secondary: {
    color: colors.textSecondary,
  },
  muted: {
    color: colors.textMuted,
  },
  accent: {
    color: colors.primary,
  },
  success: {
    color: colors.success,
  },
  warning: {
    color: colors.warning,
  },
  error: {
    color: colors.error,
  },
  
  // Alignment
  left: {
    textAlign: "left",
  },
  center: {
    textAlign: "center",
  },
  right: {
    textAlign: "right",
  },
});
