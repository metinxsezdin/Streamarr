import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import {
  ActivityIndicator,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from "react-native";

import { useAuth } from "@/providers/AuthProvider";
import type { ConfigModel } from "@/types/api";

export default function SettingsScreen(): JSX.Element {
  const { session, updateSession, signOut } = useAuth();
  const [resolverUrl, setResolverUrl] = useState("http://localhost:5055");
  const [strmPath, setStrmPath] = useState("/srv/streamarr/strm");
  const [tmdbKey, setTmdbKey] = useState("");
  const [htmlTitleFetch, setHtmlTitleFetch] = useState(true);
  const [savingError, setSavingError] = useState<string | null>(null);

  const query = useQuery({
    queryKey: ["config", session?.baseUrl],
    queryFn: () => session!.client.get<ConfigModel>("/config"),
    enabled: Boolean(session),
  });

  useEffect(() => {
    if (!query.data) {
      return;
    }

    setResolverUrl(query.data.resolver_url);
    setStrmPath(query.data.strm_output_path);
    setTmdbKey(query.data.tmdb_api_key ?? "");
    setHtmlTitleFetch(query.data.html_title_fetch);
  }, [query.data]);

  const mutation = useMutation({
    mutationFn: async () => {
      const payload = {
        resolver_url: resolverUrl.trim(),
        strm_output_path: strmPath.trim(),
        tmdb_api_key: tmdbKey.trim() ? tmdbKey.trim() : null,
        html_title_fetch: htmlTitleFetch,
      } satisfies ConfigModel;

      const result = await session!.client.put<ConfigModel>("/config", payload);
      updateSession((current) => ({ ...current, config: result }));
      return result;
    },
    onError: (error) => {
      const message =
        error instanceof Error
          ? error.message
          : "Ayarlar güncellenirken bir hata oluştu.";
      setSavingError(message);
    },
    onSuccess: () => {
      setSavingError(null);
    },
  });

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
        <Text style={styles.errorText}>Ayarlar yüklenemedi.</Text>
      </View>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.pageTitle}>Yapılandırma</Text>

      <View style={styles.card}>
        <Text style={styles.label}>Resolver URL</Text>
        <TextInput
          value={resolverUrl}
          onChangeText={setResolverUrl}
          autoCapitalize="none"
          autoCorrect={false}
          style={styles.input}
        />

        <Text style={[styles.label, styles.sectionSpacing]}>STRM Çıktı Dizini</Text>
        <TextInput
          value={strmPath}
          onChangeText={setStrmPath}
          autoCapitalize="none"
          autoCorrect={false}
          style={styles.input}
        />

        <Text style={[styles.label, styles.sectionSpacing]}>TMDB API Anahtarı</Text>
        <TextInput
          value={tmdbKey}
          onChangeText={setTmdbKey}
          autoCapitalize="none"
          autoCorrect={false}
          placeholder="Opsiyonel"
          style={styles.input}
        />

        <View style={[styles.toggleRow, styles.sectionSpacing]}>
          <View>
            <Text style={styles.label}>HTML Başlık Yedeği</Text>
            <Text style={styles.helperText}>
              Katalog oluştururken HTML başlık bilgisini kullan.
            </Text>
          </View>
          <Switch value={htmlTitleFetch} onValueChange={setHtmlTitleFetch} />
        </View>

        {savingError ? <Text style={styles.errorText}>{savingError}</Text> : null}

        <TouchableOpacity
          style={[styles.primaryButton, mutation.isPending && styles.buttonDisabled]}
          onPress={() => mutation.mutate()}
          disabled={mutation.isPending}
        >
          {mutation.isPending ? (
            <ActivityIndicator color="#ffffff" />
          ) : (
            <Text style={styles.primaryButtonText}>Kaydet</Text>
          )}
        </TouchableOpacity>
      </View>

      <View style={styles.card}>
        <Text style={styles.label}>Oturum</Text>
        <Text style={styles.helperText}>Oturumu kapatarak yeniden kurulum ekranına dönebilirsiniz.</Text>
        <TouchableOpacity style={styles.secondaryButton} onPress={() => signOut()}>
          <Text style={styles.secondaryButtonText}>Oturumu Kapat</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 24,
    gap: 24,
    backgroundColor: "#0f172a",
    flexGrow: 1,
  },
  pageTitle: {
    color: "#f8fafc",
    fontSize: 24,
    fontWeight: "700",
  },
  card: {
    backgroundColor: "#1e293b",
    borderRadius: 16,
    padding: 20,
    gap: 12,
  },
  label: {
    color: "#e2e8f0",
    fontSize: 15,
    fontWeight: "600",
  },
  sectionSpacing: {
    marginTop: 12,
  },
  input: {
    backgroundColor: "#0f172a",
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    color: "#f8fafc",
    borderWidth: 1,
    borderColor: "#334155",
  },
  helperText: {
    color: "#94a3b8",
    fontSize: 13,
    marginTop: 4,
  },
  toggleRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
  },
  primaryButton: {
    marginTop: 8,
    backgroundColor: "#2563eb",
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
  },
  buttonDisabled: {
    opacity: 0.7,
  },
  primaryButtonText: {
    color: "#ffffff",
    fontSize: 16,
    fontWeight: "600",
  },
  secondaryButton: {
    marginTop: 8,
    borderRadius: 12,
    paddingVertical: 12,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#f87171",
  },
  secondaryButtonText: {
    color: "#f87171",
    fontSize: 15,
    fontWeight: "600",
  },
  errorText: {
    color: "#f87171",
  },
  loadingContainer: {
    flex: 1,
    backgroundColor: "#0f172a",
    alignItems: "center",
    justifyContent: "center",
  },
});
