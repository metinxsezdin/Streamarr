import { Platform } from "react-native";

// Black Theme Colors
export const colors = {
  // Backgrounds
  background: "#000000",
  surface: "#111111",
  surfaceVariant: "#222222",
  
  // Borders
  border: "#333333",
  borderLight: "#444444",
  
  // Text
  text: "#f8fafc",
  textSecondary: "#94a3b8",
  textMuted: "#64748b",
  
  // Accent
  primary: "#60a5fa",
  primaryDark: "#3b82f6",
  
  // Status
  success: "#10b981",
  warning: "#f59e0b",
  error: "#ef4444",
  
  // Overlay
  overlay: "rgba(0, 0, 0, 0.7)",
  overlayLight: "rgba(0, 0, 0, 0.5)",
} as const;

// Typography
export const typography = {
  // Headers
  h1: {
    fontSize: Platform.OS === 'web' ? 32 : 28,
    fontWeight: "700" as const,
    lineHeight: Platform.OS === 'web' ? 38 : 34,
  },
  h2: {
    fontSize: Platform.OS === 'web' ? 28 : 24,
    fontWeight: "700" as const,
    lineHeight: Platform.OS === 'web' ? 34 : 30,
  },
  h3: {
    fontSize: Platform.OS === 'web' ? 24 : 20,
    fontWeight: "600" as const,
    lineHeight: Platform.OS === 'web' ? 30 : 26,
  },
  
  // Body
  body: {
    fontSize: Platform.OS === 'web' ? 16 : 14,
    fontWeight: "400" as const,
    lineHeight: Platform.OS === 'web' ? 24 : 20,
  },
  bodySmall: {
    fontSize: Platform.OS === 'web' ? 14 : 12,
    fontWeight: "400" as const,
    lineHeight: Platform.OS === 'web' ? 20 : 16,
  },
  
  // Labels
  label: {
    fontSize: Platform.OS === 'web' ? 14 : 12,
    fontWeight: "600" as const,
    lineHeight: Platform.OS === 'web' ? 18 : 16,
  },
  labelSmall: {
    fontSize: Platform.OS === 'web' ? 12 : 10,
    fontWeight: "600" as const,
    lineHeight: Platform.OS === 'web' ? 16 : 14,
  },
} as const;

// Spacing
export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  xxl: 24,
  xxxl: 32,
} as const;

// Border Radius
export const borderRadius = {
  sm: 6,
  md: 8,
  lg: 12,
  xl: 16,
  xxl: 20,
  full: 9999,
} as const;

// Shadows
export const shadows = {
  sm: {
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  md: {
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.15,
    shadowRadius: 8,
    elevation: 4,
  },
  lg: {
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.25,
    shadowRadius: 16,
    elevation: 12,
  },
} as const;

// Layout
export const layout = {
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: spacing.xxl,
  },
  grid: {
    flexDirection: "row" as const,
    flexWrap: "wrap" as const,
    gap: spacing.lg,
  },
} as const;

export type ColorKey = keyof typeof colors;
export type TypographyKey = keyof typeof typography;
export type SpacingKey = keyof typeof spacing;
export type BorderRadiusKey = keyof typeof borderRadius;
export type ShadowKey = keyof typeof shadows;
