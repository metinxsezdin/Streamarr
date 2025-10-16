import { useState } from "react";
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

import { useRouter } from "expo-router";

import { createApiClient } from "@/lib/api";
import { useAuth } from "@/providers/AuthProvider";
import type { SetupResponse } from "@/types/api";

export default function SetupScreen() {
  const router = useRouter();
  const { completeSetup, lastBackendUrl } = useAuth();

  const [baseUrl, setBaseUrl] = useState(lastBackendUrl ?? "http://localhost:8000");
  const [resolverUrl, setResolverUrl] = useState("http://localhost:5055");
  const [strmPath, setStrmPath] = useState("/srv/streamarr/strm");
  const [tmdbKey, setTmdbKey] = useState("");
  const [htmlTitleFetch, setHtmlTitleFetch] = useState(true);
  const [runInitialJob, setRunInitialJob] = useState(true);
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(): Promise<void> {
    const trimmedBaseUrl = baseUrl.trim();
    if (!trimmedBaseUrl) {
      setError("Lütfen geçerli bir backend URL'si girin.");
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const client = createApiClient(trimmedBaseUrl, token.trim() || undefined);
      const payload = {
        resolver_url: resolverUrl.trim(),
        strm_output_path: strmPath.trim(),
        tmdb_api_key: tmdbKey.trim() ? tmdbKey.trim() : null,
        html_title_fetch: htmlTitleFetch,
        run_initial_job: runInitialJob,
        initial_job_type: "bootstrap",
        initial_job_payload: null,
      };

      const response = await client.post<SetupResponse>("/setup", payload);

      await completeSetup({
        baseUrl: trimmedBaseUrl,
        token: token.trim() ? token.trim() : undefined,
        config: response.config,
      });

      router.replace("/(tabs)/dashboard");
    } catch (submitError) {
      const message =
        submitError instanceof Error
          ? submitError.message
          : "Kurulum sırasında beklenmeyen bir hata oluştu.";
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
      <View style={styles.header}>
        <Text style={styles.title}>Streamarr Manager Kurulumu</Text>
        <Text style={styles.subtitle}>
          Backend URL'ini, resolver bağlantısını ve varsayılan STRM konumunu belirleyerek yöneticiyi yapılandırın.
        </Text>
      </View>

      <View style={styles.card}>
        <Text style={styles.label}>Manager Backend URL</Text>
        <TextInput
          value={baseUrl}
          onChangeText={setBaseUrl}
          autoCapitalize="none"
          autoCorrect={false}
          placeholder="http://localhost:8000"
          style={styles.input}
        />

        <Text style={[styles.label, styles.sectionSpacing]}>Resolver URL</Text>
        <TextInput
          value={resolverUrl}
          onChangeText={setResolverUrl}
          autoCapitalize="none"
          autoCorrect={false}
          placeholder="http://localhost:5055"
          style={styles.input}
        />

        <Text style={[styles.label, styles.sectionSpacing]}>STRM Çıktı Dizini</Text>
        <TextInput
          value={strmPath}
          onChangeText={setStrmPath}
          autoCapitalize="none"
          autoCorrect={false}
          placeholder="/srv/streamarr/strm"
          style={styles.input}
        />

        <Text style={[styles.label, styles.sectionSpacing]}>TMDB API Anahtarı (opsiyonel)</Text>
        <TextInput
          value={tmdbKey}
          onChangeText={setTmdbKey}
          autoCapitalize="none"
          autoCorrect={false}
          placeholder="TMDB API key"
          style={styles.input}
        />

        <View style={[styles.toggleRow, styles.sectionSpacing]}>
          <View>
            <Text style={styles.label}>HTML Başlık Yedeği</Text>
            <Text style={styles.helperText}>
              Dizilerde başlık bulunamazsa HTML başlığını kullan.
            </Text>
          </View>
          <Switch value={htmlTitleFetch} onValueChange={setHtmlTitleFetch} />
        </View>

        <View style={styles.toggleRow}>
          <View>
            <Text style={styles.label}>Başlangıç işini çalıştır</Text>
            <Text style={styles.helperText}>
              Kurulum sonrası pipeline'ı otomatik başlat.
            </Text>
          </View>
          <Switch value={runInitialJob} onValueChange={setRunInitialJob} />
        </View>

        <Text style={[styles.label, styles.sectionSpacing]}>API Jetonu (opsiyonel)</Text>
        <TextInput
          value={token}
          onChangeText={setToken}
          autoCapitalize="none"
          autoCorrect={false}
          placeholder="Bearer token"
          style={styles.input}
        />

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <TouchableOpacity
          style={[styles.button, submitting && styles.buttonDisabled]}
          onPress={handleSubmit}
          disabled={submitting}
        >
          {submitting ? (
            <ActivityIndicator color="#ffffff" />
          ) : (
            <Text style={styles.buttonText}>Kurulumu Tamamla</Text>
          )}
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 24,
    backgroundColor: "#0f172a",
    flexGrow: 1,
  },
  header: {
    marginBottom: 24,
  },
  title: {
    color: "#f8fafc",
    fontSize: 24,
    fontWeight: "700",
    marginBottom: 8,
  },
  subtitle: {
    color: "#cbd5f5",
    fontSize: 15,
    lineHeight: 22,
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
    maxWidth: 240,
  },
  toggleRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
  },
  button: {
    marginTop: 16,
    backgroundColor: "#2563eb",
    borderRadius: 12,
    paddingVertical: 14,
    alignItems: "center",
  },
  buttonDisabled: {
    opacity: 0.7,
  },
  buttonText: {
    color: "#ffffff",
    fontSize: 16,
    fontWeight: "600",
  },
  error: {
    color: "#f87171",
    marginTop: 8,
  },
});
