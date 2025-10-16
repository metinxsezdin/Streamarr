import React from "react";
import { View, StyleSheet } from "react-native";
import { Input } from "../atoms/Input";
import { colors, spacing } from "../theme";

export interface SearchBarProps {
  value: string;
  onChangeText: (text: string) => void;
  placeholder?: string;
  style?: any;
}

export function SearchBar({
  value,
  onChangeText,
  placeholder = "Ara...",
  style,
}: SearchBarProps) {
  return (
    <View style={[styles.container, style]}>
      <Input
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        style={styles.input}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    width: "100%",
  },
  input: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
  },
});
